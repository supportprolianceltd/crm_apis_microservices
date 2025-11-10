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

  // Create user from auth service if they don't exist locally
  async createUserFromAuthService(userId, tenantId, req = null) {
    try {
      // Check if user already exists
      const existingUser = await prisma.user.findUnique({
        where: { id: userId },
      });

      if (existingUser) {
        return existingUser;
      }

      // Fetch user from auth service using the gateway URL
      const authServiceUrl = process.env.AUTH_SERVICE_URL || 'http://localhost:9090/api/auth_service';
      const response = await fetch(`${authServiceUrl}/api/user/users/${userId}/`, {
        headers: {
          'Authorization': req?.headers?.authorization || `Bearer ${process.env.AUTH_SERVICE_TOKEN || ''}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch user from auth service: ${response.status}`);
      }

      const userData = await response.json();

      // For messaging, we allow cross-tenant communication
      // The tenant validation is handled at the auth level
      console.log(`Creating user ${userId} for tenant ${tenantId} (user's tenant: ${userData.tenant})`);

      // Create user in messaging database with simplified fields
      const newUser = await prisma.user.create({
        data: {
          id: userId,
          email: userData.email,
          username: userData.username,
          firstName: userData.first_name,
          lastName: userData.last_name,
          role: userData.role,
          tenantId: tenantId,
          online: false,
          lastSeen: new Date(),
        },
      });

      return newUser;
    } catch (error) {
      console.error("Error creating user from auth service:", error);
      throw new Error(`Failed to create user: ${error.message}`);
    }
  },

  // Enhanced send message with user creation
  async sendMessageToUser(recipientId, senderId, content, tenantId, req = null) {
    return prisma.$transaction(async (tx) => {
      // Ensure recipient exists (create from auth service if needed)
      let recipient = await tx.user.findUnique({
        where: { id: recipientId },
      });

      if (!recipient) {
        // Try to create user from auth service
        try {
          recipient = await this.createUserFromAuthService(recipientId, tenantId, req);
        } catch (error) {
          throw new Error(`Recipient not found and could not be created: ${error.message}`);
        }
      }

      // Get or create direct chat
      let chat = await tx.chat.findFirst({
        where: {
          type: "DIRECT",
          users: {
            every: {
              userId: { in: [senderId, recipientId].filter(id => id !== undefined && id !== null) },
              leftAt: null,
            },
          },
          ...(tenantId ? { tenantId } : {}),
        },
      });

      if (!chat) {
        chat = await tx.chat.create({
          data: {
            type: "DIRECT",
            tenantId,
            users: {
              create: [
                { userId: senderId, role: "MEMBER" },
                { userId: recipientId, role: "MEMBER" },
              ].filter(user => user.userId !== undefined && user.userId !== null),
            },
          },
        });
      }

      // Create message
      const message = await tx.message.create({
        data: {
          content,
          chatId: chat.id,
          authorId: senderId || req?.user?.id, // Fallback to req.user.id if senderId is undefined
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
        where: { id: chat.id },
        data: {
          lastMessageId: message.id,
          updatedAt: new Date(),
        },
      });

      // Update unread counters for other participants
      await tx.usersOnChats.updateMany({
        where: {
          chatId: chat.id,
          userId: { not: senderId },
          leftAt: null,
        },
        data: {
          unreadCount: { increment: 1 },
        },
      });

      // Get updated chat with participants
      const updatedChat = await tx.chat.findUnique({
        where: { id: chat.id },
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

  // Send message to user by email (for cases where we don't have user ID)
  async sendMessageToUserByEmail(recipientEmail, senderId, content, tenantId) {
    return prisma.$transaction(async (tx) => {
      // Find recipient by email in the same tenant
      let recipient = await tx.user.findFirst({
        where: {
          email: recipientEmail,
          ...(tenantId ? { tenantId } : {}),
        },
      });

      if (!recipient) {
        // Try to create user from auth service by email
        try {
          // First, we need to get the user ID from auth service using email
          const authServiceUrl = process.env.AUTH_SERVICE_URL || 'http://localhost:8000';

          // Search for user by email in auth service using gateway
          const searchResponse = await fetch(`${authServiceUrl}/api/user/users/?search=${encodeURIComponent(recipientEmail)}`, {
            headers: {
              'Authorization': req?.headers?.authorization || `Bearer ${process.env.AUTH_SERVICE_TOKEN || ''}`,
              'Content-Type': 'application/json',
            },
          });

          if (searchResponse.ok) {
            const users = await searchResponse.json();
            if (users.length > 0) {
              const authUser = users[0];
              recipient = await this.createUserFromAuthService(authUser.id, tenantId);
            }
          }

          if (!recipient) {
            throw new Error(`Recipient with email ${recipientEmail} not found`);
          }
        } catch (error) {
          throw new Error(`Recipient not found: ${error.message}`);
        }
      }

      // Use the existing sendMessageToUser logic
      return this.sendMessageToUser(recipient.id, senderId, content, tenantId);
    });
  },

  // Get messages with pagination
  async getMessages(chatId, userId, options = {}) {
    const { limit = 50, offset = 0, before } = options;

    // Verify user has access to chat
    const chat = await prisma.chat.findFirst({
      where: {
        id: chatId,
        users: {
          some: {
            userId,
            leftAt: null,
          },
        },
      },
    });

    if (!chat) {
      throw new Error("Chat not found or access denied");
    }

    const messages = await prisma.message.findMany({
      where: {
        chatId,
        ...(before && { createdAt: { lt: new Date(before) } }),
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
      orderBy: {
        createdAt: "desc",
      },
      take: limit,
      skip: offset,
    });

    return {
      messages: messages.reverse(), // Return in chronological order
      hasMore: messages.length === limit,
      total: await prisma.message.count({ where: { chatId } }),
    };
  },

  // Search messages in a chat
  async searchMessages(chatId, userId, query, options = {}) {
    const { limit = 20, offset = 0 } = options;

    // Verify user has access to chat
    const chat = await prisma.chat.findFirst({
      where: {
        id: chatId,
        users: {
          some: {
            userId,
            leftAt: null,
          },
        },
      },
    });

    if (!chat) {
      throw new Error("Chat not found or access denied");
    }

    const messages = await prisma.message.findMany({
      where: {
        chatId,
        content: {
          contains: query,
          mode: "insensitive",
        },
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
      orderBy: {
        createdAt: "desc",
      },
      take: limit,
      skip: offset,
    });

    return {
      messages: messages.reverse(),
      query,
      hasMore: messages.length === limit,
    };
  },

  // Leave a chat
  async leaveChat(chatId, userId) {
    return prisma.usersOnChats.updateMany({
      where: {
        chatId,
        userId,
        leftAt: null,
      },
      data: {
        leftAt: new Date(),
      },
    });
  },

  // Archive a chat (soft delete for user)
  async archiveChat(chatId, userId) {
    return prisma.usersOnChats.updateMany({
      where: {
        chatId,
        userId,
        leftAt: null,
      },
      data: {
        archivedAt: new Date(),
      },
    });
  },

  // Add reaction to message
  async addReaction(messageId, userId, emoji) {
    // Check if reaction already exists
    const existingReaction = await prisma.messageReaction.findFirst({
      where: {
        messageId,
        userId,
        emoji,
      },
    });

    if (existingReaction) {
      // Remove reaction if it exists (toggle)
      await prisma.messageReaction.delete({
        where: { id: existingReaction.id },
      });
      return { action: "removed", emoji };
    } else {
      // Add new reaction
      await prisma.messageReaction.create({
        data: {
          messageId,
          userId,
          emoji,
        },
      });
      return { action: "added", emoji };
    }
  },

  // Get message reactions
  async getMessageReactions(messageId) {
    const reactions = await prisma.messageReaction.findMany({
      where: { messageId },
      include: {
        user: {
          select: {
            id: true,
            username: true,
            firstName: true,
            lastName: true,
          },
        },
      },
    });

    // Group by emoji
    const groupedReactions = reactions.reduce((acc, reaction) => {
      if (!acc[reaction.emoji]) {
        acc[reaction.emoji] = [];
      }
      acc[reaction.emoji].push(reaction.user);
      return acc;
    }, {});

    return groupedReactions;
  },

  // Edit message (only by author)
  async editMessage(messageId, userId, newContent) {
    const message = await prisma.message.findUnique({
      where: { id: messageId },
    });

    if (!message) {
      throw new Error("Message not found");
    }

    if (message.authorId !== userId) {
      throw new Error("Only message author can edit");
    }

    // Check if message is too old (optional - 24 hours)
    const messageAge = Date.now() - new Date(message.createdAt).getTime();
    const maxEditAge = 24 * 60 * 60 * 1000; // 24 hours

    if (messageAge > maxEditAge) {
      throw new Error("Message too old to edit");
    }

    return prisma.message.update({
      where: { id: messageId },
      data: {
        content: newContent,
        editedAt: new Date(),
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
  },

  // Mark messages as read
  async markMessagesAsRead(chatId, userId, messageIds) {
    return prisma.$transaction(async (tx) => {
      // Convert single messageId to array for consistency
      const messageIdArray = Array.isArray(messageIds) ? messageIds : [messageIds];

      // Verify user has access to chat
      const chat = await tx.chat.findFirst({
        where: {
          id: chatId,
          users: {
            some: {
              userId,
              leftAt: null,
            },
          },
        },
      });

      if (!chat) {
        throw new Error("Chat not found or access denied");
      }

      // Mark messages as read (update read receipts)
      await tx.messageReadReceipt.upsert({
        where: {
          messageId_userId: {
            messageId: messageIdArray[0], // For single message, use first ID
            userId,
          },
        },
        update: {
          readAt: new Date(),
        },
        create: {
          messageId: messageIdArray[0],
          userId,
          readAt: new Date(),
        },
      });

      // Update unread count for the user in this chat
      const unreadCount = await tx.message.count({
        where: {
          chatId,
          status: "DELIVERED",
          NOT: {
            authorId: userId,
          },
          readReceipts: {
            none: {
              userId,
            },
          },
        },
      });

      // Update the user's unread count for this chat
      await tx.usersOnChats.updateMany({
        where: {
          chatId,
          userId,
          leftAt: null,
        },
        data: {
          unreadCount: Math.max(0, unreadCount),
        },
      });

      return { success: true, markedCount: messageIdArray.length };
    });
  },

  // Delete message (soft delete or hard delete)
  async deleteMessage(messageId, userId, hardDelete = false) {
    const message = await prisma.message.findUnique({
      where: { id: messageId },
    });

    if (!message) {
      throw new Error("Message not found");
    }

    if (message.authorId !== userId) {
      throw new Error("Only message author can delete");
    }

    if (hardDelete) {
      // Completely remove message
      await prisma.message.delete({
        where: { id: messageId },
      });
    } else {
      // Soft delete - mark as deleted
      await prisma.message.update({
        where: { id: messageId },
        data: {
          deletedAt: new Date(),
          content: "[Message deleted]",
        },
      });
    }

    return { success: true, hardDelete };
  },
};
