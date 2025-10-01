import { ChatService } from "../services/chatService.js";

export const setupMessageSubscribers = (io, socket) => {
  console.log("💬 setupMessageSubscribers called for socket:", socket.id);

  // Get message history for a chat with pagination
  const getMessages = async ({ chatId, limit, offset, before }, callback) => {
    try {
      console.log("📜 get_messages called for chat:", chatId);
      console.log("📊 Pagination params:", { limit, offset, before });

      const userId = socket.user?.id;

      if (!userId) {
        const errorMsg = { status: "error", message: "User not authenticated" };
        console.log("❌ Authentication failed");
        return callback
          ? callback(errorMsg)
          : socket.emit("get_messages_error", errorMsg);
      }

      if (!chatId) {
        const errorMsg = { status: "error", message: "chatId is required" };
        console.log("❌ Missing chatId");
        return callback
          ? callback(errorMsg)
          : socket.emit("get_messages_error", errorMsg);
      }

      // Set default pagination values
      const paginationOptions = {
        limit: limit ? parseInt(limit, 10) : 50,
        offset: offset ? parseInt(offset, 10) : 0,
        before: before || null,
      };

      // Validate pagination params
      if (isNaN(paginationOptions.limit) || paginationOptions.limit < 1 || paginationOptions.limit > 100) {
        const errorMsg = { status: "error", message: "limit must be between 1 and 100" };
        console.log("❌ Invalid limit");
        return callback
          ? callback(errorMsg)
          : socket.emit("get_messages_error", errorMsg);
      }

      if (isNaN(paginationOptions.offset) || paginationOptions.offset < 0) {
        const errorMsg = { status: "error", message: "offset must be 0 or greater" };
        console.log("❌ Invalid offset");
        return callback
          ? callback(errorMsg)
          : socket.emit("get_messages_error", errorMsg);
      }

      console.log("✅ Calling ChatService.getMessages");
      const result = await ChatService.getMessages(chatId, userId, paginationOptions);
      console.log(`✅ Retrieved ${result.messages.length} messages (total: ${result.total})`);

      const successMsg = {
        status: "success",
        data: {
          messages: result.messages,
          hasMore: result.hasMore,
          total: result.total,
          limit: paginationOptions.limit,
          offset: paginationOptions.offset,
        },
      };

      console.log("📤 Sending get_messages response");
      if (callback) {
        callback(successMsg);
      } else {
        socket.emit("get_messages_response", successMsg);
      }
    } catch (error) {
      console.error("❌ Error in getMessages:", error);
      const errorMsg = { status: "error", message: error.message };
      if (callback) {
        callback(errorMsg);
      } else {
        socket.emit("get_messages_error", errorMsg);
      }
    }
  };

  // Send a new message
  const sendMessage = async ({ chatId, content }, callback) => {
    try {
      const userId = socket.user?.id;

      if (!userId) {
        const errorMsg = { status: "error", message: "User not authenticated" };
        return callback
          ? callback(errorMsg)
          : socket.emit("send_message_error", errorMsg);
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

      const successMsg = { status: "success", data: message };
      if (callback) {
        callback(successMsg);
      } else {
        socket.emit("send_message_response", successMsg);
      }
    } catch (error) {
      console.error("Error in sendMessage:", error);
      const errorMsg = { status: "error", message: error.message };
      if (callback) {
        callback(errorMsg);
      } else {
        socket.emit("send_message_error", errorMsg);
      }
    }
  };

  // Send message to user (creates chat if it doesn't exist)
  const sendMessageToUser = async (
    { recipientId, recipientEmail, content },
    callback
  ) => {
    try {
      const userId = socket.user?.id;
      const tenantId = socket.tenant?.id;

      if (!userId) {
        const errorMsg = { status: "error", message: "User not authenticated" };
        return callback
          ? callback(errorMsg)
          : socket.emit("send_message_to_user_error", errorMsg);
      }

      if (!content || content.trim().length === 0) {
        const errorMsg = {
          status: "error",
          message: "Message content is required",
        };
        return callback
          ? callback(errorMsg)
          : socket.emit("send_message_to_user_error", errorMsg);
      }

      if (content.length > 2000) {
        const errorMsg = {
          status: "error",
          message: "Message content too long (max 2000 characters)",
        };
        return callback
          ? callback(errorMsg)
          : socket.emit("send_message_to_user_error", errorMsg);
      }

      let result;

      if (recipientId) {
        // Send message to user by ID
        result = await ChatService.sendMessageToUser(
          recipientId,
          userId,
          content,
          tenantId
        );
      } else if (recipientEmail) {
        // Send message to user by email
        result = await ChatService.sendMessageToUserByEmail(
          recipientEmail,
          userId,
          content,
          tenantId
        );
      } else {
        const errorMsg = {
          status: "error",
          message: "Either recipientId or recipientEmail is required",
        };
        return callback
          ? callback(errorMsg)
          : socket.emit("send_message_to_user_error", errorMsg);
      }

      const { message, chat } = result;

      // Emit the new message to all participants
      chat.users.forEach((participant) => {
        if (participant.user.online) {
          io.to(`user_${participant.userId}`).emit("new_message", {
            chatId: chat.id,
            message,
            unreadCount:
              participant.userId === userId ? 0 : participant.unreadCount,
          });
        }
      });

      const successMsg = {
        status: "success",
        data: {
          message,
          chat: chat,
        },
      };

      if (callback) {
        callback(successMsg);
      } else {
        socket.emit("send_message_to_user_response", successMsg);
      }
    } catch (error) {
      console.error("Error in sendMessageToUser:", error);
      const errorMsg = { status: "error", message: error.message };
      if (callback) {
        callback(errorMsg);
      } else {
        socket.emit("send_message_to_user_error", errorMsg);
      }
    }
  };

  // Mark messages as read (supports single message ID or array of message IDs)
  const markAsRead = async ({ chatId, messageIds }, callback) => {
    try {
      const userId = socket.user?.id;

      if (!userId) {
        const errorMsg = {
          status: "error",
          message: "User not authenticated",
        };
        return callback
          ? callback(errorMsg)
          : socket.emit("mark_as_read_error", errorMsg);
      }

      if (!chatId) {
        const errorMsg = { status: "error", message: "Chat ID is required" };
        return callback
          ? callback(errorMsg)
          : socket.emit("mark_as_read_error", errorMsg);
      }

      if (
        !messageIds ||
        (Array.isArray(messageIds) && messageIds.length === 0)
      ) {
        const errorMsg = {
          status: "error",
          message: "At least one message ID is required",
        };
        return callback
          ? callback(errorMsg)
          : socket.emit("mark_as_read_error", errorMsg);
      }

      await ChatService.markMessagesAsRead(chatId, userId, messageIds);

      // Notify other participants that messages were read
      socket.to(`chat_${chatId}`).emit("messages_read", {
        chatId,
        messageIds: Array.isArray(messageIds) ? messageIds : [messageIds],
        readBy: userId,
        readAt: new Date(),
      });

      const successMsg = { status: "success" };
      if (callback) {
        callback(successMsg);
      } else {
        socket.emit("mark_as_read_response", successMsg);
      }
    } catch (error) {
      console.error("Error in markAsRead:", error);
      const errorMsg = { status: "error", message: error.message };
      if (callback) {
        callback(errorMsg);
      } else {
        socket.emit("mark_as_read_error", errorMsg);
      }
    }
  };

  // Register event listeners
  console.log("🔧 Registering message event listeners for socket:", socket.id);
  socket.on("get_messages", getMessages);
  socket.on("send_message", sendMessage);
  socket.on("send_message_to_user", sendMessageToUser);
  socket.on("mark_as_read", markAsRead);
  console.log("✅ Message event listeners registered");

  // Return cleanup function
  return () => {
    console.log("🧹 Cleaning up message subscribers for socket:", socket.id);
    socket.off("get_messages", getMessages);
    socket.off("send_message", sendMessage);
    socket.off("send_message_to_user", sendMessageToUser);
    socket.off("mark_as_read", markAsRead);
  };
};
