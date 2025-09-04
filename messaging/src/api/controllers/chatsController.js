const chatService = require('../../services/chatService');

const getChats = async (req, res) => {
  try {
    const { tenantId, userId } = req.params;
    // In a real app, you'd validate the tenantId and userId
    const chats = await chatService.getChatsForUser(userId);
    res.status(200).json(chats);
  } catch (error) {
    res.status(500).json({ message: 'Error fetching chats', error: error.message });
  }
};

module.exports = { getChats };
