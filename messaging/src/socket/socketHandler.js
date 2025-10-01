// src/socket/socketHandler.js
import { setupSubscribers } from "../subscribers/index.js";
import { socketAuth } from "../middleware/auth.middleware.js";
import prisma from "../config/prisma.js";

export const initializeSocket = (io) => {
  // Apply socket auth middleware
  io.use(socketAuth);

  // Handle connections
  io.on("connection", (socket) => {
    console.log("🔌 New WebSocket connection:", socket.id);
    console.log("🔐 Socket user:", socket.user);
    console.log("🏢 Socket tenant:", socket.tenant);

    // Set up all subscribers after authentication
    const cleanupSubscribers = setupSubscribers(io, socket);
    console.log("✅ Subscribers setup completed");

    // Debug: Log all incoming events
    socket.onAny((eventName, ...args) => {
      console.log(`📨 Event received: ${eventName}`, args);
    });

    // Handle disconnection
    socket.on("disconnect", async () => {
      console.log("🔌 Client disconnected:", socket.id);

      // Update user presence
      if (socket.user?.id) {
        try {
          console.log(`👤 Updating presence for user ${socket.user.id}`);
          await prisma.user.update({
            where: { id: socket.user.id },
            data: {
              online: false,
              lastSeen: new Date(),
            },
          });
          console.log(`✅ User ${socket.user.id} marked offline`);
        } catch (error) {
          console.error("❌ Error updating user presence on disconnect:", error);
        }
      }

      cleanupSubscribers?.();
    });

    // Handle authentication (this runs after socketAuth middleware)
    socket.on("authenticate", async ({ token }, callback) => {
      try {
        // The socketAuth middleware should have already validated the token
        // and set socket.user and socket.tenant

        if (!socket.user?.id) {
          throw new Error("Authentication failed - no user context");
        }

        // Update user presence
        await prisma.user.update({
          where: { id: socket.user.id },
          data: {
            online: true,
            lastSeen: null,
          },
        });

        // Join user's presence room
        socket.join(`user_${socket.user.id}`);

        // Get user's active chats and join those rooms
        const userChats = await prisma.chat.findMany({
          where: {
            users: {
              some: {
                userId: socket.user.id,
                leftAt: null,
              },
            },
          },
          select: { id: true },
        });

        // Join all chat rooms
        userChats.forEach((chat) => {
          socket.join(`chat_${chat.id}`);
        });

        // Notify client of successful auth
        socket.emit("authenticated");
        callback?.({ status: "success" });
      } catch (error) {
        console.error("Authentication error:", error);
        callback?.({ status: "error", message: error.message });
        socket.disconnect();
      }
    });
  });
};
