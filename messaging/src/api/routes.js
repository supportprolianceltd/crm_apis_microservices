import { Router } from "express";
import prisma from "../config/prisma.js";
import chatsRouter from "./routes/chats.js";
import messagesRouter from "./routes/messages.js";
const apiRouter = Router();

apiRouter.use("/", chatsRouter);
apiRouter.use("/messages", messagesRouter);

/**
 * @swagger
 * /api/messaging/users:
 *   get:
 *     summary: Get all users from auth service with pagination support
 *     tags: [Users]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: query
 *         name: page
 *         schema:
 *           type: integer
 *           default: 1
 *         description: Page number for pagination
 *       - in: query
 *         name: page_size
 *         schema:
 *           type: integer
 *           default: 50
 *         description: Number of users per page (max 100)
 *       - in: query
 *         name: search
 *         schema:
 *           type: string
 *         description: Search term for filtering users by name or email
 *     responses:
 *       200:
 *         description: Paginated list of users from auth service
 *       401:
 *         description: Unauthorized
 *       500:
 *         description: Server error
 */
apiRouter.get("/users", async (req, res) => {
  try {
    const { page = 1, page_size = 50, search } = req.query;
    const authServiceUrl = process.env.AUTH_SERVICE_URL || 'http://localhost:9090/api/auth_service';

    // Build query parameters
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: Math.min(parseInt(page_size, 10) || 50, 100).toString(), // Max 100 per page
    });

    if (search) {
      params.append('search', search);
    }

    const response = await fetch(`${authServiceUrl}/api/user/users/?${params.toString()}`, {
      headers: {
        'Authorization': req.headers.authorization,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Auth service returned ${response.status}`);
    }

    const data = await response.json();

    // Transform the response to include only the fields we need for messaging
    const transformedData = {
      count: data.count,
      next: data.next,
      previous: data.previous,
      results: data.results.map(user => ({
        id: user.id,
        username: user.username,
        email: user.email,
        first_name: user.first_name,
        last_name: user.last_name,
        role: user.role,
        job_role: user.job_role,
        tenant: user.tenant,
        status: user.status,
        online: false, // Default to offline, will be updated by presence system
        createdAt: user.createdAt || new Date().toISOString(),
        updatedAt: user.updatedAt || new Date().toISOString()
      }))
    };

    res.json(transformedData);
  } catch (error) {
    console.error('Error fetching users from auth service:', error);
    res.status(500).json({
      status: 'error',
      message: 'Failed to fetch users',
      error: process.env.NODE_ENV === 'development' ? error.message : undefined
    });
  }
});

/**
 * @swagger
 * /api/messaging/chats:
 *   get:
 *     summary: Get all chats for the authenticated user
 *     tags: [Chats]
 *     security:
 *       - bearerAuth: []
 *     responses:
 *       200:
 *         description: List of user's chats
 *       401:
 *         description: Unauthorized
 *       500:
 *         description: Server error
 */
apiRouter.get("/chats", async (req, res) => {
  try {
    const userId = req.user.id;
    const tenantId = req.tenant?.id;

    const chats = await prisma.chat.findMany({
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
        messages: {
          orderBy: {
            createdAt: 'desc',
          },
          take: 1, // Get latest message
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

    // Format the response
    const formattedChats = chats.map((chat) => {
      const otherParticipants = chat.users
        .filter((p) => p.userId !== userId)
        .map((p) => p.user);

      return {
        id: chat.id,
        name:
          chat.name ||
          otherParticipants
            .map(
              (u) =>
                u.username || `${u.firstName} ${u.lastName}`.trim() || u.email
            )
            .join(", "),
        type: chat.type || "DIRECT",
        unreadCount:
          chat.users.find((u) => u.userId === userId)?.unreadCount || 0,
        participants: chat.users.map((u) => u.user),
        lastMessage: chat.messages[0] || null,
        updatedAt: chat.updatedAt,
      };
    });

    res.json({ status: "success", data: formattedChats });
  } catch (error) {
    console.error('Error in getChats:', error);
    res.status(500).json({
      status: 'error',
      message: 'Failed to fetch chats',
      error: process.env.NODE_ENV === 'development' ? error.message : undefined
    });
  }
});

/**
 * @swagger
 * /api/messaging/messages/{chatId}:
 *   get:
 *     summary: Get messages for a specific chat with pagination
 *     tags: [Messages]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: chatId
 *         required: true
 *         schema:
 *           type: string
 *         description: Chat ID
 *       - in: query
 *         name: limit
 *         schema:
 *           type: integer
 *           default: 50
 *         description: Number of messages to return (max 100)
 *       - in: query
 *         name: offset
 *         schema:
 *           type: integer
 *           default: 0
 *         description: Number of messages to skip
 *       - in: query
 *         name: before
 *         schema:
 *           type: string
 *           format: date-time
 *         description: Get messages before this timestamp
 *     responses:
 *       200:
 *         description: Paginated list of messages in the chat
 *       401:
 *         description: Unauthorized
 *       403:
 *         description: Access denied to chat
 *       500:
 *         description: Server error
 */
apiRouter.get("/messages/:chatId", async (req, res) => {
  try {
    const { chatId } = req.params;
    const { limit = 50, offset = 0, before } = req.query;
    const userId = req.user.id;

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
      return res.status(403).json({
        status: "error",
        message: "Chat not found or access denied"
      });
    }

    // Set default pagination values
    const paginationOptions = {
      limit: Math.min(parseInt(limit, 10) || 50, 100), // Max 100
      offset: Math.max(parseInt(offset, 10) || 0, 0),
      before: before || null,
    };

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
      take: paginationOptions.limit,
      skip: paginationOptions.offset,
    });

    const total = await prisma.message.count({ where: { chatId } });

    res.json({
      status: "success",
      data: {
        messages: messages.reverse(), // Return in chronological order
        hasMore: messages.length === paginationOptions.limit,
        total,
        limit: paginationOptions.limit,
        offset: paginationOptions.offset,
      },
    });
  } catch (error) {
    console.error('Error in getMessages:', error);
    res.status(500).json({
      status: 'error',
      message: 'Failed to fetch messages',
      error: process.env.NODE_ENV === 'development' ? error.message : undefined
    });
  }
});

export default apiRouter;
