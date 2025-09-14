import chatService from "../../services/chatService.js";

const getChatsController = async (req, res) => {
  try {
    const { tenantId, userId } = req.params;
    // In a real app, you'd validate the tenantId and userId
    const chats = await chatService.getChatsForUser(userId);
    res.status(200).json(chats);
  } catch (error) {
    res
      .status(500)
      .json({ message: "Error fetching chats", error: error.message });
  }
};

const updateMessageStatusController = async (req, res) => {
  chatService.updateMessageStatus(req.params.messageId, req.body.status);
  res.status(200).json({ message: "Message status updated successfully" });
};

export default { getChatsController, updateMessageStatusController };
