import { Router } from "express";
import prisma from "../config/prisma.js";
import { ChatService } from "../services/chatService.js";

const messagesRouter = Router();

// Send a message to a user (by userId)
messagesRouter.post("/send", async (req, res) => {
  try {
    const { recipientId, content } = req.body;
    const senderId = req.user.id;
    const tenantId = req.tenant?.id;
    if (!recipientId || !content) {
      return res.status(400).json({ status: "error", message: "recipientId and content are required" });
    }
    const result = await ChatService.sendMessageToUser(recipientId, senderId, content, tenantId);
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

export default messagesRouter;
