import api from './axios';

const AUTH_BASE = 'http://localhost:9090/api';

const authAPI = {
  login: (email, password) => {
    return api.post(`${AUTH_BASE}/token/`, {
      email,
      password
    });
  },

  verifyToken: (token) => {
    return api.get(`${AUTH_BASE}/verify/`, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
  },

  getUsers: () => {
    return api.get(`${AUTH_BASE}/user/users/`);
  }
};

export default authAPI;