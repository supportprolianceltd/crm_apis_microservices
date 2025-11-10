import prisma from "../config/prisma.js";
import { FileStorageService } from "./fileStorageService.js";

// Function to generate custom ID (for messages and chats)
function generateCustomId(prefix) {
  const date = new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const dateStr = `${year}${month}${day}`;

  // Generate 5-character alphanumeric code (uppercase)
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  let randomCode = '';
  for (let i = 0; i < 5; i++) {
    randomCode += chars.charAt(Math.floor(Math.random() * chars.length));
  }

  return `${prefix}-${dateStr}-${randomCode}`;
}

// Function to generate custom message ID
function generateMessageId() {
  return generateCustomId('MSG');
}

// Function to generate custom chat ID
function generateChatId() {
  return generateCustomId('CHAT');
}

export const ChatService = {
  // Get all chats for a user with participant info and unread counts
  async getChatsForUser(userId, tenantId) {
    try {
      // Get all chats where user is a participant
      const userChats = await prisma.usersOnChats.findMany({
        where: {
          userId: userId,
          leftAt: null, // Only active chats
          chat: {
            tenantId: tenantId
          }
        },
        include: {
          chat: {
            include: {
              users: {
                where: {
                  userId: {
                    not: userId
                  },
                  leftAt: null
                },
                include: {
                  user: {
                    select: {
                      id: true,
                      username: true,
                      email: true,
                      online: true,
                      lastSeen: true,
                      firstName: true,
                      lastName: true
                    }
                  }
                }
              },
              messages: {
                take: 1,
                orderBy: {
                  createdAt: 'desc'
                },
                include: {
                  author: {
                    select: {
                      id: true,
                      username: true,
                      email: true,
                      firstName: true,
                      lastName: true
                    }
                  }
                }
              }
            }
          }
        },
        orderBy: {
          chat: {
            updatedAt: 'desc'
          }
        }
      });

      // Format the response
      const chats = userChats.map(userChat => {
        const chat = userChat.chat;
        const otherParticipant = chat.users[0]?.user;

        return {
          id: chat.id,
          name: otherParticipant ? `${otherParticipant.firstName || ''} ${otherParticipant.lastName || ''}`.trim() || otherParticipant.username || otherParticipant.email : 'Unknown',
          type: chat.type,
          unreadCount: userChat.unreadCount,
          participants: otherParticipant ? [otherParticipant] : [],
          lastMessage: chat.messages[0] ? {
            id: chat.messages[0].id,
            content: chat.messages[0].content,
            createdAt: chat.messages[0].createdAt
          } : null,
          updatedAt: chat.updatedAt
        };
      });

      return chats;
    } catch (error) {
      console.error('Error in getChatsForUser:', error);
      throw new Error('Failed to fetch chats');
    }
  },

  // Create or get existing direct chat between two users
  async getOrCreateDirectChat(userId, participantId, tenantId) {
    try {
      // Check if a direct chat already exists between these users
      const existingChat = await prisma.usersOnChats.findFirst({
        where: {
          userId: userId,
          chat: {
            type: 'DIRECT',
            tenantId: tenantId,
            users: {
              some: {
                userId: participantId,
                leftAt: null
              }
            }
          },
          leftAt: null
        },
        include: {
          chat: {
            include: {
              users: {
                where: {
                  leftAt: null
                },
                include: {
                  user: {
                    select: {
                      id: true,
                      username: true,
                      email: true,
                      firstName: true,
                      lastName: true
                    }
                  }
                }
              }
            }
          }
        }
      });

      if (existingChat) {
        return {
          id: existingChat.chat.id,
          type: existingChat.chat.type,
          createdAt: existingChat.chat.createdAt,
          users: existingChat.chat.users.map(u => ({
            userId: u.userId,
            role: u.role
          }))
        };
      }

      // Create new direct chat
      const chatId = generateChatId();
      const newChat = await prisma.chat.create({
        data: {
          chatId: chatId,
          type: 'DIRECT',
          tenantId: tenantId,
          users: {
            create: [
              { userId: userId },
              { userId: participantId }
            ]
          }
        },
        include: {
          users: true
        }
      });

      return {
        id: newChat.id,
        type: newChat.type,
        createdAt: newChat.createdAt,
        users: newChat.users.map(u => ({
          userId: u.userId,
          role: u.role
        }))
      };
    } catch (error) {
      console.error('Error in getOrCreateDirectChat:', error);
      throw new Error('Failed to create or get direct chat');
    }
  },

  // Mark messages as read in a chat
  async markMessagesAsRead(chatId, userId, messageId) {
    try {
      // Verify user is part of the chat
      const userChat = await prisma.usersOnChats.findUnique({
        where: {
          userId_chatId: {
            userId: userId,
            chatId: chatId
          }
        }
      });

      if (!userChat) {
        throw new Error('Chat not found or access denied');
      }

      // Mark the specific message as read
      await prisma.message.update({
        where: {
          id: messageId,
          chatId: chatId,
          authorId: {
            not: userId // Don't mark own messages as read
          }
        },
        data: {
          status: 'READ',
          readAt: new Date()
        }
      });

      // Update unread count for the user in this chat
      const unreadCount = await prisma.message.count({
        where: {
          chatId: chatId,
          authorId: {
            not: userId
          },
          status: {
            not: 'READ'
          }
        }
      });

      await prisma.usersOnChats.update({
        where: {
          userId_chatId: {
            userId: userId,
            chatId: chatId
          }
        },
        data: {
          unreadCount: unreadCount
        }
      });
    } catch (error) {
      console.error('Error in markMessagesAsRead:', error);
      throw error;
    }
  },

  // Send message to a user (creates chat if doesn't exist)
  async sendMessageToUser(recipientId, senderId, content, tenantId, req) {
    try {
      // Get or create direct chat
      const chat = await this.getOrCreateDirectChat(senderId, recipientId, tenantId);

      // Generate unique message ID
      const messageId = generateMessageId();

      // Get author details from request (from JWT token)
      const authorDetails = req?.user ? {
        id: req.user.id,
        username: req.user.username,
        email: req.user.email,
        firstName: req.user.firstName || "",
        lastName: req.user.lastName || ""
      } : null;

      // Create the message with the custom messageId
      const message = await prisma.message.create({
        data: {
          messageId: messageId,
          content: content,
          chatId: chat.id,
          authorId: senderId,
          status: 'DELIVERED'
        }
      });

      // Update chat's last message
      await prisma.chat.update({
        where: { id: chat.id },
        data: {
          lastMessageId: message.id,
          updatedAt: new Date()
        }
      });

      // Increment unread count for other participants
      await prisma.usersOnChats.updateMany({
        where: {
          chatId: chat.id,
          userId: {
            not: senderId
          }
        },
        data: {
          unreadCount: {
            increment: 1
          }
        }
      });

      // Emit real-time event if socket is available
      if (req && req.io) {
        req.io.to(`user_${recipientId}`).emit('new_message', {
          chatId: chat.id,
          message: {
            id: message.messageId,
            content: message.content,
            type: message.type,
            fileUrl: message.fileUrl,
            fileName: message.fileName,
            fileSize: message.fileSize,
            fileType: message.fileType,
            createdAt: message.createdAt,
            author: authorDetails
          },
          unreadCount: 1
        });
      }

      return {
        message: {
          id: message.messageId,
          content: message.content,
          chatId: message.chatId,
          authorId: message.authorId,
          status: message.status,
          createdAt: message.createdAt,
          author: authorDetails
        },
        chat: {
          id: chat.id,
          type: chat.type
        }
      };
    } catch (error) {
      console.error('Error in sendMessageToUser:', error);
      throw new Error('Failed to send message');
    }
  },

  // Send message to a user by email
  async sendMessageToUserByEmail(recipientEmail, senderId, content, tenantId) {
    try {
      // Find user by email
      const recipient = await prisma.user.findFirst({
        where: {
          email: recipientEmail,
          tenantId: tenantId
        }
      });

      if (!recipient) {
        throw new Error('Recipient not found');
      }

      // Use the existing sendMessageToUser method
      return await this.sendMessageToUser(recipient.id, senderId, content, tenantId);
    } catch (error) {
      console.error('Error in sendMessageToUserByEmail:', error);
      throw error;
    }
  },

  // Send message with file attachment
  async sendMessageWithFile(recipientId, senderId, content, file, tenantId, req) {
    try {
      // Get or create direct chat
      const chat = await this.getOrCreateDirectChat(senderId, recipientId, tenantId);

      // Generate unique message ID
      const messageId = generateMessageId();

      // Get author details from request (from JWT token)
      const authorDetails = req?.user ? {
        id: req.user.id,
        username: req.user.username,
        email: req.user.email,
        firstName: req.user.firstName || "",
        lastName: req.user.lastName || ""
      } : null;

      // Determine message type and file details
      let messageType = 'TEXT';
      let fileUrl = null;
      let fileName = null;
      let fileSize = null;
      let fileType = null;

      if (file) {
        // Upload file to configured storage platform
        const uploadResult = await FileStorageService.uploadFile(file, 'messages');

        fileUrl = uploadResult.url;
        fileName = uploadResult.fileName;
        fileSize = uploadResult.fileSize;
        fileType = uploadResult.fileType;

        // Determine message type based on file mimetype
        if (file.mimetype.startsWith('image/')) {
          messageType = 'IMAGE';
        } else if (file.mimetype.startsWith('video/')) {
          messageType = 'VIDEO';
        } else if (file.mimetype.startsWith('audio/')) {
          messageType = 'AUDIO';
        } else {
          messageType = 'FILE';
        }
      }

      // Create the message with file attachment
      const message = await prisma.message.create({
        data: {
          messageId: messageId,
          content: content || null,
          type: messageType,
          fileUrl: fileUrl,
          fileName: fileName,
          fileSize: fileSize,
          fileType: fileType,
          chatId: chat.id,
          authorId: senderId,
          status: 'DELIVERED'
        }
      });

      // Update chat's last message
      await prisma.chat.update({
        where: { id: chat.id },
        data: {
          lastMessageId: message.id,
          updatedAt: new Date()
        }
      });

      // Increment unread count for other participants
      await prisma.usersOnChats.updateMany({
        where: {
          chatId: chat.id,
          userId: {
            not: senderId
          }
        },
        data: {
          unreadCount: {
            increment: 1
          }
        }
      });

      // Emit real-time event if socket is available
      if (req && req.io) {
        req.io.to(`user_${recipientId}`).emit('new_message', {
          chatId: chat.id,
          message: {
            id: message.messageId,
            content: message.content,
            type: message.type,
            fileUrl: message.fileUrl,
            fileName: message.fileName,
            fileSize: message.fileSize,
            fileType: message.fileType,
            createdAt: message.createdAt,
            author: authorDetails
          },
          unreadCount: 1
        });
      }

      return {
        message: {
          id: message.messageId,
          content: message.content,
          type: message.type,
          fileUrl: message.fileUrl,
          fileName: message.fileName,
          fileSize: message.fileSize,
          fileType: message.fileType,
          chatId: message.chatId,
          authorId: message.authorId,
          status: message.status,
          createdAt: message.createdAt,
          author: authorDetails
        },
        chat: {
          id: chat.id,
          type: chat.type
        }
      };
    } catch (error) {
      console.error('Error in sendMessageWithFile:', error);
      throw new Error('Failed to send message with file');
    }
  }
};
