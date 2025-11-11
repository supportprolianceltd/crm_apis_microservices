import { Router } from "express";
import multer from "multer";
import path from "path";
import prisma from "../../config/prisma.js";
import { ChatService } from "../../services/chatService.js";

const messagesRouter = Router();

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
