import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:9090/api/project-manager/api';

const instance = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
});

instance.interceptors.request.use(config => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

instance.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default instance;