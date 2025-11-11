type Tenant = {
  unique_id: string;
  schema_name: string;
  users: any[];
};

type AuthServiceResponse = {
  tenants: Tenant[];
};

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

    // Filter for carers only (keep role filtering, remove tenant filtering)
    const carers = users.filter((user: any) =>
      user.role === 'carer' && user.status === 'active'
    );

    console.log(`Filtered to ${carers.length} active carers`);
    return carers;
  }

  async getCarerById(authToken: string | undefined, carerId: string) {
    const carers = await this.getCarers(authToken);
    console.log(`Searching for carer ID: ${carerId} among ${carers.length} carers`);
    
    // Debug: Log all carer IDs to see what's available
    console.log('Available carer IDs:', carers.map(c => c.id));
    
    const carer = carers.find((carer: any) => {
      const match = carer.id.toString() === carerId;
      console.log(`Checking carer ${carer.id} (type: ${typeof carer.id}) against ${carerId} (type: ${typeof carerId}): ${match}`);
      return match;
    });
    
    console.log('Found carer:', carer ? `Yes - ${carer.first_name} ${carer.last_name}` : 'No');
    
    return carer;
  }
}