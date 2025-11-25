export class ClientService {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || process.env.AUTH_SERVICE_URL || 'http://auth-service';
  }

  async getClientById(token: string | undefined, id: string) {
    try {
      const url = `${this.baseUrl.replace(/\/$/, '')}/api/user/clients/${encodeURIComponent(id)}`;
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
      // Prefer GET with comma-separated ids when supported
      const query = ids.map(encodeURIComponent).join(',');
      const url = `${this.baseUrl.replace(/\/$/, '')}/api/user/clients?ids=${query}`;
      const resp = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        }
      });
      if (!resp.ok) {
        // Fallback: try POST bulk lookup if available
        try {
          const postUrl = `${this.baseUrl.replace(/\/$/, '')}/api/user/clients/bulk`;
          const postResp = await fetch(postUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(token ? { Authorization: `Bearer ${token}` } : {})
            },
            body: JSON.stringify({ ids })
          });
          if (!postResp.ok) {
            console.error('ClientService.getClientsByIds POST fallback returned non-ok', postResp.status);
            return [];
          }
          const postParsed = await postResp.json();
          return this.normalizeClientsResponse(postParsed);
        } catch (e) {
          console.error('ClientService.getClientsByIds fallback POST failed', e);
          return [];
        }
      }

      const parsed = await resp.json();
      return this.normalizeClientsResponse(parsed);
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
