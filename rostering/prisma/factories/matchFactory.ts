// prisma/factories/matchFactory.ts
import { PrismaClient, MatchStatus, MatchResponse } from '@prisma/client';

const TENANT_ID = '4';

export async function createHistoricalMatch(
  prisma: PrismaClient,
  visit: any,
  carer: any,
  response: MatchResponse
) {
  const distance = Math.sqrt(
    Math.pow((visit.latitude - carer.latitude) * 111000, 2) +
    Math.pow((visit.longitude - carer.longitude) * 85000, 2)
  );

  await prisma.requestCarerMatch.upsert({
    where: {
      tenantId_requestId_carerId: {
        tenantId: TENANT_ID,
        requestId: visit.id,
        carerId: carer.id
      }
    },
    update: {},
    create: {
      tenantId: TENANT_ID,
      requestId: visit.id,
      carerId: carer.id,
      distance,
      matchScore: 0.85 + Math.random() * 0.15,
      status: MatchStatus.SENT,
      response,
      respondedAt: response === MatchResponse.ACCEPTED ? new Date() : null,
      notificationSent: true
    }
  });
}