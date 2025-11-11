import prisma from "../config/prisma.js";
import { FileStorageService } from "./fileStorageService.js";
import axios from "axios";
import { AUTH_SERVICE_URL } from "../config/config.js";

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

  // Ensure user exists in messaging database, fetch from auth service if needed
  async ensureUserExists(userId, tenantId, authToken = null, userData = null) {
    try {
      // Check if user already exists
      const existingUser = await prisma.user.findUnique({
        where: { id: userId }
      });

      if (existingUser) {
        return existingUser;
      }

      // User doesn't exist, create from JWT data or fetch from auth service
      console.log(`User ${userId} not found in messaging DB, creating from JWT data`);

      try {
        let userInfo = userData;

        // If no userData provided, try to fetch from auth service
        if (!userInfo) {
          const authServiceUrl = process.env.AUTH_SERVICE_URL || 'http://auth-service:8001';
          const headers = {
            'Content-Type': 'application/json',
          };

          // Use auth token if provided
          if (authToken) {
            headers['Authorization'] = authToken;
          }

          try {
            // First try to fetch user by ID
            const response = await axios.get(`${authServiceUrl}/api/user/users/?id=${encodeURIComponent(userId)}`, {
              headers,
              timeout: 5000,
            });

            if (response.data && response.data.results && response.data.results.length > 0) {
              userInfo = response.data.results[0];
            }
          } catch (idError) {
            console.log(`Could not fetch user by ID ${userId}, trying by email`);
            // If that fails, try by email (assuming userId might be email)
            try {
              const response = await axios.get(`${authServiceUrl}/api/user/users/?email=${encodeURIComponent(userId)}`, {
                headers,
                timeout: 5000,
              });

              if (response.data && response.data.results && response.data.results.length > 0) {
                userInfo = response.data.results[0];
              }
            } catch (emailError) {
              console.error("Could not fetch user by email either:", emailError.message);
            }
          }
        }

        if (userInfo) {
          // Create user in messaging database
          const newUser = await prisma.user.create({
            data: {
              id: userInfo.id || userId,
              email: userInfo.email || userId,
              username: userInfo.username || userInfo.email?.split("@")[0] || `user_${userId}`,
              firstName: userInfo.first_name || userInfo.firstName || "",
              lastName: userInfo.last_name || userInfo.lastName || "",
              role: userInfo.role || "user",
              tenantId: tenantId,
            }
          });

          console.log(`Created user ${userId} in messaging database`);
          return newUser;
        } else {
          // Create minimal user from JWT data if available
          if (userData) {
            const newUser = await prisma.user.create({
              data: {
                id: userData.id || userId,
                email: userData.email || userId,
                username: userData.username || userData.email?.split("@")[0] || `user_${userId}`,
                firstName: userData.firstName || "",
                lastName: userData.lastName || "",
                role: userData.role || "user",
                tenantId: tenantId,
              }
            });

            console.log(`Created user ${userId} in messaging database from JWT data`);
            return newUser;
          }

          throw new Error(`User ${userId} not found in auth service and no JWT data provided`);
        }
      } catch (authError) {
        console.error("Could not fetch user from auth service:", authError.message);
        // If we have JWT data, create user anyway
        if (userData) {
          const newUser = await prisma.user.create({
            data: {
              id: userData.id || userId,
              email: userData.email || userId,
              username: userData.username || userData.email?.split("@")[0] || `user_${userId}`,
              firstName: userData.firstName || "",
              lastName: userData.lastName || "",
              role: userData.role || "user",
              tenantId: tenantId,
            }
          });

          console.log(`Created user ${userId} in messaging database from JWT data (fallback)`);
          return newUser;
        }

        throw new Error(`Failed to create user ${userId}`);
      }
    } catch (error) {
      console.error('Error in ensureUserExists:', error);
      throw error;
    }
  },

  // Create or get existing direct chat between two users
  async getOrCreateDirectChat(userId, participantId, tenantId, authToken = null, participantData = null) {
    try {
      // Ensure the participant user exists in the messaging database
      await this.ensureUserExists(participantId, tenantId, authToken, participantData);

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

  // Send message to an existing chat
  async sendMessageToChat(chatId, senderId, content, tenantId, req) {
    try {
      // Verify user has access to the chat
      const userChat = await prisma.usersOnChats.findUnique({
        where: {
          userId_chatId: {
            userId: senderId,
            chatId: chatId
          }
        }
      });

      if (!userChat) {
        throw new Error('Chat not found or access denied');
      }

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

      // Create the message
      const message = await prisma.message.create({
        data: {
          messageId: messageId,
          content: content,
          chatId: chatId,
          authorId: senderId,
          status: 'DELIVERED'
        }
      });

      // Update chat's last message
      await prisma.chat.update({
        where: { id: chatId },
        data: {
          lastMessageId: message.id,
          updatedAt: new Date()
        }
      });

      // Increment unread count for other participants
      await prisma.usersOnChats.updateMany({
        where: {
          chatId: chatId,
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
        // Get all participants except sender
        const participants = await prisma.usersOnChats.findMany({
          where: {
            chatId: chatId,
            userId: {
              not: senderId
            }
          },
          select: {
            userId: true
          }
        });

        // Emit to all participants
        participants.forEach(participant => {
          req.io.to(`user_${participant.userId}`).emit('new_message', {
            chatId: chatId,
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
          id: chatId,
          type: 'DIRECT' // Assuming direct chat for now
        }
      };
    } catch (error) {
      console.error('Error in sendMessageToChat:', error);
      throw new Error('Failed to send message to chat');
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
