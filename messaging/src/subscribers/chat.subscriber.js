// src/subscribers/chat.subscriber.js
import { ChatService } from "../services/chatService.js";

export const setupChatSubscribers = (io, socket) => {
  console.log("📋 setupChatSubscribers called for socket:", socket.id);
  // Get all chats for the current user
  const getChats = async (data, callback) => {
    try {
      console.log("📋 get_chats called");

      const userId = socket.user?.id;
      const tenantId = socket.tenant?.id;

      console.log("🔐 userId:", userId, "tenantId:", tenantId);

      if (!userId) {
        const errorMsg = { status: "error", message: "User not authenticated" };
        console.log("❌ Authentication failed");
        return callback
          ? callback(errorMsg)
          : socket.emit("get_chats_error", errorMsg);
      }

      console.log("✅ Calling ChatService.getChatsForUser");
      const chats = await ChatService.getChatsForUser(userId, tenantId);
      console.log("✅ Found chats:", chats.length);

      // Format the response
      const formattedChats = chats.map((chat) => {
        console.log("🔄 Formatting chat:", chat.id);
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
          participants: chat.users.map((u) => u.user),
          updatedAt: chat.updatedAt,
        };
      });

      const successMsg = { status: "success", data: formattedChats };
      console.log("📤 Sending get_chats response");

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

  // Send message to user (updated to use recipientId instead of recipientEmail)
  const sendMessageToUser = async ({ recipientId, content }, callback) => {
    try {
      console.log("💬 send_message_to_user called:", { recipientId, content });

      const senderId = socket.user?.id;
      const tenantId = socket.tenant?.id;
      console.log("🔐 senderId:", senderId, "tenantId:", tenantId);

      if (!senderId) {
        const errorMsg = { status: "error", message: "User not authenticated" };
        console.log("❌ Authentication failed");
        return callback ? callback(errorMsg) : socket.emit("send_message_to_user_error", errorMsg);
      }

      if (!recipientId || !content) {
        const errorMsg = { status: "error", message: "recipientId and content are required" };
        console.log("❌ Missing required fields");
        return callback ? callback(errorMsg) : socket.emit("send_message_to_user_error", errorMsg);
      }

      // Convert recipientId to integer if it's a string
      const recipientIdInt = typeof recipientId === 'string' ? parseInt(recipientId, 10) : recipientId;
      
      if (isNaN(recipientIdInt)) {
        const errorMsg = { status: "error", message: "recipientId must be a valid number" };
        console.log("❌ Invalid recipientId");
        return callback ? callback(errorMsg) : socket.emit("send_message_to_user_error", errorMsg);
      }

      console.log("✅ Calling ChatService.sendMessageToUser with recipientId:", recipientIdInt);
      const result = await ChatService.sendMessageToUser(recipientIdInt, senderId, content, tenantId);
      console.log("✅ Message sent successfully:", result.message.id);

      const successMsg = {
        status: "success",
        data: {
          message: result.message,
          chat: result.chat,
        },
      };

      console.log("📤 Sending response");
      if (callback) {
        callback(successMsg);
      } else {
        socket.emit("send_message_to_user_response", successMsg);
      }
    } catch (error) {
      console.error("❌ Error in sendMessageToUser:", error);
      const errorMsg = { status: "error", message: error.message };
      if (callback) {
        callback(errorMsg);
      } else {
        socket.emit("send_message_to_user_error", errorMsg);
      }
    }
  };

  // Create or get existing direct chat
  const getOrCreateDirectChat = async ({ participantId }, callback) => {
    try {
      console.log("🔗 get_or_create_chat called for participant:", participantId);

      const userId = socket.user?.id;
      const tenantId = socket.tenant?.id;

      console.log("🔐 userId:", userId, "tenantId:", tenantId);

      if (!userId) {
        const errorMsg = { status: "error", message: "User not authenticated" };
        console.log("❌ Authentication failed");
        return callback
          ? callback(errorMsg)
          : socket.emit("get_or_create_chat_error", errorMsg);
      }

      if (!participantId) {
        const errorMsg = { status: "error", message: "participantId is required" };
        console.log("❌ Missing participantId");
        return callback
          ? callback(errorMsg)
          : socket.emit("get_or_create_chat_error", errorMsg);
      }

      // Convert participantId to integer if it's a string
      const participantIdInt = typeof participantId === 'string' ? parseInt(participantId, 10) : participantId;
      
      if (isNaN(participantIdInt)) {
        const errorMsg = { status: "error", message: "participantId must be a valid number" };
        console.log("❌ Invalid participantId");
        return callback
          ? callback(errorMsg)
          : socket.emit("get_or_create_chat_error", errorMsg);
      }

      console.log("✅ Calling ChatService.getOrCreateDirectChat with participantId:", participantIdInt);
      const chat = await ChatService.getOrCreateDirectChat(
        userId,
        participantIdInt,
        tenantId
      );
      console.log("✅ Chat created/found:", chat.id);

      const successMsg = { status: "success", data: chat };
      console.log("📤 Sending get_or_create_chat response");

      if (callback) {
        callback(successMsg);
      } else {
        socket.emit("get_or_create_chat_response", successMsg);
      }
    } catch (error) {
      console.error("❌ Error in getOrCreateDirectChat:", error);
      const errorMsg = { status: "error", message: error.message };
      if (callback) {
        callback(errorMsg);
      } else {
        socket.emit("get_or_create_chat_error", errorMsg);
      }
    }
  };

  // Register event listeners
  console.log("🔧 Registering chat event listeners for socket:", socket.id);
  socket.on("get_chats", getChats);
  socket.on("send_message_to_user", sendMessageToUser);
  socket.on("get_or_create_chat", getOrCreateDirectChat);
  console.log("✅ Chat event listeners registered");

  // Return cleanup function
  return () => {
    console.log("🧹 Cleaning up chat subscribers for socket:", socket.id);
    socket.off("get_chats", getChats);
    socket.off("send_message_to_user", sendMessageToUser);
    socket.off("get_or_create_chat", getOrCreateDirectChat);
  };
};
