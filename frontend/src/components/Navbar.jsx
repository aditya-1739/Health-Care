import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { UserMenu } from './UserMenu';

export function Navbar() {
  const { user, isAuthenticated } = useAuth();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const isMedicinePage = location.pathname.startsWith('/medicine-information');

  const getDashboardLink = () => {
    if (!user) return '/';
    if (user.role === 'PATIENT') return '/patient/dashboard';
    if (user.role === 'DOCTOR') return '/doctor/dashboard';
    if (user.role === 'ADMIN') return '/admin/dashboard';
    return '/';
  };

  const getDashboardLabel = () => {
    if (!user) return 'Home';
    if (user.role === 'PATIENT') return 'Patient Dashboard';
    if (user.role === 'DOCTOR') return 'Doctor Console';
    if (user.role === 'ADMIN') return 'Admin Console';
    return 'Dashboard';
  };

  return (
    <header className="navbar">
      <div className="nav-content">
        <Link to={getDashboardLink()} className="brand">
          <div className="brand-icon">+</div>
          <span>Healthcare Appointment Manager</span>
        </Link>

        {/* Mobile menu hamburger toggle */}
        <button
          className="mobile-menu-toggle"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          aria-label="Toggle navigation menu"
          aria-expanded={mobileMenuOpen}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            {mobileMenuOpen ? (
              <path d="M18 6L6 18M6 6l12 12" />
            ) : (
              <path d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>

        <nav className={`nav-links ${mobileMenuOpen ? 'nav-links-mobile-open' : ''}`}>
          {isAuthenticated ? (
            <>
              <Link
                to={getDashboardLink()}
                className="nav-link"
                style={{ fontWeight: 600, color: 'var(--text-main)' }}
                onClick={() => setMobileMenuOpen(false)}
              >
                {getDashboardLabel()}
              </Link>
              {!isMedicinePage && (
                <Link
                  to="/medicine-information"
                  className="nav-link"
                  style={{ fontWeight: 600 }}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Search Medicine
                </Link>
              )}
              <div className="nav-user" style={{ display: 'flex', alignItems: 'center' }}>
                <UserMenu onNavigate={() => setMobileMenuOpen(false)} />
              </div>
            </>
          ) : (
            <>
              <Link
                to="/"
                className="nav-link"
                style={{ fontWeight: 500 }}
                onClick={() => setMobileMenuOpen(false)}
              >
                Home
              </Link>
              {isMedicinePage ? (
                <>
                  <a
                    href="/#features"
                    className="nav-link"
                    style={{ fontWeight: 500 }}
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    Features
                  </a>
                  <a
                    href="/#how-it-works"
                    className="nav-link"
                    style={{ fontWeight: 500 }}
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    How It Works
                  </a>
                </>
              ) : (
                <Link
                  to="/medicine-information"
                  className="nav-link"
                  style={{ fontWeight: 500 }}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Search Medicine
                </Link>
              )}
              <div className="nav-user" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Link
                  to="/roles"
                  className="btn btn-secondary btn-sm"
                  style={{ fontWeight: 600 }}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Sign In
                </Link>
                <Link
                  to="/register"
                  className="btn btn-primary btn-sm"
                  style={{ fontWeight: 600 }}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Register as Patient
                </Link>
              </div>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
