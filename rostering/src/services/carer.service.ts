type Tenant = {
  unique_id: string;
  schema_name: string;
  users: any[];
};

type AuthServiceResponse = {
  tenants: Tenant[];
};

type Carer = any;

export class CarerService {
  private authServiceUrl = process.env.AUTH_SERVICE_URL || 'http://localhost:8001';

  async getCarers(authToken?: string, tenantId?: string) {
    const headers: any = { 'Content-Type': 'application/json' };
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

    console.log(`Calling: ${this.authServiceUrl}/api/user/users/`);

    const response = await fetch(`${this.authServiceUrl}/api/user/users/`, {
      method: 'GET',
      headers
    });

    if (!response.ok) {
      console.error(`Auth service returned status: ${response.status}`);
      throw new Error(`Auth service request failed: ${response.status}`);
    }

    const data: any = await response.json();
    console.log('Auth service response structure:', Object.keys(data || {}));
    
    // Handle the new paginated response format
    let users: any[] = [];
    
    if (data && typeof data === 'object') {
      if (Array.isArray(data.results)) {
        console.log(`Found ${data.results.length} users in 'results' array`);
        users = data.results;
      } else if (Array.isArray(data)) {
        console.log(`Found ${data.length} users in direct array`);
        users = data;
      } else {
        console.warn('Unexpected response format from auth service:', data);
        return [];
      }
    }

    console.log(`Processing ${users.length} users from auth service`);

    // Return all users without filtering
    console.log(`Returning ${users.length} users`);
    return users;
  }

  async getCarerById(authToken: string | undefined, carerId: string): Promise<Carer | null> {
    // For internal/background operations, skip auth service call if token is mock
    if (authToken && authToken.includes('mock-token-for-background-job')) {
      console.log(`Using internal carer lookup for background job (carerId: ${carerId})`);
      return this.getCarerByIdInternal(carerId);
    }

    try {
      const headers: any = { 'Content-Type': 'application/json' };
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

      console.log(`Calling: ${this.authServiceUrl}/api/user/users/${carerId}/`);

      const response = await fetch(`${this.authServiceUrl}/api/user/users/${carerId}/`, {
        method: 'GET',
        headers
      });

      if (!response.ok) {
        console.error(`Auth service returned status: ${response.status} for carer ${carerId}`);
        return null;
      }

      const carer = await response.json() as Carer;
      console.log('Found carer:', carer ? `Yes - ${carer.first_name} ${carer.last_name}` : 'No');

      return carer;
    } catch (error) {
      console.error(`Error fetching carer ${carerId}:`, error);
      return null;
    }
  }

  /**
   * Internal method to get carer by ID without authentication
   * Used for background jobs where carer validation already occurred
   */
  private async getCarerByIdInternal(carerId: string) {
    console.log(`Internal carer lookup for ID: ${carerId}`);

    // For internal operations, we assume the carer exists and return basic info
    // In a real implementation, you might want to cache carer data or have a local lookup
    // For now, return a minimal carer object that satisfies the interface
    return {
      id: carerId,
      first_name: 'Carer',
      last_name: '(Background Job)',
      email: `carer_${carerId}@internal.local`,
      role: 'carer',
      status: 'active',
      profile: {
        personal_phone: null,
        work_phone: null,
        professional_qualifications: []
      }
    };
  }
}