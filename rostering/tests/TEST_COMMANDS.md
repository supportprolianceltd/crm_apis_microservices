# Test Commands Reference

## 🧪 Running Tests

### Run All Tests
```bash
npm test
```

### Run Specific Test Suite
```bash
# Roster tests
npm test -- roster.integration.test

# Live operations tests
npm test -- live-operations.integration.test

# Disruption tests
npm test -- disruption.integration.test

# Clustering tests (existing)
npm test -- clustering.integration.test
```

### Run Tests in Watch Mode
```bash
npm test -- --watch
```

### Run with Coverage
```bash
npm test -- --coverage
```

### Run Specific Test Case
```bash
npm test -- -t "should generate 3 scenarios"
```

---

## 📁 Test File Locations

```
tests/
├── setup.ts                              # ✅ Already exists
├── setupEnv.ts                           # ✅ Already exists
├── clustering.integration.test.ts        # ✅ Already exists
├── roster.integration.test.ts            # ✅ NEW (provided)
├── live-operations.integration.test.ts   # ✅ NEW (provided)
└── disruption.integration.test.ts        # ✅ NEW (provided)
```

---

## 🔧 Test Configuration

### jest.config.js (Already Correct)
```javascript
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/tests'],
  testMatch: [
    '**/tests/**/*.test.ts',
    '**/tests/**/*.integration.test.ts'
  ],
  transform: {
    '^.+\\.ts$': 'ts-jest',
  },
  collectCoverageFrom: [
    'src/**/*.ts',
    '!src/**/*.d.ts',
  ],
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'lcov', 'html'],
  setupFilesAfterEnv: ['<rootDir>/tests/setup.ts'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
  },
  testTimeout: 30000,
  setupFiles: ['<rootDir>/tests/setupEnv.ts'],
};
```

---

## ✅ Adding New Tests

### Step 1: Create Test File
```bash
# In tests/ directory
touch tests/my-feature.integration.test.ts
```

### Step 2: Copy Test Template
```typescript
import { PrismaClient } from '@prisma/client';
import { MyService } from '../src/services/my-service';

describe('My Feature Integration Tests', () => {
  let prisma: PrismaClient;
  let myService: MyService;
  let tenantId: string;

  beforeAll(async () => {
    prisma = new PrismaClient();
    await prisma.$connect();
    myService = new MyService(prisma);
    tenantId = `test-${Date.now()}`;
  });

  afterAll(async () => {
    await prisma.externalRequest.deleteMany({ where: { tenantId } });
    await prisma.$disconnect();
  });

  beforeEach(async () => {
    // Create test data
  });

  afterEach(async () => {
    // Cleanup
  });

  it('should do something', async () => {
    // Test logic
    expect(true).toBe(true);
  });
});
```

### Step 3: Run Test
```bash
npm test -- my-feature.integration.test
```

---

## 🐛 Debugging Tests

### Run Single Test with Verbose Output
```bash
npm test -- -t "specific test name" --verbose
```

### Run with Node Debugger
```bash
node --inspect-brk node_modules/.bin/jest --runInBand tests/roster.integration.test.ts
```

### Check Test Database
```bash
# Open Prisma Studio
npx prisma studio

# Check if test data exists
# Look for tenants starting with "test-"
```

### Clear Jest Cache
```bash
npm test -- --clearCache
```

---

## 📊 Coverage Reports

### Generate HTML Coverage
```bash
npm test -- --coverage --coverageReporters=html
```

### View Coverage
```bash
# Open in browser
open coverage/index.html
```

### Coverage Targets
- Statements: > 80%
- Branches: > 75%
- Functions: > 80%
- Lines: > 80%

---

## 🔍 Test Structure

### Good Test Structure
```typescript
describe('Feature Name', () => {
  describe('Sub-feature', () => {
    it('should do expected behavior', async () => {
      // Arrange - Setup
      const input = createTestData();
      
      // Act - Execute
      const result = await service.method(input);
      
      // Assert - Verify
      expect(result).toBeDefined();
      expect(result.property).toBe(expectedValue);
    });
  });
});
```

### Test Naming Convention
```typescript
// ✅ Good names
it('should generate 3 scenarios with different strategies')
it('should handle empty visits gracefully')
it('should throw error when no carers available')

// ❌ Bad names
it('test1')
it('works')
it('should do stuff')
```

---

## 📝 Test Checklist

Before committing tests:
- [ ] All tests pass
- [ ] No console errors
- [ ] Test cleanup runs properly
- [ ] Test data uses unique IDs
- [ ] No hardcoded values
- [ ] Descriptive test names
- [ ] Coverage > 80%

---

## 🚨 Common Issues

### Issue: "Cannot find module"
**Solution:**
```bash
npm install
npx prisma generate
```

### Issue: "Database connection failed"
**Solution:**
Check `.env` has correct `DATABASE_URL`

### Issue: "Test timeout"
**Solution:**
Increase timeout in test:
```typescript
it('should...', async () => {
  // test
}, 60000); // 60 second timeout
```

### Issue: "Cleanup not working"
**Solution:**
Use unique tenant IDs:
```typescript
const tenantId = `test-${Date.now()}`;
```

---

## 📦 Test Dependencies

All already installed:
- ✅ jest
- ✅ ts-jest
- ✅ @types/jest
- ✅ @prisma/client

---

## 🎯 Quick Test Commands

```bash
# Run all tests
npm test

# Watch mode
npm test -- --watch

# Coverage
npm test -- --coverage

# Specific test
npm test -- roster

# Verbose
npm test -- --verbose

# Update snapshots (if using)
npm test -- -u

# Clear cache
npm test -- --clearCache
```

---

**Happy Testing! 🎉**