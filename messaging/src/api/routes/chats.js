import express from "express";
import chatsController from "../controllers/chatsController.js";
const router = express.Router();

// GET /api/v1/chats/:tenantId/:userId
router.get("/:tenantId/:userId", chatsController.getChatsController);
router.patch(
  "messages/:messageId/read",
  chatsController.updateMessageStatusController
);

export default router;
