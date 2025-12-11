export class ClientService {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || process.env.AUTH_SERVICE_URL || 'http://auth-service';
  }

  async getClientById(token: string | undefined, id: string) {
    try {
      const url = `${this.baseUrl.replace(/\/$/, '')}/api/user/users/${encodeURIComponent(id)}`;
      const resp = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        }
      });
      if (!resp.ok) return null;
      return await resp.json();
    } catch (err) {
      console.error('ClientService.getClientById error', err);
      return null;
    }
  }

  async getClientsByIds(token: string | undefined, ids: string[]) {
    if (!ids || ids.length === 0) return [];

    try {
      // Make individual requests for each client ID since users endpoint doesn't support bulk lookup
      const clientPromises = ids.map(id => this.getClientById(token, id));
      const clients = await Promise.all(clientPromises);

      // Filter out null results (clients not found)
      return clients.filter(client => client !== null);
    } catch (err) {
      console.error('ClientService.getClientsByIds error', err);
      return [];
    }
  }

  private normalizeClientsResponse(parsed: any): any[] {
    if (!parsed) return [];
    if (Array.isArray(parsed)) return parsed;
    // Common wrapper shapes
    if (Array.isArray(parsed.clients)) return parsed.clients;
    if (Array.isArray(parsed.data)) return parsed.data;
    if (Array.isArray(parsed.results)) return parsed.results;
    // If object has an items array
    if (Array.isArray(parsed.items)) return parsed.items;
    // If single object keyed by id, try to extract values
    if (typeof parsed === 'object') {
      const vals = Object.values(parsed).filter(v => Array.isArray(v));
      if (vals.length > 0) return vals[0] as any[];
    }
    // Unknown shape
    console.error('ClientService.normalizeClientsResponse: unexpected response shape', parsed);
    return [];
  }
}
