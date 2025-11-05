"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.createVisit = createVisit;
exports.seedVisits = seedVisits;
const client_1 = require("@prisma/client");
const faker_1 = require("@faker-js/faker");
const date_fns_1 = require("date-fns");
const helpers_1 = require("../utils/helpers");
const TENANT_ID = '4';
const BASE_DATE = new Date('2025-11-05T00:00:00Z');
const VISIT_TEMPLATES = [
    { clientName: 'Anne Gibson', postcode: 'NW4', hour: 9, duration: 30, urgency: client_1.RequestUrgency.MEDIUM, requirements: 'Personal Care, Medication Administration', notes: 'Prefers female carer' },
    { clientName: 'Margaret Cole', postcode: 'NW4', hour: 9, duration: 45, urgency: client_1.RequestUrgency.MEDIUM, requirements: 'Personal Care, Dementia Care, Mobility Support', notes: 'Same carer preferred' },
    { clientName: 'Elizabeth Davies', postcode: 'NW4', hour: 11, duration: 60, urgency: client_1.RequestUrgency.HIGH, requirements: 'Personal Care, Hoist Operation, Manual Handling, double handed', notes: 'DOUBLE HANDED', isDoubleHanded: true },
];
async function createVisit(prisma, template) {
    const postcodeData = (0, helpers_1.getPostcodeData)(template.postcode);
    const startTime = new Date(BASE_DATE);
    startTime.setHours(template.hour, 0, 0, 0);
    const endTime = (0, date_fns_1.addMinutes)(startTime, template.duration);
    return prisma.externalRequest.create({
        data: {
            tenantId: TENANT_ID,
            subject: `Care Visit - ${template.clientName}`,
            content: template.notes,
            requestorEmail: `${template.clientName.toLowerCase().replace(/\s+/g, '.')}@client.appbrew.com`,
            requestorName: template.clientName,
            requestorPhone: (0, helpers_1.generatePhoneNumber)(),
            address: `${faker_1.faker.location.streetAddress()}, ${postcodeData.area}`,
            postcode: `${template.postcode} ${faker_1.faker.number.int({ min: 1, max: 9 })}${faker_1.faker.string.alpha(2).toUpperCase()}`,
            latitude: (0, helpers_1.addRandomOffset)(postcodeData.lat),
            longitude: (0, helpers_1.addRandomOffset)(postcodeData.lon),
            urgency: template.urgency,
            status: client_1.RequestStatus.APPROVED,
            requirements: template.requirements,
            estimatedDuration: template.duration,
            scheduledStartTime: startTime,
            scheduledEndTime: endTime,
            notes: template.notes,
            sendToRostering: true
        }
    });
}
async function seedVisits(prisma) {
    console.log('Seeding visits...');
    const visits = await Promise.all(VISIT_TEMPLATES.map(t => createVisit(prisma, t)));
    console.log(`Created ${visits.length} visits`);
    return visits;
}
//# sourceMappingURL=visitFactory.js.map