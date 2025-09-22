import prisma from "../config/prisma.js";

export const ChatService = {
  // Get all chats for a user
  async getChatsForUser(userId, tenantId) {
    return prisma.chat.findMany({
      where: {
        users: {
          some: {
            userId,
            leftAt: null,
          },
        },
        ...(tenantId ? { tenantId } : {}),
      },
      include: {
        users: {
          include: {
            user: {
              select: {
                id: true,
                username: true,
                email: true,
                online: true,
                lastSeen: true,
                firstName: true,
                lastName: true,
              },
            },
          },
        },
        lastMessage: true,
        _count: {
          select: {
            messages: {
              where: {
                status: "DELIVERED",
                NOT: {
                  authorId: userId,
                },
              },
            },
          },
        },
      },
      orderBy: {
        updatedAt: "desc",
      },
    });
  },

  // Find or create a direct chat
  async getOrCreateDirectChat(userId, participantId, tenantId) {
    // Check if chat exists
    let chat = await prisma.chat.findFirst({
      where: {
        type: "DIRECT",
        users: {
          every: {
            userId: { in: [userId, participantId] },
            leftAt: null,
          },
        },
        ...(tenantId ? { tenantId } : {}),
      },
      include: {
        users: {
          include: {
            user: {
              select: {
                id: true,
                username: true,
                email: true,
                online: true,
              },
            },
          },
        },
      },
    });

    // Create new chat if it doesn't exist
    if (!chat) {
      const createData = {
        type: "DIRECT",
        users: {
          create: [
            { userId, role: "MEMBER" },
            { userId: participantId, role: "MEMBER" },
          ],
        },
      };

      if (tenantId) {
        createData.tenant = { connect: { id: tenantId } };
      }

      chat = await prisma.chat.create({
        data: createData,
        include: {
          users: {
            include: {
              user: {
                select: {
                  id: true,
                  username: true,
                  email: true,
                  online: true,
                },
              },
            },
          },
        },
      });
    }

    return chat;
  },

  // Send a message
  async sendMessage(chatId, senderId, content) {
    return prisma.$transaction(async (tx) => {
      // Create message
      const message = await tx.message.create({
        data: {
          content,
          chat: { connect: { id: chatId } },
          author: { connect: { id: senderId } },
          status: "DELIVERED",
        },
        include: {
          author: {
            select: {
              id: true,
              username: true,
              email: true,
              firstName: true,
              lastName: true,
            },
          },
        },
      });

      // Update chat's last message
      await tx.chat.update({
        where: { id: chatId },
        data: {
          lastMessage: { connect: { id: message.id } },
          updatedAt: new Date(),
        },
      });

      // Update unread counters for other participants
      await tx.usersOnChats.updateMany({
        where: {
          chatId,
          userId: { not: senderId },
          leftAt: null,
        },
        data: {
          unreadCount: { increment: 1 },
        },
      });

      // Get updated chat with participants
      const updatedChat = await tx.chat.findUnique({
        where: { id: chatId },
        include: {
          users: {
            where: { leftAt: null },
            include: {
              user: {
                select: {
                  id: true,
                  username: true,
                  email: true,
                  online: true,
                },
              },
            },
          },
        },
      });

      return { message, chat: updatedChat };
    });
  },

  // Mark messages as read
  async markMessagesAsRead(chatId, userId, messageId) {
    return prisma.$transaction([
      // Update message status
      prisma.message.updateMany({
        where: {
          id: messageId,
          chatId,
          authorId: { not: userId },
          status: { not: "READ" },
        },
        data: {
          status: "READ",
          readAt: new Date(),
        },
      }),
      // Reset unread counter
      prisma.usersOnChats.updateMany({
        where: {
          chatId,
          userId,
          leftAt: null,
        },
        data: {
          unreadCount: 0,
        },
      }),
    ]);
  },
};
