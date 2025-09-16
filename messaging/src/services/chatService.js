import prisma from "../config/prisma.js";

const getChatsForUser = async (userId) => {
  const userChats = await prisma.usersOnChats.findMany({
    where: { userId: userId },
    include: {
      chat: {
        include: {
          users: {
            include: {
              user: true,
            },
          },
        },
      },
    },
  });

  return userChats.map((uc) => uc.chat);
};

const updateMessageStatus = async (messageId, status) => {
  try {
    const { messageId } = req.params;
    const userId = req.user.id;

    // 1. Find the message
    const message = await prisma.message.findUnique({
      where: { id: messageId },
      include: {
        chat: {
          include: { users: true },
        },
      },
    });

    // 2. Verify user has access to this message
    const hasAccess = message.chat.users.some((u) => u.userId === userId);
    if (!hasAccess) {
      return res.status(403).json({ error: "Access denied" });
    }

    // 3. Update message status
    const updatedMessage = await prisma.message.update({
      where: { id: messageId },
      data: {
        status: "READ",
        readAt: new Date(),
      },
    });

    // 4. Notify other participants in the chat
    const recipientSocketId = onlineUsers.get(message.authorId);
    if (recipientSocketId) {
      io.to(recipientSocketId).emit("message_read", {
        messageId: message.id,
        readAt: updatedMessage.readAt,
      });
    }

    res.json(updatedMessage);
  } catch (error) {
    console.error("Error marking message as read:", error);
    res.status(500).json({ error: "Failed to mark message as read" });
  }
};

export default {
  getChatsForUser,
  updateMessageStatus,
};
