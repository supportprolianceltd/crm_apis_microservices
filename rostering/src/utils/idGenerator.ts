// utils/id-generator.ts

/**
 * Generates a custom request ID in the format: REQ-YYYYMMDD-XXXXX
 * Example: REQ-20251106-9KX4P
 */
export function generateRequestId(): string {
  const date = new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const dateStr = `${year}${month}${day}`;
  
  // Generate 5-character alphanumeric code (uppercase)
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  let randomCode = '';
  for (let i = 0; i < 5; i++) {
    randomCode += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  
  return `REQ-${dateStr}-${randomCode}`;
}

/**
 * Generates a unique request ID with collision retry
 * @param checkExists - Async function to check if ID already exists
 * @param maxRetries - Maximum number of retry attempts (default: 5)
 */
export async function generateUniqueRequestId(
  checkExists: (id: string) => Promise<boolean>,
  maxRetries: number = 5
): Promise<string> {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    const id = generateRequestId();
    const exists = await checkExists(id);
    
    if (!exists) {
      return id;
    }
    
    // If collision detected, wait a tiny bit and retry
    await new Promise(resolve => setTimeout(resolve, 10));
  }
  
  // Fallback: append timestamp milliseconds if all retries failed
  const baseId = generateRequestId();
  const ms = String(Date.now()).slice(-3);
  return `${baseId}${ms}`;
}