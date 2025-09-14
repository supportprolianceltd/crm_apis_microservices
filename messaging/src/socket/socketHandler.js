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

    socket.on("authenticate", async ({ userId, token }) => {
      if (!userId || !token) {
        socket.emit("error", { message: "User ID and token are required" });
        return;
      }

      try {
        // Verify token and get user with tenant info
        const decoded = jwt.verify(token, process.env.JWT_SECRET);
        const user = await prisma.user.findUnique({
          where: {
            id: userId,
            tenantId: decoded.tenant_id, // Ensure user belongs to the tenant in token
          },
          include: {
            contacts: {
              where: { tenantId: decoded.tenant_id }, // Only include same-tenant contacts
              select: { id: true, online: true },
            },
          },
        });

        if (!user) {
          throw new Error("User not found or unauthorized");
        }

        // Store socket info
        onlineUsers.set(userId, socket.id);
        socket.userId = userId;
        socket.tenantId = decoded.tenant_id;

        // Update online status in DB
        await updateOnlineStatus(userId, true);

        // Notify contacts
        user.contacts.forEach((contact) => {
          const contactSocketId = onlineUsers.get(contact.id);
          if (contactSocketId) {
            io.to(contactSocketId).emit("user_online", { userId });
          }
        });

        // Send online contacts list
        const onlineContacts = user.contacts
          .filter((contact) => contact.online)
          .map((contact) => contact.id);

        socket.emit("online_contacts", onlineContacts);
      } catch (error) {
        console.error("Authentication error:", error);
        socket.emit("error", { message: "Authentication failed" });
        socket.disconnect();
      }
    });
    // Handle private messages
    socket.on("private_message", async ({ to, content }) => {
      try {
        if (!socket.userId) {
          throw new Error("User not authenticated");
        }

        // Save message to database
        const message = await prisma.message.create({
          data: {
            content,
            senderId: socket.userId,
            receiverId: to,
          },
        });

        // If recipient is online, send the message
        const recipientSocketId = onlineUsers.get(to);
        if (recipientSocketId) {
          io.to(recipientSocketId).emit("new_message", message);
        }

        // Send delivery confirmation to sender
        socket.emit("message_delivered", {
          messageId: message.id,
          timestamp: new Date().toISOString(),
        });
      } catch (error) {
        console.error("Error sending message:", error);
        socket.emit("error", { message: "Failed to send message" });
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
