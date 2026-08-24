import React, { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function LoginPage() {
  const [searchParams] = useSearchParams();
  const roleParam = (searchParams.get('role') || '').toLowerCase();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();

  const getRoleHeader = () => {
    switch (roleParam) {
      case 'patient':
        return {
          title: 'Patient Sign In',
          subtitle: 'Access your patient scheduling & medication portal',
          badgeColor: '#eff6ff',
          badgeText: 'Patient Portal',
          textColor: '#2563eb',
        };
      case 'doctor':
        return {
          title: 'Doctor Sign In',
          subtitle: 'Access your clinical consultations & prescription console',
          badgeColor: '#ecfdf5',
          badgeText: 'Doctor Console',
          textColor: '#059669',
        };
      case 'admin':
        return {
          title: 'Administrator Sign In',
          subtitle: 'Access system operations and staff administration',
          badgeColor: '#f5f3ff',
          badgeText: 'Admin Console',
          textColor: '#7c3aed',
        };
      default:
        return {
          title: 'Healthcare Sign In',
          subtitle: 'Access your healthcare portal account',
          badgeColor: '#f1f5f9',
          badgeText: 'Portal Login',
          textColor: '#475569',
        };
    }
  };

  const headerInfo = getRoleHeader();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const user = await login(email.trim(), password);
      // Route based on authentic backend-verified role
      if (user.role === 'PATIENT') {
        navigate('/patient/dashboard');
      } else if (user.role === 'DOCTOR') {
        navigate('/doctor/dashboard');
      } else if (user.role === 'ADMIN') {
        navigate('/admin/dashboard');
      } else {
        navigate('/');
      }
    } catch (err) {
      setError(err.message || 'Login failed. Please check your email and password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container" style={{ padding: '2rem 1rem' }}>
      <div className="auth-card" style={{ maxWidth: '440px' }}>
        {/* Back to Portal Selection */}
        <div style={{ marginBottom: '1.25rem' }}>
          <Link
            to="/roles"
            style={{
              color: 'var(--text-muted)',
              fontSize: '0.85rem',
              fontWeight: 600,
              textDecoration: 'none',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
            }}
          >
            ← Back to Portal Selection
          </Link>
        </div>

        <div className="auth-header" style={{ textAlign: 'left', marginBottom: '1.5rem' }}>
          <span
            style={{
              display: 'inline-block',
              background: headerInfo.badgeColor,
              color: headerInfo.textColor,
              fontSize: '0.8rem',
              fontWeight: 700,
              padding: '3px 10px',
              borderRadius: '6px',
              marginBottom: '0.6rem',
            }}
          >
            {headerInfo.badgeText}
          </span>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 800, margin: '0 0 0.35rem 0', color: 'var(--text-main)' }}>
            {headerInfo.title}
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', margin: 0 }}>
            {headerInfo.subtitle}
          </p>
        </div>

        {error && (
          <div className="alert alert-error" role="alert" style={{ marginBottom: '1.25rem' }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="email">Email Address</label>
            <input
              id="email"
              type="email"
              className="form-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="e.g. user@example.com"
              autoComplete="email"
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="password">Password</label>
            <div className="password-input-wrapper">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                className="form-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                autoComplete="current-password"
                required
              />
              <button
                type="button"
                className="password-toggle-btn"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                title={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                    <line x1="1" y1="1" x2="23" y2="23" />
                  </svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-block"
            disabled={loading}
            style={{ marginTop: '1.5rem', padding: '0.75rem', fontSize: '1rem', fontWeight: 600 }}
          >
            {loading ? 'Authenticating...' : 'Sign In'}
          </button>
        </form>

        <div style={{ marginTop: '1.5rem', textAlign: 'center', fontSize: '0.875rem' }}>
          {roleParam === 'patient' || !roleParam ? (
            <p style={{ color: 'var(--text-muted)' }}>
              New patient?{' '}
              <Link to="/register" style={{ color: 'var(--primary)', fontWeight: 600, textDecoration: 'none' }}>
                Create an account
              </Link>
            </p>
          ) : (
            <p style={{ fontSize: '0.8rem', color: 'var(--text-light)', margin: 0 }}>
              Doctor & Admin accounts are managed by system administrators.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
