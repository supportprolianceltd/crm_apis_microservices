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
          if (!postResp.ok) return [];
          return await postResp.json();
        } catch (e) {
          console.error('ClientService.getClientsByIds fallback POST failed', e);
          return [];
        }
      }
      return await resp.json();
    } catch (err) {
      console.error('ClientService.getClientsByIds error', err);
      return [];
    }
  }
}
