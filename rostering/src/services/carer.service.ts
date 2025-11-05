type Tenant = {
  unique_id: string;
  schema_name: string;
  users: any[];
};

type AuthServiceResponse = {
  tenants: Tenant[];
};

export class CarerService {
  private authServiceUrl = process.env.AUTH_SERVICE_URL || 'https://server1.prolianceltd.com';

  async getCarers(authToken?: string, tenantId?: string) {
    const headers: any = { 'Content-Type': 'application/json' };
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

    const response = await fetch(`${this.authServiceUrl}/api/user/users/all-tenants/`, {
      method: 'GET',
      headers
    });

    if (!response.ok) {
      throw new Error(`Auth service request failed: ${response.status}`);
    }

    const data = await response.json() as AuthServiceResponse;
    
    // Filter for carers and optionally by tenant
    let allUsers = (data.tenants ?? []).flatMap((tenant: Tenant) => 
      tenant.users.map((user: any) => ({
        ...user,
        tenantId: tenant.unique_id,
        tenantName: tenant.schema_name
      }))
    );

    // Filter for carers only (adjust role filter as needed)
    const carers = allUsers.filter((user: any) => 
      user.role === 'carer' && user.status === 'active'
    );

    // Filter by tenant if specified
    if (tenantId) {
      return carers.filter((carer: any) => carer.tenantId === tenantId);
    }

    return carers;
  }

  async getCarerById(authToken: string | undefined, carerId: string) {
    const carers = await this.getCarers(authToken);
    return carers.find((carer: any) => carer.id.toString() === carerId);
  }
}