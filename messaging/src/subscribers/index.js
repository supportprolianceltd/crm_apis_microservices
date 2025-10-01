// src/subscribers/index.js
import { setupChatSubscribers } from "./chat.subscriber.js";
import { setupMessageSubscribers } from "./message.subscriber.js";
import { setupPresenceSubscribers } from "./presence.subscriber.js";

export const setupSubscribers = (io, socket) => {
  console.log("🔧 Setting up subscribers for socket:", socket.id);
  
  // Initialize all subscribers
  console.log("📋 Setting up chat subscribers...");
  const cleanupChatSubscribers = setupChatSubscribers(io, socket);
  console.log("✅ Chat subscribers setup complete");
  
  console.log("💬 Setting up message subscribers...");
  const cleanupMessageSubscribers = setupMessageSubscribers(io, socket);
  console.log("✅ Message subscribers setup complete");
  
  console.log("👥 Setting up presence subscribers...");
  const cleanupPresenceSubscribers = setupPresenceSubscribers(io, socket);
  console.log("✅ Presence subscribers setup complete");

  // Return cleanup function
  return () => {
    cleanupChatSubscribers?.();
    cleanupMessageSubscribers?.();
    cleanupPresenceSubscribers?.();
  };
};
