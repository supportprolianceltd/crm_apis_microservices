import { Router } from "express";
import multer from "multer";
import path from "path";
import prisma from "../../config/prisma.js";
import { ChatService } from "../../services/chatService.js";

const messagesRouter = Router();

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
messagesRouter.get("/:chatId", async (req, res) => {
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

// Configure multer for file uploads
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, 'uploads/'); // Store files in uploads directory
  },
  filename: (req, file, cb) => {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
    cb(null, file.fieldname + '-' + uniqueSuffix + path.extname(file.originalname));
  }
});

const upload = multer({
  storage: storage,
  limits: {
    fileSize: 50 * 1024 * 1024, // 50MB limit
  },
  fileFilter: (req, file, cb) => {
    // Allow images, videos, audio, and documents
    const allowedTypes = [
      'image/jpeg', 'image/png', 'image/gif', 'image/webp',
      'video/mp4', 'video/avi', 'video/mov',
      'audio/mpeg', 'audio/wav', 'audio/ogg',
      'application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'text/plain'
    ];
    if (allowedTypes.includes(file.mimetype)) {
      cb(null, true);
    } else {
      cb(new Error('Invalid file type'), false);
    }
  }
});

// Send a message to a user (by userId)
messagesRouter.post("/send", async (req, res) => {
  try {
    const { recipientId, content } = req.body;
    const senderId = req.user.id;
    const tenantId = req.tenant?.id;
    if (!recipientId || !content) {
      return res.status(400).json({ status: "error", message: "recipientId and content are required" });
    }
    const result = await ChatService.sendMessageToUser(recipientId, senderId, content, tenantId, req);
    res.status(201).json({ status: "success", data: result });
  } catch (error) {
    res.status(500).json({ status: "error", message: error.message });
  }
});

// Send a message to a user (by email)
messagesRouter.post("/send-by-email", async (req, res) => {
  try {
    const { recipientEmail, content } = req.body;
    const senderId = req.user.id;
    const tenantId = req.tenant?.id;
    if (!recipientEmail || !content) {
      return res.status(400).json({ status: "error", message: "recipientEmail and content are required" });
    }
    const result = await ChatService.sendMessageToUserByEmail(recipientEmail, senderId, content, tenantId);
    res.status(201).json({ status: "success", data: result });
  } catch (error) {
    res.status(500).json({ status: "error", message: error.message });
  }
});

// Send a message with file attachment
messagesRouter.post("/send-with-file", upload.single('file'), async (req, res) => {
  try {
    const { recipientId, content } = req.body;
    const senderId = req.user.id;
    const tenantId = req.tenant?.id;

    if (!recipientId) {
      return res.status(400).json({ status: "error", message: "recipientId is required" });
    }

    if (!req.file && !content) {
      return res.status(400).json({ status: "error", message: "Either file or content is required" });
    }

    const result = await ChatService.sendMessageWithFile(recipientId, senderId, content, req.file, tenantId, req);
    res.status(201).json({ status: "success", data: result });
  } catch (error) {
    res.status(500).json({ status: "error", message: error.message });
  }
});

export default messagesRouter;
