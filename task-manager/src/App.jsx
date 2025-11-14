// App.js - Updated
import React, { useState, useEffect } from 'react';
import Dashboard from './components/Dashboard';
import AdminDashboard from './components/AdminDashboard';
import Login from './pages/Login';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      verifyToken(token);
    } else {
      setLoading(false);
    }
  }, []);

  const verifyToken = async (token) => {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      const userData = {
        id: payload.id || payload.sub,
        first_name: payload.first_name || '',
        last_name: payload.last_name || '',
        email: payload.email || '',
        username: payload.username || '',
        role: payload.role || 'user'
      };
      setIsAuthenticated(true);
      setUser(userData);
    } catch (error) {
      console.error('Token parsing failed:', error);
      localStorage.removeItem('token');
      setIsAuthenticated(false);
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = (token, userData) => {
    localStorage.setItem('token', token);
    setIsAuthenticated(true);
    setUser(userData);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setIsAuthenticated(false);
    setUser(null);
  };

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!isAuthenticated) {
    return <Login onLogin={handleLogin} />;
  }

  // Render Admin Dashboard for admin users, regular dashboard for others
  return (
    <div className="App">
      {user?.role === 'admin' || user?.role === 'co-admin' ? (
        <AdminDashboard user={user} onLogout={handleLogout} />
      ) : (
        <Dashboard user={user} onLogout={handleLogout} />
      )}
    </div>
  );
}

export default App;
