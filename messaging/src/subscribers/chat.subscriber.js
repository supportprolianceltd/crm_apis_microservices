// src/subscribers/chat.subscriber.js
import { ChatService } from "../services/chatService.js";

export const setupChatSubscribers = (io, socket) => {
  // Get all chats for the current user
  const getChats = async (data, callback) => {
    try {
      const userId = socket.user?.id;
      const tenantId = socket.tenant?.id;

      if (!userId) {
        const errorMsg = { status: "error", message: "User not authenticated" };
        return callback ? callback(errorMsg) : socket.emit("get_chats_error", errorMsg);
      }

      const chats = await ChatService.getUserChats(userId, tenantId);

      // Format the response
      const formattedChats = chats.map((chat) => {
        const otherParticipants = chat.users
          .filter((p) => p.userId !== userId)
          .map((p) => p.user);

        return {
          id: chat.id,
          name:
            chat.name ||
            otherParticipants
              .map(
                (u) =>
                  u.username || `${u.firstName} ${u.lastName}`.trim() || u.email
              )
              .join(", "),
          type: chat.type || "DIRECT",
          unreadCount:
            chat.users.find((u) => u.userId === userId)?.unreadCount || 0,
          lastMessage: chat.lastMessage,
          participants: chat.users.map((u) => u.user),
          updatedAt: chat.updatedAt,
        };
      });

      const successMsg = { status: "success", data: formattedChats };
      if (callback) {
        callback(successMsg);
      } else {
        socket.emit("get_chats_response", successMsg);
      }
    } catch (error) {
      console.error("Error in getChats:", error);
      const errorMsg = { status: "error", message: error.message };
      if (callback) {
        callback(errorMsg);
      } else {
        socket.emit("get_chats_error", errorMsg);
      }
    }
  };

  // Create or get existing direct chat
  const getOrCreateDirectChat = async ({ participantId }, callback) => {
    try {
      const userId = socket.user?.id;
      const tenantId = socket.tenant?.id;

      if (!userId) {
        const errorMsg = { status: "error", message: "User not authenticated" };
        return callback ? callback(errorMsg) : socket.emit("get_or_create_chat_error", errorMsg);
      }

      const chat = await ChatService.getOrCreateDirectChat(
        userId,
        participantId,
        tenantId
      );

      const successMsg = { status: "success", data: chat };
      if (callback) {
        callback(successMsg);
      } else {
        socket.emit("get_or_create_chat_response", successMsg);
      }
    } catch (error) {
      console.error("Error in getOrCreateDirectChat:", error);
      const errorMsg = { status: "error", message: error.message };
      if (callback) {
        callback(errorMsg);
      } else {
        socket.emit("get_or_create_chat_error", errorMsg);
      }
    }
  };

  // Register event listeners
  socket.on("get_chats", getChats);
  socket.on("get_or_create_chat", getOrCreateDirectChat);

  // Return cleanup function
  return () => {
    socket.off("get_chats", getChats);
    socket.off("get_or_create_chat", getOrCreateDirectChat);
  };
};
