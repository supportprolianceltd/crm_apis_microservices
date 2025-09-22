// src/subscribers/index.js
import { setupChatSubscribers } from "./chat.subscriber.js";
import { setupMessageSubscribers } from "./message.subscriber.js";
import { setupPresenceSubscribers } from "./presence.subscriber.js";

export const setupSubscribers = (io, socket) => {
  // Initialize all subscribers
  const cleanupChatSubscribers = setupChatSubscribers(io, socket);
  const cleanupMessageSubscribers = setupMessageSubscribers(io, socket);
  const cleanupPresenceSubscribers = setupPresenceSubscribers(io, socket);

  // Return cleanup function
  return () => {
    cleanupChatSubscribers?.();
    cleanupMessageSubscribers?.();
    cleanupPresenceSubscribers?.();
  };
};
