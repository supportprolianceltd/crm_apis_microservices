const initializeSocket = (io) => {
  io.on("connection", (socket) => {
    console.log("New WebSocket connection:", {
      id: socket.id,
      handshake: socket.handshake,
      connected: socket.connected,
    });

    // Join a specific chat room
    socket.on("join_chat", (chatId) => {
      socket.join(chatId);
      console.log(`User ${socket.id} joined chat ${chatId}`);
      io.to(chatId).emit("user_joined", {
        userId: socket.id,
        chatId,
        message: `User ${socket.id} joined the chat`,
      });
    });

    // Handle new messages
    socket.on("send_message", (data) => {
      try {
        const { chatId, content, userId } = data;
        console.log("New message:", { chatId, content, userId });

        // Create message object
        const message = {
          id: Date.now().toString(),
          chatId,
          content,
          userId,
          timestamp: new Date().toISOString(),
        };

        // Broadcast the message to all clients in the chat room
        io.to(chatId).emit("receive_message", message);
      } catch (error) {
        console.error("Error handling message:", error);
      }
    });

    // Handle typing indicators
    socket.on("typing", (data) => {
      const { chatId, userId, isTyping } = data;
      socket.to(chatId).emit("user_typing", {
        userId,
        isTyping,
        timestamp: new Date().toISOString(),
      });
    });

    // Handle disconnection
    socket.on("disconnect", () => {
      console.log(`User ${socket.id} disconnected`);
    });
  });
};

export default initializeSocket;
