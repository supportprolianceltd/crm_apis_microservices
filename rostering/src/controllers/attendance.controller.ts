import { Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';

export class AttendanceController {
  private prisma: PrismaClient;

  constructor(prisma: PrismaClient) {
    this.prisma = prisma;
  }

  // List attendance records. Supports optional `date=YYYY-MM-DD` query to filter by day.
  public async listAttendance(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const dateParam = req.query.date as string | undefined;
      let where: any = { tenantId: tenantId.toString() };

      if (dateParam) {
        const d = new Date(dateParam + 'T00:00:00Z');
        if (isNaN(d.getTime())) return res.status(400).json({ error: 'Invalid date param, expected YYYY-MM-DD' });
        const start = d;
        const end = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() + 1));
        // include records that have clockIn or clockOut within the day
        where.AND = [
          { OR: [ { clockInAt: { gte: start, lt: end } }, { clockOutAt: { gte: start, lt: end } } ] }
        ];
      }

      const items = await (this.prisma as any).attendance.findMany({ where, orderBy: { clockInAt: 'asc' } });

      // Map to frontend-friendly rows and enrich with carerVisit.clockOutNote as remark when available.
      const rows = await Promise.all(items.map(async (it: any, idx: number) => {
        const clockInTime = it.clockInAt ? new Date(it.clockInAt) : null;
        const clockOutTime = it.clockOutAt ? new Date(it.clockOutAt) : null;
        let remark: string | null = null;

        // Prefer explicit carerVisitId link on attendance to fetch the visit note
        if (it.carerVisitId) {
          try {
            const visit = await (this.prisma as any).carerVisit.findUnique({ where: { id: it.carerVisitId }, select: { clockOutNote: true, tenantId: true } });
            if (visit && visit.clockOutNote) remark = visit.clockOutNote;
          } catch (e) {
            // ignore lookup errors and fall back to day-based lookup below
            console.error('Failed to fetch carerVisit by id for attendance enrichment', e);
          }
        }

        // Fallback: if no explicit visit link or note missing, try to find a same-day visit for this carer and use its clockOutNote
        if (!remark) {
          const ref = clockOutTime ?? clockInTime;
          if (ref) {
            const dayStart = new Date(Date.UTC(ref.getUTCFullYear(), ref.getUTCMonth(), ref.getUTCDate(), 0, 0, 0, 0));
            const dayEnd = new Date(dayStart);
            dayEnd.setUTCDate(dayStart.getUTCDate() + 1);

            try {
              const visit = await (this.prisma as any).carerVisit.findFirst({
                where: {
                  tenantId: tenantId.toString(),
                  carerId: it.staffId,
                  clockOutAt: { gte: dayStart, lt: dayEnd },
                },
                orderBy: { clockOutAt: 'desc' },
                select: { clockOutNote: true },
              });
              if (visit && visit.clockOutNote) remark = visit.clockOutNote;
            } catch (e) {
              console.error('Failed to fetch carerVisit by day for attendance enrichment', e);
            }
          }
        }

        return {
          sn: idx + 1,
          staffId: it.staffId,
          attendanceId: it.id,
          clockInTime: clockInTime ? clockInTime.toISOString() : null,
          clockOutTime: clockOutTime ? clockOutTime.toISOString() : null,
          entryStatus: it.entryStatus ?? null,
          exitStatus: it.exitStatus ?? null,
          remark,
        };
      }));

      return res.json(rows);
    } catch (error: any) {
      console.error('listAttendance error', error);
      return res.status(500).json({ error: 'Failed to fetch attendance', details: error?.message });
    }
  }
}

export default AttendanceController;
