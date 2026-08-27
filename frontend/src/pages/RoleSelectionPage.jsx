import React from 'react';
import { Link, useLocation } from 'react-router-dom';

export function RoleSelectionPage() {
  const location = useLocation();
  const bannerMessage = location.state?.message;

  return (
    <div className="role-selection-wrapper">
      {/* Top Back Link */}
      <div style={{ marginBottom: '2rem' }}>
        <Link
          to="/"
          style={{
            color: 'var(--text-muted)',
            fontWeight: 600,
            fontSize: '0.875rem',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.35rem',
            textDecoration: 'none',
          }}
        >
          ← Back to Homepage
        </Link>
      </div>

      {bannerMessage && (
        <div className="alert alert-success" style={{ marginBottom: '2rem' }}>
          {bannerMessage}
        </div>
      )}

      {/* Header */}
      <div className="role-selection-header">
        <h1>Choose your portal</h1>
        <p>Select how you want to access the platform.</p>
      </div>

      {/* 3 Balanced Role Cards */}
      <div className="roles-grid-3">
        {/* Patient Card */}
        <div className="role-card">
          <div>
            <div className="role-card-icon role-icon-patient">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
            </div>
            <h2 className="role-card-title">Patient</h2>
            <p className="role-card-desc">
              Manage appointments, medicines and health information.
            </p>
          </div>

          <div>
            <Link to="/login?role=patient" className="btn btn-primary role-card-btn">
              Continue as Patient →
            </Link>
            <div style={{ marginTop: '0.75rem', textAlign: 'center', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              New patient?{' '}
              <Link to="/register" style={{ color: 'var(--primary)', fontWeight: 600, textDecoration: 'none' }}>
                Register here
              </Link>
            </div>
          </div>
        </div>

        {/* Doctor Card */}
        <div className="role-card">
          <div>
            <div className="role-card-icon role-icon-doctor">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4.8 2.3A.3.3 0 1 0 5 2H4a2 2 0 0 0-2 2v5a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6V4a2 2 0 0 0-2-2h-1a.2.2 0 1 0 .3.3" />
                <path d="M8 15v1a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6v-4" />
                <circle cx="20" cy="10" r="2" />
              </svg>
            </div>
            <h2 className="role-card-title">Doctor</h2>
            <p className="role-card-desc">
              Manage consultations, patients and prescriptions.
            </p>
          </div>

          <div>
            <Link to="/login?role=doctor" className="btn btn-teal role-card-btn">
              Continue as Doctor →
            </Link>
            <div style={{ marginTop: '0.75rem', textAlign: 'center', fontSize: '0.775rem', color: 'var(--text-muted)' }}>
              Practitioner account required
            </div>
          </div>
        </div>

        {/* Admin Card */}
        <div className="role-card">
          <div>
            <div className="role-card-icon role-icon-admin">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
            <h2 className="role-card-title">Administrator</h2>
            <p className="role-card-desc">
              Manage users, doctors and the platform.
            </p>
          </div>

          <div>
            <Link to="/admin-login" className="btn btn-secondary role-card-btn">
              Continue as Administrator →
            </Link>
            <div style={{ marginTop: '0.75rem', textAlign: 'center', fontSize: '0.775rem', color: 'var(--text-muted)' }}>
              Administrative clearance required
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
