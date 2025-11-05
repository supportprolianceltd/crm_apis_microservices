// prisma/factories/visitFactory.ts
import { PrismaClient, RequestUrgency, RequestStatus } from '@prisma/client';
import { faker } from '@faker-js/faker';
import { addMinutes } from 'date-fns';
import { POSTCODES } from '../data/postcodes';
import { addRandomOffset, generatePhoneNumber, getPostcodeData } from '../utils/helpers';

const TENANT_ID = '4';
const BASE_DATE = new Date('2025-11-05T00:00:00Z');

interface VisitTemplate {
  clientName: string;
  postcode: keyof typeof POSTCODES;
  hour: number;
  duration: number;
  urgency: RequestUrgency;
  requirements: string;
  notes: string;
  isDoubleHanded?: boolean;
}

const VISIT_TEMPLATES: VisitTemplate[] = [
  // Reuse your original 20+ templates
  { clientName: 'Anne Gibson', postcode: 'NW4', hour: 9, duration: 30, urgency: RequestUrgency.MEDIUM, requirements: 'Personal Care, Medication Administration', notes: 'Prefers female carer' },
  { clientName: 'Margaret Cole', postcode: 'NW4', hour: 9, duration: 45, urgency: RequestUrgency.MEDIUM, requirements: 'Personal Care, Dementia Care, Mobility Support', notes: 'Same carer preferred' },
  { clientName: 'Elizabeth Davies', postcode: 'NW4', hour: 11, duration: 60, urgency: RequestUrgency.HIGH, requirements: 'Personal Care, Hoist Operation, Manual Handling, double handed', notes: 'DOUBLE HANDED', isDoubleHanded: true },
  // ... add all 20
];

export async function createVisit(prisma: PrismaClient, template: VisitTemplate) {
  const postcodeData = getPostcodeData(template.postcode);
  const startTime = new Date(BASE_DATE);
  startTime.setHours(template.hour, 0, 0, 0);
  const endTime = addMinutes(startTime, template.duration);

  return prisma.externalRequest.create({
    data: {
      tenantId: TENANT_ID,
      subject: `Care Visit - ${template.clientName}`,
      content: template.notes,
      requestorEmail: `${template.clientName.toLowerCase().replace(/\s+/g, '.')}@client.appbrew.com`,
      requestorName: template.clientName,
      requestorPhone: generatePhoneNumber(),
      address: `${faker.location.streetAddress()}, ${postcodeData.area}`,
      postcode: `${template.postcode} ${faker.number.int({ min: 1, max: 9 })}${faker.string.alpha(2).toUpperCase()}`,
      latitude: addRandomOffset(postcodeData.lat),
      longitude: addRandomOffset(postcodeData.lon),
      urgency: template.urgency,
      status: RequestStatus.APPROVED,
      requirements: template.requirements,
      estimatedDuration: template.duration,
      scheduledStartTime: startTime,
      scheduledEndTime: endTime,
      notes: template.notes,
      sendToRostering: true
    }
  });
}

export async function seedVisits(prisma: PrismaClient) {
  console.log('Seeding visits...');
  const visits = await Promise.all(VISIT_TEMPLATES.map(t => createVisit(prisma, t)));
  console.log(`Created ${visits.length} visits`);
  return visits;
}