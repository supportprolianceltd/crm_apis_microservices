// server.js - Simple static file server for testing the Socket.IO interface
import express from "express";
import { createServer } from "http";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const app = express();
const server = createServer(app);

// Serve static files from the public directory
app.use(express.static(join(__dirname, "public")));

// Serve the tester HTML file as the default route
app.get("/", (req, res) => {
  res.sendFile(join(__dirname, "public", "tester.html"));
});

// Health check endpoint
app.get("/health", (req, res) => {
  res.json({ status: "ok", timestamp: new Date().toISOString() });
});

const PORT = process.env.TESTER_PORT || 3501;

server.listen(PORT, "0.0.0.0", () => {
  console.log(`🚀 Socket.IO Tester Server running on http://0.0.0.0:${PORT}`);
  console.log(
    `📖 Open http://localhost:${PORT} in your browser to test Socket.IO events`
  );
});
