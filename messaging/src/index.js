import express from 'express';
import http from 'http';
import { Server } from 'socket.io';
import { config } from 'dotenv';

// Load environment variables
config();

const app = express();
const server = http.createServer(app);
const io = new Server(server);

const PORT = process.env.PORT || 3000;

// Import routes
import apiRoutes from './api/routes.js';

app.use(express.json());

app.get('/', (req, res) => {
  res.send('<h1>Messaging Service</h1>');
});

app.use('/api/v1', apiRoutes);

// Initialize socket
import initializeSocket from './socket/socketHandler.js';
initializeSocket(io);

server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
