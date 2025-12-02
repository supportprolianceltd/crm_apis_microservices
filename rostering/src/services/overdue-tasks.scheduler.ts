import cron from 'node-cron';
import { PrismaClient } from '@prisma/client';

// Scheduler to mark overdue tasks as MISSED.
// Config via env:
// - OVERDUE_CRON (default: '* * * * *')
// - OVERDUE_GRACE_MINUTES (default: 0)
// - OVERDUE_LOCK_KEY (default: 1234567890)

function parseLockKey(): number {
  const v = process.env.OVERDUE_LOCK_KEY || '1234567890';
  const n = parseInt(v, 10);
  return isNaN(n) ? 1234567890 : n;
}

async function tryAcquireAdvisoryLock(prisma: PrismaClient, key: number) {
  try {
    const res: any = await (prisma as any).$queryRaw`SELECT pg_try_advisory_lock(${key}) as locked`;
    // Some Prisma versions return an array with an object, some return object directly
    const locked = Array.isArray(res) ? res[0]?.locked : res?.locked;
    return !!locked;
  } catch (e) {
    console.error('Failed to acquire advisory lock', e);
    return false;
  }
}

async function releaseAdvisoryLock(prisma: PrismaClient, key: number) {
  try {
    await (prisma as any).$queryRaw`SELECT pg_advisory_unlock(${key})`;
  } catch (e) {
    console.error('Failed to release advisory lock', e);
  }
}

export function startOverdueTaskScheduler(prisma: PrismaClient) {
  const schedule = process.env.OVERDUE_CRON || '* * * * *';
  const graceMinutes = parseInt(process.env.OVERDUE_GRACE_MINUTES || '0', 10) || 0;
  const lockKey = parseLockKey();

  cron.schedule(schedule, async () => {
    const gotLock = await tryAcquireAdvisoryLock(prisma, lockKey);
    if (!gotLock) return; // another instance is handling it

    try {
      const now = new Date();
      const cutoff = new Date(now.getTime() - graceMinutes * 60 * 1000);

      // Find candidate tasks to mark MISSED
      const candidates: any[] = await (prisma as any).task.findMany({
        where: {
          dueDate: { lt: cutoff },
          status: { in: ['PENDING', 'IN_PROGRESS'] },
        },
        select: { id: true, tenantId: true, carerVisitId: true, status: true },
      });

      if (!candidates || candidates.length === 0) {
        return;
      }

      // Prepare client_visit_logs entries for candidates that are attached to a visit
      const nowIso = new Date().toISOString();
      const logs = candidates
        .filter((t: any) => t.carerVisitId)
        .map((t: any) => ({
          tenantId: t.tenantId,
          visitId: t.carerVisitId,
          action: 'TASK_MISSED',
          taskId: t.id,
          performedById: 'system',
          details: JSON.stringify({ taskId: t.id, previousStatus: t.status, markedAt: nowIso }),
        }));

      try {
        // Transaction: create logs (if any) and mark tasks MISSED
        const taskIds = candidates.map((t: any) => t.id);
        await (prisma as any).$transaction(async (tx: any) => {
          if (logs.length > 0) {
            try {
              await tx.clientVisitLog.createMany({ data: logs, skipDuplicates: true });
            } catch (e) {
              // fallback to individual creates if createMany not supported
              for (const l of logs) {
                try { await tx.clientVisitLog.create({ data: l }); } catch (err) { /* ignore */ }
              }
            }
          }

          await tx.task.updateMany({ where: { id: { in: taskIds } }, data: { status: 'MISSED' } });
        });

        console.info(`OverdueTaskScheduler: marked ${candidates.length} tasks as MISSED (cutoff=${cutoff.toISOString()}) and wrote ${logs.length} client_visit_logs`);
      } catch (e) {
        console.error('OverdueTaskScheduler transaction error', e);
      }
    } catch (err) {
      console.error('OverdueTaskScheduler error', err);
    } finally {
      await releaseAdvisoryLock(prisma, lockKey);
    }
  });

  console.info('OverdueTaskScheduler started', { schedule, graceMinutes });
}

export default startOverdueTaskScheduler;
