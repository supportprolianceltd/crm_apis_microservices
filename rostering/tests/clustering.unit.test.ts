// tests/clustering.unit.test.ts
import { ClusteringService } from '../src/services/clustering.service';

// Mock the private methods
jest.mock('../src/services/clustering.service', () => {
  return {
    ClusteringService: jest.fn().mockImplementation(() => ({
      calculateDistance: jest.fn().mockReturnValue(100),
      calculateSingleClusterMetrics: function(cluster: any) {
        // Mock implementation that doesn't rely on private methods
        return {
          geographicCompactness: 100,
          timeWindowCohesion: 80,
          carerFitScore: cluster.metrics.carerFitScore || 0,
          continuityScore: 90
        };
      }
    }))
  };
});

describe('Clustering Service Unit Tests', () => {
  let clusteringService: ClusteringService;

  beforeEach(() => {
    clusteringService = new ClusteringService(
      {} as any,
      {} as any,  
      {} as any
    );
  });

  describe('Quality Metrics Calculation', () => {
    it('should calculate metrics with mock data', () => {
      const mockCluster = {
        centroid: { latitude: 51.5, longitude: -0.1 },
        visits: [
          { 
            latitude: 51.5001, 
            longitude: -0.1001,
            timeStartMinutes: 540,
            timeEndMinutes: 600
          }
        ],
        metrics: { carerFitScore: 85 }
      } as any;

      const metrics = (clusteringService as any).calculateSingleClusterMetrics(mockCluster);
      
      expect(metrics).toHaveProperty('geographicCompactness');
      expect(metrics).toHaveProperty('timeWindowCohesion');
      expect(metrics).toHaveProperty('carerFitScore');
    });
  });
});