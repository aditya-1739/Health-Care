import React from 'react';
import { Link, useLocation } from 'react-router-dom';

export function RoleSelectionPage() {
  const location = useLocation();
  const bannerMessage = location.state?.message;

  return (
    <div className="role-selection-wrapper">
      {/* Top Back Link */}
      <div style={{ marginBottom: '1.5rem' }}>
        <Link to="/" style={{ color: 'var(--primary)', fontWeight: 600, fontSize: '0.9rem', display: 'inline-flex', alignItems: 'center', gap: '0.35rem', textDecoration: 'none' }}>
          ← Back to Homepage
        </Link>
      </div>

      {bannerMessage && (
        <div className="alert alert-success" style={{ marginBottom: '2rem' }}>
          {bannerMessage}
        </div>
      )}

      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
        <h1 style={{ fontSize: '2.4rem', fontWeight: 800, marginBottom: '0.6rem', color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
          Healthcare Portal Sign In
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '1.05rem', maxWidth: '580px', margin: '0 auto', lineHeight: 1.6 }}>
          Select your portal to access your personalized appointment scheduling, clinical workflow, or administration console.
        </p>
      </div>

      {/* 1. VISUALLY DOMINANT FEATURED PATIENT CARD */}
      <div className="patient-featured-card">
        <div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', background: 'var(--teal-light)', color: 'var(--secondary-dark)', border: '1px solid var(--teal-border)', borderRadius: 'var(--radius-full)', padding: '0.3rem 0.8rem', fontSize: '0.78rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '1rem' }}>
            <span>🌟</span> Most Popular • Patients & Families
          </div>

          <h2 style={{ fontSize: '1.75rem', fontWeight: 800, marginBottom: '0.6rem', color: 'var(--text-main)', letterSpacing: '-0.01em' }}>
            Patient Portal
          </h2>

          <p style={{ color: 'var(--text-muted)', fontSize: '0.975rem', lineHeight: 1.6, marginBottom: '1.25rem' }}>
            Find certified doctors, schedule consultation slots with temporary holds, submit pre-visit symptoms, and access structured digital prescriptions and medical history.
          </p>

          <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 1.25rem 0', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.6rem', fontSize: '0.875rem', color: 'var(--text-main)' }}>
            <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className="trust-check" style={{ width: '20px', height: '20px', fontSize: '0.7rem' }}>✓</span> Real-time slot booking
            </li>
            <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className="trust-check" style={{ width: '20px', height: '20px', fontSize: '0.7rem' }}>✓</span> Pre-visit symptom intake
            </li>
            <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className="trust-check" style={{ width: '20px', height: '20px', fontSize: '0.7rem' }}>✓</span> Digital prescription vault
            </li>
            <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className="trust-check" style={{ width: '20px', height: '20px', fontSize: '0.7rem' }}>✓</span> Personal medical profile
            </li>
          </ul>
        </div>

        <div style={{ background: '#f8fafc', padding: '1.75rem', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: '1rem', textAlign: 'center' }}>
          <div style={{ width: '56px', height: '56px', borderRadius: '50%', background: 'var(--primary-light)', color: 'var(--primary-dark)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto', fontSize: '1.75rem' }}>
            👤
          </div>
          <Link to="/login?role=patient" className="btn btn-primary btn-lg" style={{ width: '100%', fontWeight: 700 }}>
            Sign In as Patient →
          </Link>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            New patient?{' '}
            <Link to="/register" style={{ color: 'var(--primary)', fontWeight: 700, textDecoration: 'none' }}>
              Register account
            </Link>
          </div>
        </div>
      </div>

      {/* 2. SECONDARY CLINICAL & ADMINISTRATIVE STAFF STRIP */}
      <div className="staff-section-divider">
        <hr />
        <span style={{ fontSize: '0.85rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', background: 'var(--bg-main)', padding: '0 0.5rem' }}>
          Healthcare Practitioners & Staff
        </span>
        <hr />
      </div>

      <div className="grid-2" style={{ gap: '1.5rem' }}>
        {/* Doctor Console Card */}
        <div className="staff-card">
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <div style={{ width: '42px', height: '42px', borderRadius: 'var(--radius-md)', background: 'var(--teal-light)', color: 'var(--secondary-dark)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.3rem' }}>
                🩺
              </div>
              <span className="user-badge badge-doctor" style={{ fontSize: '0.75rem' }}>
                Practitioner Access
              </span>
            </div>

            <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.4rem', color: 'var(--text-main)' }}>
              Doctor Console
            </h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', lineHeight: 1.5, marginBottom: '1.25rem' }}>
              Review assigned patient queues, inspect AI pre-visit clinical summaries, author structured digital prescriptions, and manage working hours.
            </p>
          </div>

          <div>
            <Link to="/login?role=doctor" className="btn btn-teal btn-block" style={{ fontWeight: 600 }}>
              Sign In as Doctor →
            </Link>
            <div style={{ marginTop: '0.75rem', textAlign: 'center', fontSize: '0.775rem', color: 'var(--text-muted)' }}>
              Staff accounts are provisioned by hospital administrators
            </div>
          </div>
        </div>

        {/* Admin Console Card */}
        <div className="staff-card">
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <div style={{ width: '42px', height: '42px', borderRadius: 'var(--radius-md)', background: '#f5f3ff', color: '#6d28d9', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.3rem' }}>
                ⚙️
              </div>
              <span className="user-badge badge-admin" style={{ fontSize: '0.75rem' }}>
                Staff Clearance
              </span>
            </div>

            <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.4rem', color: 'var(--text-main)' }}>
              Admin Console
            </h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', lineHeight: 1.5, marginBottom: '1.25rem' }}>
              Provision practitioner staff profiles, manage user directories, review leave requests, and inspect reliability metrics and audit logs.
            </p>
          </div>

          <div>
            <Link to="/login?role=admin" className="btn btn-secondary btn-block" style={{ fontWeight: 600 }}>
              Sign In as Admin →
            </Link>
            <div style={{ marginTop: '0.75rem', textAlign: 'center', fontSize: '0.775rem', color: 'var(--text-muted)' }}>
              Root administrative authorization required
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
