import { PrismaClient } from '@prisma/client';
import { POSTCODES } from '../data/postcodes';
export interface CarerOverrides {
    firstName?: string;
    lastName?: string;
    postcode?: keyof typeof POSTCODES;
    skills?: string[];
    experience?: number;
}
export declare function createCarer(prisma: PrismaClient, overrides?: CarerOverrides): Promise<{
    id: string;
    latitude: number | null;
    longitude: number | null;
    tenantId: string;
    createdAt: Date;
    updatedAt: Date;
    address: string;
    postcode: string;
    clusterId: string | null;
    email: string;
    firstName: string;
    lastName: string;
    phone: string | null;
    country: string | null;
    isActive: boolean;
    maxTravelDistance: number;
    availabilityHours: import("@prisma/client/runtime/library").JsonValue | null;
    skills: string[];
    languages: string[];
    qualification: string | null;
    experience: number | null;
    hourlyRate: number | null;
    authUserId: string | null;
}>;
//# sourceMappingURL=carerFactory.d.ts.map