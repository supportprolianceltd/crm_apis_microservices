// tests/setupEnv.ts
import { config } from 'dotenv';

// Load test environment variables
config({ path: '.env.test' });

console.log('🧪 Test environment loaded');
console.log('DATABASE_URL:', process.env.DATABASE_URL ? '✅ Set' : '❌ Missing');