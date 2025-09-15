import { Router } from "express";
import prisma from "../config/prisma.js";
import chatsRouter from "./routes/chats.js";
const apiRouter = Router();

apiRouter.use("/", chatsRouter);

/**
 * @swagger
 * /api/v1/users:
 *   get:
 *     summary: Get all users
 *     tags: [Users]
 *     responses:
 *       200:
 *         description: List of users
 */
apiRouter.get("/users", async (req, res) => {
  try {
    const users = await prisma.user.findMany();
    res.json(users);
  } catch (error) {
    res.status(500).json({ message: error.message });
  }
});

/**
 * @swagger
 * /api/v1/chats:
 *   get:
 *     summary: Get all chats
 *     tags: [Chats]
 *     responses:
 *       200:
 *         description: List of chats
 */
apiRouter.get("/chats", async (req, res) => {
  try {
    const chats = await prisma.chat.findMany({
      include: {
        users: {
          include: {
            user: true,
          },
        },
        messages: true,
      },
    });
    res.json(chats);
  } catch (error) {
    res.status(500).json({ message: error.message });
  }
});

/**
 * @swagger
 * /api/v1/messages/{chatId}:
 *   get:
 *     summary: Get messages for a specific chat
 *     tags: [Messages]
 *     parameters:
 *       - in: path
 *         name: chatId
 *         required: true
 *         schema:
 *           type: string
 *         description: Chat ID
 *     responses:
 *       200:
 *         description: List of messages in the chat
 */
apiRouter.get("/messages/:chatId", async (req, res) => {
  try {
    const { chatId } = req.params;
    const messages = await prisma.message.findMany({
      where: { chatId },
      include: {
        author: true,
      },
      orderBy: {
        createdAt: "asc",
      },
    });
    res.json(messages);
  } catch (error) {
    res.status(500).json({ message: error.message });
  }
});

export default apiRouter;
