const express = require('express');
const chatRoutes = require('./chats');

const router = express.Router();

router.use('/chats', chatRoutes);

module.exports = router;
