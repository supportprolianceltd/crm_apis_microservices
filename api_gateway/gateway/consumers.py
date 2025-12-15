import asyncio
import websockets
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger('gateway.websocket')

class WebSocketProxyConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer that proxies connections to microservices
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_websocket = None
        self.target_url = None

    async def connect(self):
        """
        Handle WebSocket connection from client
        """
        try:
            # Get the path from the URL route
            path = self.scope['url_route']['kwargs']['path']
            logger.info(f"WebSocket proxy connection request for path: {path}")

            # Parse the path to determine target service
            path_parts = path.strip('/').split('/')
            if not path_parts:
                await self.close(code=4000)
                return

            service_name = path_parts[0]
            sub_path = '/'.join(path_parts[1:]) if len(path_parts) > 1 else ''

            # Get target service URL
            target_service_url = self._get_target_service_url(service_name)
            if not target_service_url:
                logger.error(f"No target service URL found for {service_name}")
                await self.close(code=4001)
                return

            # Convert HTTP URL to WebSocket URL
            target_ws_url = target_service_url.replace('http://', 'ws://').replace('https://', 'wss://')

            # Construct full WebSocket URL
            if sub_path:
                # For notifications service, use ws/notifications/{sub_path}
                if service_name == 'notifications':
                    full_target_ws_url = f"{target_ws_url}/ws/notifications/{sub_path}"
                else:
                    full_target_ws_url = f"{target_ws_url}/ws/{service_name}/{sub_path}"
            else:
                full_target_ws_url = f"{target_ws_url}/ws/{service_name}/"

            # Add query parameters from original request
            query_string = self.scope.get('query_string', b'').decode('utf-8')
            if query_string:
                full_target_ws_url += f"?{query_string}"

            self.target_url = full_target_ws_url
            logger.info(f"Proxying WebSocket to: {self.target_url}")

            # Accept the client connection
            await self.accept()

            # Start proxying
            await self._start_proxy()

        except Exception as e:
            logger.exception(f"WebSocket proxy connection error: {str(e)}")
            await self.close(code=4002)

    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection
        """
        logger.info(f"WebSocket proxy disconnect: {close_code}")
        if self.target_websocket:
            try:
                await self.target_websocket.close()
            except Exception as e:
                logger.warning(f"Error closing target WebSocket: {str(e)}")

    async def receive(self, text_data=None, bytes_data=None):
        """
        Handle messages from client
        """
        if self.target_websocket:
            try:
                if text_data:
                    await self.target_websocket.send(text_data)
                elif bytes_data:
                    await self.target_websocket.send(bytes_data)
            except Exception as e:
                logger.error(f"Error sending to target WebSocket: {str(e)}")
                await self.close(code=4003)

    async def _start_proxy(self):
        """
        Start proxying between client and target service
        """
        try:
            # Connect to target WebSocket
            self.target_websocket = await websockets.connect(
                self.target_url,
                additional_headers=self._get_forward_headers(),
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5
            )

            logger.info(f"Connected to target WebSocket: {self.target_url}")

            # Start bidirectional message forwarding
            await asyncio.gather(
                self._forward_from_target(),
                self._forward_from_client()
            )

        except Exception as e:
            logger.error(f"Failed to connect to target WebSocket: {str(e)}")
            await self.close(code=4004)

    async def _forward_from_target(self):
        """
        Forward messages from target service to client
        """
        try:
            async for message in self.target_websocket:
                if isinstance(message, str):
                    await self.send(text_data=message)
                else:
                    await self.send(bytes_data=message)
        except websockets.exceptions.ConnectionClosed:
            logger.info("Target WebSocket connection closed")
            await self.close()
        except Exception as e:
            logger.error(f"Error forwarding from target: {str(e)}")
            await self.close(code=4005)

    async def _forward_from_client(self):
        """
        Forward messages from client to target service (handled in receive method)
        """
        # This is handled by the receive method
        # We use a simple loop to keep the gather alive
        while True:
            await asyncio.sleep(1)

    def _get_target_service_url(self, service_name):
        """
        Get the target service URL for a given service name
        """
        service_urls = getattr(settings, 'MICROSERVICE_URLS', {})
        return service_urls.get(service_name)

    def _get_forward_headers(self):
        """
        Get headers to forward to target service
        """
        headers = {}

        # Forward authorization header if present
        if 'authorization' in self.scope.get('headers', {}):
            for header_name, header_value in self.scope['headers']:
                if header_name == b'authorization':
                    headers['Authorization'] = header_value.decode('utf-8')
                    break

        # Add gateway headers
        headers['X-Gateway-Request-ID'] = f"gateway_ws_{id(self)}"
        headers['X-Gateway-Service'] = 'websocket-proxy'

        return headers