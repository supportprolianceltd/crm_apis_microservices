// prisma/factories/carerFactory.ts
import { PrismaClient } from '@prisma/client';
import { faker } from '@faker-js/faker';
import { SKILLS, POSTCODES } from '../data/postcodes';
import { addRandomOffset, getRandomElements, generatePhoneNumber, getPostcodeData } from '../utils/helpers';

const TENANT_ID = '4';

export interface CarerOverrides {
  firstName?: string;
  lastName?: string;
  postcode?: keyof typeof POSTCODES;
  skills?: string[];
  experience?: number;
}

export async function createCarer(prisma: PrismaClient, overrides: CarerOverrides = {}) {
  const postcodeKey = overrides.postcode || faker.helpers.arrayElement(Object.keys(POSTCODES)) as keyof typeof POSTCODES;
  const postcodeData = getPostcodeData(postcodeKey);
  const experience = overrides.experience ?? faker.number.int({ min: 1, max: 20 });
  const skills = overrides.skills || getRandomElements(SKILLS, faker.number.int({ min: 2, max: 5 }));

  const firstName = overrides.firstName || faker.person.firstName();
  const lastName = overrides.lastName || faker.person.lastName();

  return prisma.carer.create({
    data: {
      tenantId: TENANT_ID,
      email: `${firstName.toLowerCase()}.${lastName.toLowerCase()}@appbrew.com`,
      firstName,
      lastName,
      phone: generatePhoneNumber(),
      address: `${faker.location.streetAddress()} ${postcodeData.area}`,
      postcode: `${postcodeKey} ${faker.number.int({ min: 1, max: 9 })}${faker.string.alpha(2).toUpperCase()}`,
      country: 'United Kingdom',
      latitude: addRandomOffset(postcodeData.lat),
      longitude: addRandomOffset(postcodeData.lon),
      isActive: true,
      maxTravelDistance: 10000,
      availabilityHours: {
        monday: [{ start: '08:00', end: '18:00' }],
        tuesday: [{ start: '08:00', end: '18:00' }],
        wednesday: [{ start: '08:00', end: '18:00' }],
        thursday: [{ start: '08:00', end: '18:00' }],
        friday: [{ start: '08:00', end: '18:00' }],
        saturday: [{ start: '09:00', end: '15:00' }],
        sunday: []
      },
      skills,
      languages: ['English'],
      qualification: 'NVQ Level 3 in Health & Social Care',
      experience,
      hourlyRate: 12.50 + (experience * 0.5)
    }
  });
}