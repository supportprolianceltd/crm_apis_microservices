export interface LocationInput {
  address?: string;
  postcode?: string;
  latitude?: number;
  longitude?: number;
}

export interface TravelCalculationRequest {
  from: LocationInput;
  to: LocationInput;
  mode?: 'driving' | 'walking' | 'transit' | 'bicycling';
  forceRefresh?: boolean;
}

export interface CoordinatesData {
  latitude: number;
  longitude: number;
}

export interface LocationData {
  address?: string;
  postcode?: string;
  geocoded?: string;
  coordinates: CoordinatesData;
}

export interface DistanceData {
  meters: number;
  kilometers: number;
  text: string;
}

export interface DurationData {
  seconds: number;
  minutes: number;
  text: string;
}

export interface WarningData {
  type: string;
  message: string;
  severity: 'info' | 'warning' | 'error';
}

export interface TravelCalculationResponse {
  distance: DistanceData;
  duration: DurationData;
  trafficDuration?: DurationData;
  from: LocationData;
  to: LocationData;
  mode: string;
  precisionLevel: 'COORDINATES' | 'ADDRESS' | 'POSTCODE';
  cached: boolean;
  calculatedAt: Date;
  expiresAt: Date;
  warnings: WarningData[];
}

export enum PrecisionLevel {
  COORDINATES = 'COORDINATES',
  ADDRESS = 'ADDRESS',
  POSTCODE = 'POSTCODE'
}

export interface GoogleDistanceMatrixResponse {
  destination_addresses: string[];
  origin_addresses: string[];
  rows: Array<{
    elements: Array<{
      distance: {
        text: string;
        value: number;
      };
      duration: {
        text: string;
        value: number;
      };
      duration_in_traffic?: {
        text: string;
        value: number;
      };
      status: string;
    }>;
  }>;
  status: string;
  error_message?: string;
}

export interface CachedTravelData {
  distanceMeters: number;
  durationSeconds: number;
  trafficDurationSeconds?: number;
  fromLatitude: number;
  fromLongitude: number;
  toLatitude: number;
  toLongitude: number;
  fromAddress?: string;
  toAddress?: string;
  fromPostcode: string;
  toPostcode: string;
  precisionLevel: PrecisionLevel;
  calculatedAt: Date;
  expiresAt: Date;
}