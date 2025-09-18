import jwt from "jsonwebtoken";

const initializeSocket = (io) => {
  const onlineUsers = new Map(); // userId -> socketId

  // Update user's online status in DB
  const updateOnlineStatus = async (userId, isOnline) => {
    try {
      await prisma.user.update({
        where: { id: userId },
        data: {
          online: isOnline,
          lastSeen: isOnline ? null : new Date(),
        },
      });
    } catch (error) {
      console.error("Error updating online status:", error);
    }
  };

  io.on("connection", (socket) => {
    console.log("New WebSocket connection:", socket.id);

    socket.on("authenticate", async ({ token }) => {
      if (!token) {
        socket.emit("error", { message: "Token is required" });
        return;
      }

      try {
        // Verify token and get user with tenant info
        const decoded = jwt.verify(token, process.env.JWT_SECRET);
        console.log(decoded);

        const user = await prisma.user.findUnique({
          where: {
            id: decoded.user_id, // Get user ID from token
            tenantId: decoded.tenant_id,
          },
          include: {
            contacts: {
              where: { tenantId: decoded.tenant_id },
              select: { id: true, online: true },
            },
          },
        });

        if (!user) {
          throw new Error("User not found or unauthorized");
        }

        // Store socket info
        onlineUsers.set(user.id, socket.id);
        socket.userId = user.id;
        socket.tenantId = decoded.tenant_id;

        // Update online status in DB
        await updateOnlineStatus(user.id, true);

        // Rest of the code remains the same...
      } catch (error) {
        console.error("Authentication error:", error);
        socket.emit("error", {
          message: "Authentication failed",
          details: error.message,
        });
        socket.disconnect();
      }
    });

    // Handle private messages
    socket.on("private_message", async ({ to, content }) => {
      try {
        if (!socket.userId) {
          throw new Error("User not authenticated");
        }

        // 1. Save message to database
        const message = await prisma.message.create({
          data: {
            content,
            senderId: socket.userId,
            receiverId: to,
            status: "DELIVERED",
          },
          include: {
            sender: {
              select: { id: true, username: true, email: true },
            },
          },
        });

        // 2. Check if recipient is online
        const recipientSocketId = onlineUsers.get(to);
        if (recipientSocketId) {
          // 3. If online, send the message directly
          io.to(recipientSocketId).emit("new_message", message);
        }
        // else {
        //   // 4. If offline, create a notification
        //   await prisma.notification.create({
        //     data: {
        //       type: "NEW_MESSAGE",
        //       userId: to,
        //       data: {
        //         messageId: message.id,
        //         from: message.senderId,
        //         preview:
        //           content.length > 50
        //             ? content.substring(0, 50) + "..."
        //             : content,
        //       },
        //       read: false,
        //     },
        //   });

        // Optionally: Trigger email/push notification here
        // await notificationService.sendPushNotification(...);
        // }

        // 5. Send delivery confirmation to sender
        socket.emit("message_delivered", {
          messageId: message.id,
          timestamp: new Date().toISOString(),
          status: recipientSocketId ? "DELIVERED" : "SENT",
        });
      } catch (error) {
        console.error("Error sending message:", error);
        socket.emit("error", {
          message: "Failed to send message",
          details: error.message,
        });
      }
    });

    // Handle typing indicator
    socket.on("typing", async ({ to, isTyping }) => {
      try {
        const recipientSocketId = onlineUsers.get(to);
        if (recipientSocketId) {
          io.to(recipientSocketId).emit("user_typing", {
            from: socket.userId,
            isTyping,
            tenantId: socket.tenantId,
          });
        }
      } catch (error) {
        console.error("Error handling typing indicator:", error);
      }
    });

    socket.on("mark_as_read", async ({ messageId }) => {
      try {
        if (!socket.userId) {
          throw new Error("Not authenticated");
        }

        const message = await prisma.message.update({
          where: {
            id: messageId,
            // Ensure user is the recipient
            chat: {
              users: {
                some: { userId: socket.userId },
              },
            },
          },
          data: {
            status: "READ",
            readAt: new Date(),
          },
        });

        // Notify the sender that their message was read
        const senderSocketId = onlineUsers.get(message.authorId);
        if (senderSocketId) {
          io.to(senderSocketId).emit("message_read", {
            messageId: message.id,
            readAt: message.readAt,
          });
        }
      } catch (error) {
        console.error("Error marking message as read:", error);
        socket.emit("error", { message: "Failed to mark message as read" });
      }
    });

    socket.on("disconnect", async () => {
      if (socket.userId) {
        onlineUsers.delete(socket.userId);
        await updateOnlineStatus(socket.userId, false);

        try {
          const user = await prisma.user.findUnique({
            where: { id: socket.userId },
            select: { contacts: { select: { id: true } } },
          });

          user?.contacts.forEach(({ id }) => {
            const contactSocketId = onlineUsers.get(id);
            if (contactSocketId) {
              io.to(contactSocketId).emit("user_offline", {
                userId: socket.userId,
              });
            }
          });
        } catch (error) {
          console.error("Error handling disconnection:", error);
        }
      }
    });
  });
};

export default initializeSocket;
