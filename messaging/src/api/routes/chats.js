import express from "express";
import chatsController from "../controllers/chatsController.js";
const router = express.Router();

/**
 * @swagger
 * /api/chats:
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
router.get("/", chatsController.getChatsController);

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
