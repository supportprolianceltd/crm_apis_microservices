const express = require('express');
const http = require('http');
const { Server } = require("socket.io");
require('dotenv').config();

const app = express();
const server = http.createServer(app);
const io = new Server(server);

const PORT = process.env.PORT || 3000;

const apiRoutes = require('./api/routes');

app.use(express.json());

app.get('/', (req, res) => {
  res.send('<h1>Messaging Service</h1>');
});

app.use('/api/v1', apiRoutes);


const initializeSocket = require('./socket/socketHandler');
initializeSocket(io);

server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
