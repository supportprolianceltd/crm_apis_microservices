import express from "express";
import http from "http";
import { Server } from "socket.io";
import { config } from "dotenv";
import cors from "cors";
import swaggerDocs from "./config/swagger.js";

// Load environment variables
config();

const app = express();
const server = http.createServer(app);

// CORS configuration
const corsOptions = {
  origin: "*", // Allow all origins for development
  methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
  allowedHeaders: ["Content-Type", "Authorization"],
  credentials: true,
};

// Initialize Socket.IO with CORS
const io = new Server(server, {
  cors: {
    origin: "*",
    methods: ["GET", "POST"],
  },
});

const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors(corsOptions));
app.use(express.json());
app.use(express.static("public"));

// API Documentation
swaggerDocs(app);

// Basic route
app.get("/", (req, res) => {
  res.redirect("/api-docs");
});

// API Routes
import apiRoutes from "./api/routes.js";
app.use("/api/v1", apiRoutes);

// Initialize WebSocket
import initializeSocket from "./socket/socketHandler.js";
initializeSocket(io);

// Error handling middleware
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({
    success: false,
    message: "Internal Server Error",
    error: process.env.NODE_ENV === "development" ? err.message : {},
  });
});

// Start server
server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
