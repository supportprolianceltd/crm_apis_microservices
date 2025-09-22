import { ChatService } from "../services/chatService.js";

export const setupMessageSubscribers = (io, socket) => {
  // Send a new message
  const sendMessage = async ({ chatId, content }, callback) => {
    try {
      const userId = socket.user?.id;

      if (!userId) {
        throw new Error("User not authenticated");
      }

      const { message, chat } = await ChatService.sendMessage(
        chatId,
        userId,
        content
      );

      // Emit the new message to all participants
      chat.users.forEach((participant) => {
        if (participant.user.online) {
          io.to(`user_${participant.userId}`).emit("new_message", {
            chatId,
            message,
            unreadCount:
              participant.userId === userId ? 0 : participant.unreadCount,
          });
        }
      });

      callback({ status: "success", data: message });
    } catch (error) {
      console.error("Error in sendMessage:", error);
      callback({ status: "error", message: error.message });
    }
  };

  // Mark messages as read
  const markAsRead = async ({ chatId, messageId }, callback) => {
    try {
      const userId = socket.user?.id;

      if (!userId) {
        throw new Error("User not authenticated");
      }

      await ChatService.markMessagesAsRead(chatId, userId, messageId);

      // Notify other participants that messages were read
      socket.to(`chat_${chatId}`).emit("messages_read", {
        chatId,
        messageId,
        readBy: userId,
        readAt: new Date(),
      });

      callback({ status: "success" });
    } catch (error) {
      console.error("Error in markAsRead:", error);
      callback({ status: "error", message: error.message });
    }
  };

  // Register event listeners
  socket.on("send_message", sendMessage);
  socket.on("mark_as_read", markAsRead);

  // Return cleanup function
  return () => {
    socket.off("send_message", sendMessage);
    socket.off("mark_as_read", markAsRead);
  };
};
