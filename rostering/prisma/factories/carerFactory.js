"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.createCarer = createCarer;
const faker_1 = require("@faker-js/faker");
const postcodes_1 = require("../data/postcodes");
const helpers_1 = require("../utils/helpers");
const TENANT_ID = '4';
async function createCarer(prisma, overrides = {}) {
    const postcodeKey = overrides.postcode || faker_1.faker.helpers.arrayElement(Object.keys(postcodes_1.POSTCODES));
    const postcodeData = (0, helpers_1.getPostcodeData)(postcodeKey);
    const experience = overrides.experience ?? faker_1.faker.number.int({ min: 1, max: 20 });
    const skills = overrides.skills || (0, helpers_1.getRandomElements)(postcodes_1.SKILLS, faker_1.faker.number.int({ min: 2, max: 5 }));
    const firstName = overrides.firstName || faker_1.faker.person.firstName();
    const lastName = overrides.lastName || faker_1.faker.person.lastName();
    return prisma.carer.create({
        data: {
            tenantId: TENANT_ID,
            email: `${firstName.toLowerCase()}.${lastName.toLowerCase()}@appbrew.com`,
            firstName,
            lastName,
            phone: (0, helpers_1.generatePhoneNumber)(),
            address: `${faker_1.faker.location.streetAddress()} ${postcodeData.area}`,
            postcode: `${postcodeKey} ${faker_1.faker.number.int({ min: 1, max: 9 })}${faker_1.faker.string.alpha(2).toUpperCase()}`,
            country: 'United Kingdom',
            latitude: (0, helpers_1.addRandomOffset)(postcodeData.lat),
            longitude: (0, helpers_1.addRandomOffset)(postcodeData.lon),
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
//# sourceMappingURL=carerFactory.js.map