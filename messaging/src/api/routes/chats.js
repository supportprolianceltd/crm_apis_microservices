import express from "express";
import prisma from "../../config/prisma.js";
import chatsController from "../controllers/chatsController.js";
const router = express.Router();

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
router.get("/", async (req, res) => {
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
 * /api/chats/direct:
 *   post:
 *     summary: Create or get existing direct chat with another user
 *     tags: [Chats]
 *     security:
 *       - bearerAuth: []
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required:
 *               - participantId
 *             properties:
 *               participantId:
 *                 type: string
 *                 description: ID of the participant to start a chat with
 *     responses:
 *       200:
 *         description: Direct chat found or created successfully
 *       400:
 *         description: Missing participant ID
 *       401:
 *         description: Unauthorized
 *       500:
 *         description: Server error
 */
router.post("/direct", chatsController.getOrCreateDirectChatController);

/**
 * @swagger
 * /api/chats/{chatId}/messages/{messageId}/read:
 *   patch:
 *     summary: Mark messages as read in a chat
 *     tags: [Chats]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: chatId
 *         required: true
 *         schema:
 *           type: string
 *         description: ID of the chat containing the messages
 *       - in: path
 *         name: messageId
 *         required: true
 *         schema:
 *           type: string
 *         description: ID of the message to mark as read
 *     responses:
 *       200:
 *         description: Messages marked as read successfully
 *       400:
 *         description: Missing chat ID or message ID
 *       401:
 *         description: Unauthorized
 *       500:
 *         description: Server error
 */
router.patch(
  "/:chatId/messages/:messageId/read",
  chatsController.markMessagesAsReadController
);

export default router;
