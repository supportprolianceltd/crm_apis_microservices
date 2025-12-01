import { Job } from 'bull';
import { PrismaClient } from '@prisma/client';
import { ClientClusterAssignmentJobData } from '../queues/client-cluster-assignment.queue';
import { ClientClusterAssignmentService } from '../../services/client-cluster-assignment.service';
import { GeocodingEnhancedService } from '../../services/geocoding-enhanced.service';
import { logger } from '../../utils/logger';

const prisma = new PrismaClient();
const geocodingService = new GeocodingEnhancedService(prisma);
const clusterAssignmentService = new ClientClusterAssignmentService(prisma);

export async function processClientClusterAssignment(
  job: Job<ClientClusterAssignmentJobData>
): Promise<any> {
  const { tenantId, clientId, clientName, address, postcode, town, city } = job.data;

  logger.info('Processing client cluster assignment job', {
    jobId: job.id,
    clientId,
    tenantId
  });

  try {
    // STEP 1: Update job progress - Starting
    await job.progress({
      step: 'STARTING',
      percentage: 10,
      message: 'Starting cluster assignment process'
    });

    // STEP 2: Geocode address to get coordinates
    await job.progress({
      step: 'GEOCODING',
      percentage: 30,
      message: 'Getting coordinates from address'
    });

    logger.debug('Geocoding address', { address, postcode });
    
    const geocodeResult = await geocodingService.geocodeAddressWithPostcode(
      address,
      postcode
    );

    if (!geocodeResult) {
      // Try postcode-only geocoding as fallback
      logger.warn('Full address geocoding failed, trying postcode only', { postcode });
      
      const postcodeResult = await geocodingService.geocodePostcodeOnly(postcode);
      
      if (!postcodeResult) {
        throw new Error('Failed to geocode address and postcode');
      }

      // Use postcode coordinates
      await job.progress({
        step: 'GEOCODING',
        percentage: 40,
        message: 'Using postcode coordinates (address geocoding failed)'
      });

      return await performClusterAssignment(
        job,
        tenantId,
        clientId,
        {
          name: clientName,
          address,
          postcode,
          town,
          city,
          latitude: postcodeResult.latitude,
          longitude: postcodeResult.longitude
        }
      );
    }

    // STEP 3: Perform cluster assignment with geocoded coordinates
    await job.progress({
      step: 'GEOCODING_COMPLETE',
      percentage: 50,
      message: `Geocoded successfully: ${geocodeResult.formattedAddress}`
    });

    logger.info('Geocoding successful', {
      latitude: geocodeResult.latitude,
      longitude: geocodeResult.longitude,
      formattedAddress: geocodeResult.formattedAddress
    });

    return await performClusterAssignment(
      job,
      tenantId,
      clientId,
      {
        name: clientName,
        address,
        postcode,
        town: town || geocodeResult.addressComponents.town,
        city: city || geocodeResult.addressComponents.city,
        latitude: geocodeResult.latitude,
        longitude: geocodeResult.longitude
      }
    );

  } catch (error: any) {
    logger.error('Job processing failed', {
      jobId: job.id,
      clientId,
      error: error.message,
      stack: error.stack
    });

    // Update job with error details
    await job.progress({
      step: 'FAILED',
      percentage: 0,
      message: `Error: ${error.message}`
    });

    throw error; // Re-throw to mark job as failed
  }
}

/**
 * Perform the actual cluster assignment
 */
async function performClusterAssignment(
  job: Job<ClientClusterAssignmentJobData>,
  tenantId: string,
  clientId: string,
  clientDetails: {
    name: string;
    address: string;
    postcode: string;
    town?: string;
    city?: string;
    latitude: number;
    longitude: number;
  }
) {
  await job.progress({
    step: 'ASSIGNING',
    percentage: 60,
    message: 'Finding appropriate cluster'
  });

  const result = await clusterAssignmentService.assignClientToCluster(
    tenantId,
    clientId,
    clientDetails
  );

  await job.progress({
    step: 'COMPLETED',
    percentage: 100,
    message: result.message
  });

  logger.info('Cluster assignment completed', {
    jobId: job.id,
    clientId,
    clusterId: result.clusterId,
    clusterName: result.clusterName,
    assignmentType: result.assignmentType
  });

  return {
    success: true,
    clientId,
    clusterId: result.clusterId,
    clusterName: result.clusterName,
    assignmentType: result.assignmentType,
    distance: result.distance,
    message: result.message,
    completedAt: new Date().toISOString()
  };
}

// Export processor function for worker
export default processClientClusterAssignment;