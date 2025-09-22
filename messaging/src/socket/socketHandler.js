// src/socket/socketHandler.js
import { setupSubscribers } from "../subscribers/index.js";

export const initializeSocket = (io) => {
  // Handle connections
  io.on("connection", (socket) => {
    console.log("New WebSocket connection:", socket.id);

    // Set up all subscribers
    const cleanupSubscribers = setupSubscribers(io, socket);

    // Handle disconnection
    socket.on("disconnect", async () => {
      console.log("Client disconnected:", socket.id);
      cleanupSubscribers?.();
    });

    // Handle authentication
    socket.on("authenticate", async ({ token }, callback) => {
      try {
        // Your existing auth logic here
        // ...

        // After successful auth, set up subscribers
        cleanupSubscribers?.();
        setupSubscribers(io, socket);

        // Notify client of successful auth
        socket.emit("authenticated");
        callback?.({ status: "success" });
      } catch (error) {
        console.error("Authentication error:", error);
        callback?.({ status: "error", message: error.message });
        socket.disconnect();
      }
    });
  });
};
