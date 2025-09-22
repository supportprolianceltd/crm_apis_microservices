// src/subscribers/chat.subscriber.js
import { ChatService } from "../services/chatService.js";

export const setupChatSubscribers = (io, socket) => {
  // Get all chats for the current user
  const getChats = async (callback) => {
    try {
      const userId = socket.user?.id;
      const tenantId = socket.tenant?.id;

      if (!userId) {
        return callback({ status: "error", message: "User not authenticated" });
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

      callback({ status: "success", data: formattedChats });
    } catch (error) {
      console.error("Error in getChats:", error);
      callback({ status: "error", message: error.message });
    }
  };

  // Create or get existing direct chat
  const getOrCreateDirectChat = async ({ participantId }, callback) => {
    try {
      const userId = socket.user?.id;
      const tenantId = socket.tenant?.id;

      if (!userId) {
        throw new Error("User not authenticated");
      }

      const chat = await ChatService.getOrCreateDirectChat(
        userId,
        participantId,
        tenantId
      );

      callback({ status: "success", data: chat });
    } catch (error) {
      console.error("Error in getOrCreateDirectChat:", error);
      callback({ status: "error", message: error.message });
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
