from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

logger = logging.getLogger('notifications.channels')

class BaseHandler(ABC):
    def __init__(self, tenant_id: str, credentials: dict):
        self.tenant_id = tenant_id
        self.credentials = credentials

    @abstractmethod
    async def send(self, recipient: str, content: dict, context: dict) -> Dict[str, Any]:
        """Send message and return {'success': bool, 'error': str, 'response': any}"""
        pass

    def log_result(self, record_id: str, result: Dict[str, Any]):
        logger.info(f"Tenant {self.tenant_id}: Notification {record_id} - {result}")