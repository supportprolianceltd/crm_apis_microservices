function initializeSocket(io) {
  io.on('connection', (socket) => {
    console.log(`A user connected with socket id: ${socket.id}`);

    // Event to join a chat room
    socket.on('joinChat', (chatId) => {
      socket.join(chatId);
      console.log(`User ${socket.id} joined chat ${chatId}`);
    });

    // Event to send a message
    socket.on('sendMessage', (data) => {
      const { chatId, message } = data;
      // Broadcast the message to everyone in the chat room
      io.to(chatId).emit('receiveMessage', message);
      console.log(`Message sent to chat ${chatId}: ${message.content}`);
      
      // Here you would typically save the message to the database
      // e.g., messageService.createMessage(message);
    });

    // Handle disconnection
    socket.on('disconnect', () => {
      console.log(`User ${socket.id} disconnected`);
    });
  });
}

export default initializeSocket;
