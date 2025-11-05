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

    const response = await fetch(`${this.authServiceUrl}/api/user/users/`, {
      method: 'GET',
      headers
    });

    if (!response.ok) {
      throw new Error(`Auth service request failed: ${response.status}`);
    }

    const users = await response.json() as any[];
    console.log(`Received ${users.length} users from auth service`);


    // Debug: Show what tenant values we actually have
    const tenantValues = [...new Set(users.map(u => u.tenant))];
    console.log('Unique tenant values in response:', tenantValues);

    // Filter for carers only
    const carers = users.filter((user: any) => 
      user.role === 'carer' && user.status === 'active'
    );

    console.log(`Filtered to ${carers.length} active carers`);

    return carers;
  }

  async getCarerById(authToken: string | undefined, carerId: string) {
    const carers = await this.getCarers(authToken);
    console.log(`Searching for carer ID: ${carerId} among ${carers.length} carers`);
    
    const carer = carers.find((carer: any) => carer.id.toString() === carerId);
    console.log('Found carer:', carer ? 'Yes' : 'No');
    
    return carer;
  }
}