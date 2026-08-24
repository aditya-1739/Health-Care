import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function UnauthorizedPage() {
  const { user } = useAuth();

  const getDashboardUrl = () => {
    if (!user) return '/login';
    if (user.role === 'PATIENT') return '/patient/dashboard';
    if (user.role === 'DOCTOR') return '/doctor/dashboard';
    if (user.role === 'ADMIN') return '/admin/dashboard';
    return '/';
  };

  return (
    <div className="auth-container">
      <div className="auth-card" style={{ textAlign: 'center' }}>
        <div style={{ fontSize: '3rem', color: 'var(--danger)', marginBottom: '1rem' }}>
          ⚠️
        </div>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)', marginBottom: '0.5rem' }}>
          403 - Access Denied
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.925rem', marginBottom: '1.5rem' }}>
          You do not have permission to view or access this page. Your role (<strong>{user?.role || 'Guest'}</strong>) is restricted.
        </p>

        <Link to={getDashboardUrl()} className="btn btn-primary btn-block">
          Return to Your Dashboard
        </Link>
      </div>
    </div>
  );
}
