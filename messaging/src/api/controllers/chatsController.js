import { ChatService } from "../../services/chatService.js";

/**
 * @route GET /api/chats
 * @description Get all chats for the authenticated user
 * @access Private
 */
const getChatsController = async (req, res) => {
  try {
    const userId = req.user.id; // From auth middleware
    const tenantId = req.tenant?.id; // From tenant middleware if applicable

    const chats = await ChatService.getChatsForUser(userId, tenantId);
    res.status(200).json({ status: 'success', data: chats });
  } catch (error) {
    console.error('Error in getChatsController:', error);
    res.status(500).json({ 
      status: 'error', 
      message: 'Failed to fetch chats', 
      error: process.env.NODE_ENV === 'development' ? error.message : undefined
    });
  }
};

/**
 * @route POST /api/chats/direct
 * @description Create or get existing direct chat with another user
 * @access Private
 */
const getOrCreateDirectChatController = async (req, res) => {
  try {
    const { participantId } = req.body;
    const userId = req.user.id;
    const tenantId = req.tenant?.id;
    const authToken = req.headers.authorization;

    if (!participantId) {
      return res.status(400).json({
        status: 'error',
        message: 'Participant ID is required'
      });
    }

    const chat = await ChatService.getOrCreateDirectChat(userId, participantId, tenantId, authToken);
    res.status(200).json({ status: 'success', data: chat });
  } catch (error) {
    console.error('Error in getOrCreateDirectChatController:', error);
    res.status(500).json({
      status: 'error',
      message: 'Failed to create or get direct chat',
      error: process.env.NODE_ENV === 'development' ? error.message : undefined
    });
  }
};

/**
 * @route PATCH /api/chats/:chatId/messages/:messageId/read
 * @description Mark messages as read in a chat
 * @access Private
 */
const markMessagesAsReadController = async (req, res) => {
  try {
    const { chatId, messageId } = req.params;
    const userId = req.user.id;

    if (!chatId || !messageId) {
      return res.status(400).json({ 
        status: 'error', 
        message: 'Chat ID and Message ID are required' 
      });
    }

    await ChatService.markMessagesAsRead(chatId, userId, messageId);
    res.status(200).json({ 
      status: 'success', 
      message: 'Messages marked as read' 
    });
  } catch (error) {
    console.error('Error in markMessagesAsReadController:', error);
    res.status(500).json({ 
      status: 'error', 
      message: 'Failed to mark messages as read',
      error: process.env.NODE_ENV === 'development' ? error.message : undefined
    });
  }
};

export default { 
  getChatsController, 
  getOrCreateDirectChatController,
  markMessagesAsReadController 
};
