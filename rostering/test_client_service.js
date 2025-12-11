const { ClientService } = require('./src/services/client.service');

async function testClientService() {
  const clientService = new ClientService();

  console.log('Testing ClientService.getClientsByIds...');

  // Test with some client IDs from the database
  const clientIds = ['104', '105', '106'];
  const token = null; // No token for now

  try {
    const clients = await clientService.getClientsByIds(token, clientIds);
    console.log('Success! Clients returned:', clients.length);
    console.log('Clients:', clients);
  } catch (error) {
    console.error('Error:', error);
  }
}

testClientService();