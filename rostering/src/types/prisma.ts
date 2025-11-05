// Temporary type definitions until Prisma client is properly set up
//C:\Users\CPT-003\Desktop\CRM\crm_apis_microservices\rostering\src\types\prisma.ts
export type PrismaClient = any;

export enum RequestStatus {
  APPROVED = 'APPROVED',
  PENDING = 'PENDING',
  PROCESSING = 'PROCESSING',
  MATCHED = 'MATCHED'
}

export interface ExternalRequest {
  id: string;
  tenantId: string;
  scheduledStartTime: Date | null;
  scheduledEndTime: Date | null;
  requirements: string | null;
  latitude: number | null;
  longitude: number | null;
  postcode: string | null;
  estimatedDuration: number | null;
  status: RequestStatus;
  matches?: {
    response: string;
    carerId: string;
  }[];
}

