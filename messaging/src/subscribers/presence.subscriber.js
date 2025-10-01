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
    const getOnlineStatus = async ({ userId }, callback) => {
      try {
        const currentUserId = socket.user?.id;
        const tenantId = socket.tenant?.id;

        if (!currentUserId) {
          const errorMsg = {
            status: "error",
            message: "User not authenticated",
          };
          return callback
            ? callback(errorMsg)
            : socket.emit("get_online_status_error", errorMsg);
        }

        if (!userId) {
          const errorMsg = { status: "error", message: "User ID is required" };
          return callback
            ? callback(errorMsg)
            : socket.emit("get_online_status_error", errorMsg);
        }

        // Verify user exists in same tenant
        const user = await prisma.user.findFirst({
          where: {
            id: userId,
            ...(tenantId ? { tenantId } : {}),
          },
          select: {
            id: true,
            online: true,
            lastSeen: true,
            username: true,
            firstName: true,
            lastName: true,
            email: true,
          },
        });

        if (!user) {
          const errorMsg = {
            status: "error",
            message: "User not found or not in same tenant",
          };
          return callback
            ? callback(errorMsg)
            : socket.emit("get_online_status_error", errorMsg);
        }

        const successMsg = {
          status: "success",
          data: {
            userId: user.id,
            online: user.online,
            lastSeen: user.lastSeen,
            displayName:
              user.username ||
              `${user.firstName} ${user.lastName}`.trim() ||
              user.email,
          },
        };

        if (callback) {
          callback(successMsg);
        } else {
          socket.emit("get_online_status_response", successMsg);
        }
      } catch (error) {
        console.error("Error in getOnlineStatus:", error);
        const errorMsg = { status: "error", message: error.message };
        if (callback) {
          callback(errorMsg);
        } else {
          socket.emit("get_online_status_error", errorMsg);
        }
      }
    };

    // Get all users in tenant with their status
    const getUsers = async (data, callback) => {
      try {
        console.log("🔍 get_users called");
        console.log("🔐 socket.user:", socket.user);
        console.log("🏢 socket.tenant:", socket.tenant);

        const currentUserId = socket.user?.id;
        const tenantId = socket.tenant?.id;

        if (!currentUserId) {
          console.log("❌ ERROR: User not authenticated - socket.user is undefined");
          const errorMsg = {
            status: "error",
            message: "User not authenticated - please connect with a valid JWT token",
          };
          return callback
            ? callback(errorMsg)
            : socket.emit("get_users_error", errorMsg);
        }

        if (!tenantId) {
          console.log("❌ ERROR: Tenant not found - socket.tenant is undefined");
          const errorMsg = {
            status: "error",
            message: "Tenant context not available",
          };
          return callback
            ? callback(errorMsg)
            : socket.emit("get_users_error", errorMsg);
        }

        console.log(`✅ Authenticated user: ${currentUserId} in tenant: ${tenantId}`);

        // Get all users in the same tenant
        const users = await prisma.user.findMany({
          where: {
            ...(tenantId ? { tenantId } : {}),
            // Exclude current user from the list
            NOT: { id: currentUserId },
          },
          select: {
            id: true,
            username: true,
            firstName: true,
            lastName: true,
            email: true,
            online: true,
            lastSeen: true,
            role: true,
          },
          orderBy: [
            { online: "desc" }, // Online users first
            { lastSeen: "desc" }, // Then by last seen
          ],
        });

        console.log(`📊 Found ${users.length} users in tenant`);

        const formattedUsers = users.map((user) => ({
          id: user.id,
          username: user.username,
          email: user.email,
          displayName:
            user.username ||
            `${user.firstName} ${user.lastName}`.trim() ||
            user.email,
          firstName: user.firstName,
          lastName: user.lastName,
          online: user.online,
          lastSeen: user.lastSeen,
          role: user.role,
        }));

        const successMsg = { status: "success", data: formattedUsers };
        console.log("✅ Sending get_users response");

        if (callback) {
          callback(successMsg);
        } else {
          socket.emit("get_users_response", successMsg);
        }
      } catch (error) {
        console.error("❌ Error in getUsers:", error);
        const errorMsg = { status: "error", message: error.message };
        if (callback) {
          callback(errorMsg);
        } else {
          socket.emit("get_users_error", errorMsg);
        }
      }
    };

    // Register event listeners
    console.log("🔧 Registering presence event listeners for socket:", socket.id);
    socket.on("online", handleOnline);
    socket.on("disconnect", handleOffline);
    socket.on("get_online_status", getOnlineStatus);
    socket.on("get_users", getUsers);
    console.log("✅ Presence event listeners registered");

    // Return cleanup function
    return () => {
      console.log("🧹 Cleaning up presence subscribers for socket:", socket.id);
      socket.off("online", handleOnline);
      socket.off("disconnect", handleOffline);
      socket.off("get_online_status", getOnlineStatus);
      socket.off("get_users", getUsers);
    };
  };
};
