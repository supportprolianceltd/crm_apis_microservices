// utils/request-search.ts

/**
 * Parse a request ID to extract components
 */
export function parseRequestId(id: string): {
  prefix: string;
  date: string;
  code: string;
  year?: number;
  month?: number;
  day?: number;
} | null {
  const match = id.match(/^REQ-(\d{8})-([A-Z0-9]{5})$/);
  if (!match) return null;

  const dateStr = match[1];
  const year = parseInt(dateStr.substring(0, 4));
  const month = parseInt(dateStr.substring(4, 6));
  const day = parseInt(dateStr.substring(6, 8));

  return {
    prefix: 'REQ',
    date: dateStr,
    code: match[2],
    year,
    month,
    day
  };
}

/**
 * Build a WHERE clause for searching requests by date pattern
 */
export function buildDatePatternWhere(date: Date | string): { id: { startsWith: string } } {
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  const year = dateObj.getFullYear();
  const month = String(dateObj.getMonth() + 1).padStart(2, '0');
  const day = String(dateObj.getDate()).padStart(2, '0');
  const dateStr = `${year}${month}${day}`;

  return {
    id: {
      startsWith: `REQ-${dateStr}-`
    }
  };
}

/**
 * Build WHERE clause for date range search
 */
export function buildDateRangeWhere(
  startDate: Date | string,
  endDate: Date | string
): { id: { gte: string; lte: string } } {
  const start = typeof startDate === 'string' ? new Date(startDate) : startDate;
  const end = typeof endDate === 'string' ? new Date(endDate) : endDate;

  const startYear = start.getFullYear();
  const startMonth = String(start.getMonth() + 1).padStart(2, '0');
  const startDay = String(start.getDate()).padStart(2, '0');
  const startStr = `${startYear}${startMonth}${startDay}`;

  const endYear = end.getFullYear();
  const endMonth = String(end.getMonth() + 1).padStart(2, '0');
  const endDay = String(end.getDate()).padStart(2, '0');
  const endStr = `${endYear}${endMonth}${endDay}`;

  return {
    id: {
      gte: `REQ-${startStr}-00000`,
      lte: `REQ-${endStr}-ZZZZZ`
    }
  };
}

/**
 * Validate request ID format
 */
export function isValidRequestId(id: string): boolean {
  return /^REQ-\d{8}-[A-Z0-9]{5}$/.test(id);
}

/**
 * Example usage in controller:
 */
export const exampleUsage = `
// Search for requests created on a specific date
const today = new Date();
const requests = await prisma.externalRequest.findMany({
  where: {
    tenantId,
    ...buildDatePatternWhere(today)
  }
});

// Search for requests in a date range
const requests = await prisma.externalRequest.findMany({
  where: {
    tenantId,
    ...buildDateRangeWhere('2025-11-01', '2025-11-30')
  }
});

// Validate before querying
if (!isValidRequestId(req.params.id)) {
  return res.status(400).json({ error: 'Invalid request ID format' });
}

// Parse request ID to get date info
const parsed = parseRequestId('REQ-20251106-9KX4P');
console.log(parsed);
// {
//   prefix: 'REQ',
//   date: '20251106',
//   code: '9KX4P',
//   year: 2025,
//   month: 11,
//   day: 6
// }
`;