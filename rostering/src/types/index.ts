///C:\Users\CPT-003\Desktop\CRM\crm_apis_microservices\rostering\src\types\index.ts
// Database model types
export interface ExternalRequest {
  id: string;
  tenantId: string;
  subject: string;
  content: string;
  requestorEmail: string;
  requestorName?: string | null;
  requestorPhone?: string | null;
  address: string;
  postcode: string;
  location?: any; // PostGIS geography type
  latitude?: number | null;
  longitude?: number | null;
  urgency: RequestUrgency;
  status: RequestStatus;
  requirements?: string;
  requiredSkills: string[];
  estimatedDuration?: number;
  scheduledStartTime?: Date;
  scheduledEndTime?: Date;
  recurrencePattern?: string;
  notes?: string;
  emailMessageId?: string;
  emailThreadId?: string;
  requestTypes?: string;
  createdAt: Date;
  updatedAt: Date;
  processedAt?: Date;
  matches?: RequestCarerMatch[];
}

export interface Carer {
  id: string;
  tenantId: string;
  email: string;
  firstName: string;
  lastName: string;
  phone?: string | null;
  address: string;
  postcode: string;
  location?: any; // PostGIS geography type
  latitude?: number | null;
  longitude?: number | null;
  isActive: boolean;
  maxTravelDistance: number;
  availabilityHours?: any; // JSON
  skills: string[];
  languages: string[];
  qualification?: string;
  experience?: number;
  hourlyRate?: number;
  createdAt: Date;
  updatedAt: Date;
  matches?: RequestCarerMatch[];
}

export interface RequestCarerMatch {
  id: string;
  tenantId: string;
  requestId: string;
  carerId: string;
  distance: number;
  matchScore: number;
  status: MatchStatus;
  respondedAt?: Date;
  response?: MatchResponse;
  responseNotes?: string;
  createdAt: Date;
  updatedAt: Date;
  request?: ExternalRequest;
  carer?: Carer;
}

export interface GeocodingResult {
  latitude: number;
  longitude: number;
  confidence?: number;
  address?: string;
  source: string;
}

// Enums
export enum RequestUrgency {
  LOW = 'LOW',
  MEDIUM = 'MEDIUM',
  HIGH = 'HIGH',
  URGENT = 'URGENT'
}

export enum RequestStatus {
  PENDING = 'PENDING',
  PROCESSING = 'PROCESSING',
  MATCHED = 'MATCHED',
  ASSIGNED = 'ASSIGNED',
  COMPLETED = 'COMPLETED',
  CANCELLED = 'CANCELLED',
  FAILED = 'FAILED'
}

export enum MatchStatus {
  PENDING = 'PENDING',
  SENT = 'SENT',
  OPENED = 'OPENED',
  ACCEPTED = 'ACCEPTED',
  DECLINED = 'DECLINED',
  EXPIRED = 'EXPIRED',
  CANCELLED = 'CANCELLED'
}

export enum MatchResponse {
  ACCEPTED = 'ACCEPTED',
  DECLINED = 'DECLINED',
  INTERESTED = 'INTERESTED'
}

export enum ProcessingStatus {
  SUCCESS = 'SUCCESS',
  FAILED = 'FAILED',
  DUPLICATE = 'DUPLICATE',
  INVALID_FORMAT = 'INVALID_FORMAT',
  GEOCODING_FAILED = 'GEOCODING_FAILED'
}

// Service interfaces
export interface EmailConfig {
  host: string;
  port: number;
  secure: boolean;
  user: string;
  pass: string;
}

export interface ParsedEmail {
  messageId: string;
  threadId?: string;
  subject: string;
  from: string;
  content: string;
  date: Date;
  attachments?: any[];
}

export interface ExtractedRequest {
  requestorEmail: string;
  requestorName?: string;
  requestorPhone?: string;
  address?: string;
  postcode?: string;
  urgency: RequestUrgency;
  requirements?: string;
  requiredSkills?: string[];
  estimatedDuration?: number;
  scheduledStartTime?: Date;
  scheduledEndTime?: Date;
  recurrencePattern?: string;
  notes?: string;
}

export interface MatchingCriteria {
  maxDistance?: number;
  requiredSkills?: string[];
  preferredLanguages?: string[];
  availabilityRequired?: boolean;
  urgencyBoost?: number;
}

export interface MatchResult {
  carer: Carer;
  distance: number;
  matchScore: number;
  reasoning: string[];
}

// API Request/Response types
export interface CreateRequestPayload {
  subject: string;
  content: string;
  requestorEmail: string;
  requestorName?: string;
  requestorPhone?: string;
  address: string;
  postcode?: string;
  urgency?: RequestUrgency;
  requirements?: string;
  requiredSkills?: string[];
  estimatedDuration?: number;
  scheduledStartTime?: string;
  scheduledEndTime?: string;
  recurrencePattern?: string;
  notes?: string;
  requestTypes?: string;
}

export interface UpdateRequestPayload {
  subject?: string;
  content?: string;
  requestorName?: string;
  requestorPhone?: string;
  address?: string;
  postcode?: string;
  urgency?: RequestUrgency;
  status?: RequestStatus;
  requirements?: string;
  requiredSkills?: string[];
  estimatedDuration?: number;
  scheduledStartTime?: string;
  scheduledEndTime?: string;
  recurrencePattern?: string;
  notes?: string;
  requestTypes?: string;
}

export interface CreateCarerPayload {
  email: string;
  firstName: string;
  lastName: string;
  phone?: string | null;
  address: string;
  postcode?: string;
  maxTravelDistance?: number;
  availabilityHours?: any;
  skills?: string[];
  languages?: string[];
  qualification?: string;
  experience?: number;
  hourlyRate?: number;
}

export interface SearchCarersQuery {
  postcode?: string;
  skills?: string[];
  languages?: string[];
  maxDistance?: number;
  isActive?: boolean;
  page?: number;
  limit?: number;
}

export interface SearchRequestsQuery {
  status?: RequestStatus;
  urgency?: RequestUrgency;
  postcode?: string;
  dateFrom?: string;
  dateTo?: string;
  requestorEmail?: string;
  page?: number;
  limit?: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    pages: number;
    hasNext: boolean;
    hasPrev: boolean;
  };
}

// Error types
export interface ServiceError extends Error {
  code?: string;
  statusCode?: number;
  details?: any;
}

export interface ValidationError extends Error {
  field: string;
  value: any;
  constraint: string;
}

