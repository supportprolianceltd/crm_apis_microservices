import prisma from "../config/prisma.js";

export const setupPresenceSubscribers = (io, socket) => {
  const updateOnlineStatus = async (userId, isOnline) => {
    try {
      await prisma.user.update({
        where: { id: userId },
        data: {
          online: isOnline,
          lastSeen: isOnline ? null : new Date(),
        },
      });

      // Notify other users
      socket.broadcast.emit("user_status_change", {
        userId,
        isOnline,
        lastSeen: isOnline ? null : new Date(),
      });
    } catch (error) {
      console.error("Error updating online status:", error);
    }
  };

  // Handle user going online
  const handleOnline = async (callback) => {
    try {
      const userId = socket.user?.id;
      if (!userId) {
        throw new Error("User not authenticated");
      }

      // Join user's presence room
      socket.join(`user_${userId}`);

      // Update online status
      await updateOnlineStatus(userId, true);

      // Get user's active chats
      const userChats = await prisma.chat.findMany({
        where: {
          users: {
            some: {
              userId,
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

      callback?.({ status: "success" });
    } catch (error) {
      console.error("Error in handleOnline:", error);
      callback?.({ status: "error", message: error.message });
    }
  };

  // Handle user going offline
  const handleOffline = async () => {
    try {
      const userId = socket.user?.id;
      if (userId) {
        await updateOnlineStatus(userId, false);
      }
    } catch (error) {
      console.error("Error in handleOffline:", error);
    }
  };

  // Register event listeners
  socket.on("online", handleOnline);
  socket.on("disconnect", handleOffline);

  // Return cleanup function
  return () => {
    socket.off("online", handleOnline);
    socket.off("disconnect", handleOffline);
  };
};
