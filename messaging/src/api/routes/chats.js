import express from "express";
import chatsController from "../controllers/chatsController.js";
const router = express.Router();

/**
 * @swagger
 * /chats/{tenantId}/{userId}:
 *   get:
 *     summary: Get all chats for a specific user
 *     tags: [Chats]
 *     parameters:
 *       - in: path
 *         name: tenantId
 *         required: true
 *         schema:
 *           type: string
 *         description: The tenant ID
 *       - in: path
 *         name: userId
 *         required: true
 *         schema:
 *           type: string
 *         description: The user ID
 *     responses:
 *       200:
 *         description: List of chats for the user
 */
router.get("/:tenantId/:userId", chatsController.getChatsController);

/**
 * @swagger
 * /chats/messages/{messageId}/read:
 *   patch:
 *     summary: Mark a message as read
 *     tags: [Messages]
 *     parameters:
 *       - in: path
 *         name: messageId
 *         required: true
 *         schema:
 *           type: string
 *         description: The ID of the message to mark as read
 *     responses:
 *       200:
 *         description: Message status updated successfully
 *       403:
 *         description: Access denied
 *       404:
 *         description: Message not found
 */
router.patch(
  "/messages/:messageId/read",
  chatsController.updateMessageStatusController
);

export default router;
