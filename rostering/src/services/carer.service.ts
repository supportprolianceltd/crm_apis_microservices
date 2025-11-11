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

  async getCarers(authToken?: string, tenantId?: string, options?: { maxItems?: number }) {
    const headers: any = { 'Content-Type': 'application/json' };
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

    console.log(`Calling: ${this.authServiceUrl}/api/user/users/`);
    // Fetch first page
    const firstResp = await fetch(`${this.authServiceUrl}/api/user/users/`, {
      method: 'GET',
      headers
    });

    if (!firstResp.ok) {
      console.error(`Auth service returned status: ${firstResp.status}`);
      throw new Error(`Auth service request failed: ${firstResp.status}`);
    }

    const firstData: any = await firstResp.json();
    console.log('Auth service response structure (first page):', Object.keys(firstData || {}));

    // Aggregate users from pages (support DRF-style pagination)
    let users: any[] = [];

    const pushResults = (pageData: any) => {
      if (!pageData) return;
      if (Array.isArray(pageData.results)) {
        users.push(...pageData.results);
      } else if (Array.isArray(pageData)) {
        users.push(...pageData);
      }
    };

    // Start with first page
    pushResults(firstData);

    // If we've been asked to limit items, and already have enough, return early
    if (options && typeof options.maxItems === 'number' && users.length >= options.maxItems) {
      return users.slice(0, options.maxItems);
    }

    // If response contains a `next` link, follow it until exhausted
    let nextUrl: string | null | undefined = (firstData && (firstData as any).next) || null;
    while (nextUrl) {
      try {
        // nextUrl may be absolute or relative. If relative, prefix with authServiceUrl.
        const fetchUrl = nextUrl.startsWith('http') ? nextUrl : `${this.authServiceUrl.replace(/\/$/, '')}${nextUrl.startsWith('/') ? nextUrl : '/' + nextUrl}`;
        console.log(`Fetching next page: ${fetchUrl}`);
        const pageResp = await fetch(fetchUrl, { method: 'GET', headers });
        if (!pageResp.ok) {
          console.warn(`Failed to fetch next page ${fetchUrl}: ${pageResp.status}`);
          break; // stop fetching further pages
        }
        const pageData = await pageResp.json();
        pushResults(pageData);

        // If we've been asked to limit items, and now have enough, return early
        if (options && typeof options.maxItems === 'number' && users.length >= options.maxItems) {
          return users.slice(0, options.maxItems);
        }

        // pageData may be typed as {}, cast to any to access `next`
        nextUrl = pageData && (pageData as any).next ? (pageData as any).next : null;
      } catch (err) {
        console.error('Error fetching paginated users:', err);
        break;
      }
    }

    console.log(`Processing ${users.length} users from auth service`);

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