const express = require("express");
const chatsController = require("../controllers/chatsController");

const router = express.Router();

// GET /api/v1/chats/:tenantId/:userId
router.get("/:tenantId/:userId", chatsController.getChatsController);
router.patch(
  "messages/:messageId/read",
  chatsController.updateMessageStatusController
);

module.exports = router;
