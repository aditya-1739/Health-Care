import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function LandingPage() {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const getDashboardLink = () => {
    if (!user) return '/roles';
    if (user.role === 'PATIENT') return '/patient/dashboard';
    if (user.role === 'DOCTOR') return '/doctor/dashboard';
    if (user.role === 'ADMIN') return '/admin/dashboard';
    return '/';
  };

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  return (
    <div className="landing-container">
      {/* Navigation Header */}
      <header className="landing-nav">
        <Link to="/" className="brand">
          <div className="brand-icon">+</div>
          <span>Healthcare Appointment Manager</span>
        </Link>

        {/* Mobile menu toggle */}
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

        {/* Desktop & Responsive Mobile Links */}
        <ul className={`landing-nav-links ${mobileMenuOpen ? 'landing-nav-links-mobile-open' : ''}`}>
          <li>
            <a href="#how-it-works" onClick={() => setMobileMenuOpen(false)}>How It Works</a>
          </li>
          <li>
            <a href="#features" onClick={() => setMobileMenuOpen(false)}>Features</a>
          </li>
          <li>
            <Link to="/medicine-information" onClick={() => setMobileMenuOpen(false)}>Search Medicine</Link>
          </li>
          <li>
            <a href="#security" onClick={() => setMobileMenuOpen(false)}>Security</a>
          </li>

          {/* Mobile Auth Links inside Drawer */}
          {mobileMenuOpen && (
            <li style={{ borderTop: '1px solid var(--border)', paddingTop: '0.75rem', marginTop: '0.25rem' }}>
              {isAuthenticated ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  <Link to={getDashboardLink()} className="btn btn-primary btn-block" onClick={() => setMobileMenuOpen(false)}>
                    Dashboard ({user?.role})
                  </Link>
                  <button onClick={() => { setMobileMenuOpen(false); handleLogout(); }} className="btn btn-outline btn-block">
                    Logout
                  </button>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  <Link to="/roles" className="btn btn-outline btn-block" onClick={() => setMobileMenuOpen(false)}>
                    Sign In
                  </Link>
                  <Link to="/register" className="btn btn-primary btn-block" onClick={() => setMobileMenuOpen(false)}>
                    Register as Patient
                  </Link>
                </div>
              )}
            </li>
          )}
        </ul>

        {/* Desktop Header Actions */}
        <div className="nav-user" style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          {isAuthenticated ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Link to={getDashboardLink()} className="btn btn-primary">
                Dashboard ({user?.role})
              </Link>
              <button onClick={handleLogout} className="btn btn-outline" style={{ padding: '0.5rem 0.85rem' }}>
                Logout
              </button>
            </div>
          ) : (
            <>
              <Link to="/roles" className="btn btn-outline">
                Sign In
              </Link>
              <Link to="/register" className="btn btn-primary">
                Register as Patient
              </Link>
            </>
          )}
        </div>
      </header>

      {/* Hero Section */}
      <section className="landing-hero">
        <div>
          <div className="hero-eyebrow">
            <span>✨</span> Healthcare made simpler
          </div>

          <h1 className="hero-title">
            Better Appointments. <span className="hero-title-highlight">Better Care.</span>
          </h1>

          <p className="hero-description">
            Find certified doctors, schedule appointment slots with temporary holds, submit pre-visit symptoms, and manage digital prescriptions in one unified platform.
          </p>

          <div className="hero-cta-group">
            {isAuthenticated ? (
              <Link to={getDashboardLink()} className="btn btn-primary btn-lg">
                Enter Your Dashboard →
              </Link>
            ) : (
              <>
                <Link to="/register" className="btn btn-primary btn-lg">
                  Find a Doctor
                </Link>
                <Link to="/roles" className="btn btn-outline btn-lg">
                  Sign In
                </Link>
              </>
            )}
          </div>
        </div>

        {/* Hero Visual with Overlapping Demo Confirmation Card */}
        <div className="hero-image-wrapper">
          <div className="hero-photo-frame" style={{ background: '#ffffff', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1.25rem' }}>
            <img
              src="/images/hero-doctor-patient.jpg"
              alt="Doctor consulting with a patient during a clinical appointment"
              style={{ maxHeight: '390px', width: 'auto', maxWidth: '100%', objectFit: 'contain', display: 'block' }}
              loading="eager"
            />
          </div>

          {/* Overlapping Appointment Confirmation Card for Visual Depth */}
          <div className="hero-demo-overlap-card">
            <div style={{ width: '42px', height: '42px', borderRadius: '50%', background: 'var(--teal-light)', color: 'var(--secondary-dark)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: '0.9rem', border: '1px solid var(--teal-border)' }}>
              Dr
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                Appointment Confirmed
                <span style={{ color: 'var(--secondary)', fontSize: '0.85rem' }}>✓</span>
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Today • 4:00 PM • Dr. Sarah Connor</div>
            </div>
            <span className="user-badge badge-doctor" style={{ fontSize: '0.75rem', padding: '0.25rem 0.55rem', marginLeft: 'auto' }}>
              Confirmed
            </span>
          </div>
        </div>
      </section>

      {/* Trust / Value Strip */}
      <div className="trust-strip">
        <div className="trust-strip-inner">
          <span style={{ color: 'var(--text-main)', fontWeight: 800, letterSpacing: '-0.01em' }}>
            Unified Clinical Platform:
          </span>
          <div className="trust-strip-item">
            <span className="trust-check">✓</span> Real-Time Doctor Appointments
          </div>
          <div className="trust-strip-item">
            <span className="trust-check">✓</span> Pre-Visit Symptom Intake
          </div>
          <div className="trust-strip-item">
            <span className="trust-check">✓</span> Structured Digital Prescriptions
          </div>
          <div className="trust-strip-item">
            <span className="trust-check">✓</span> Authoritative Medicine Information
          </div>
        </div>
      </div>

      {/* Section 1: How It Works (4-Step Consultation Journey) */}
      <section id="how-it-works" className="landing-section" style={{ background: '#f8fafc', borderBottom: '1px solid var(--border)' }}>
        <div className="landing-section-header">
          <div className="landing-section-tag">How It Works</div>
          <h2 className="landing-section-title">Simple 4-Step Consultation Journey</h2>
          <p className="landing-section-desc">
            From booking to digital follow-up care, your healthcare experience is effortless and transparent.
          </p>
        </div>

        <div className="timeline-grid">
          <div className="timeline-step-card">
            <div className="timeline-step-header">
              <div className="timeline-step-number">01</div>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              </svg>
            </div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.4rem', color: 'var(--text-main)' }}>Choose a Doctor</h3>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', lineHeight: 1.5, margin: 0 }}>
              Browse certified physicians, filter by clinical specialty, and view verified schedules.
            </p>
          </div>

          <div className="timeline-step-card">
            <div className="timeline-step-header">
              <div className="timeline-step-number">02</div>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                <line x1="16" y1="2" x2="16" y2="6"></line>
                <line x1="8" y1="2" x2="8" y2="6"></line>
                <line x1="3" y1="10" x2="21" y2="10"></line>
              </svg>
            </div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.4rem', color: 'var(--text-main)' }}>Book Your Slot</h3>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', lineHeight: 1.5, margin: 0 }}>
              Reserve your slot with temporary holds and submit pre-visit symptoms to prepare your care team.
            </p>
          </div>

          <div className="timeline-step-card">
            <div className="timeline-step-header">
              <div className="timeline-step-number">03</div>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
              </svg>
            </div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.4rem', color: 'var(--text-main)' }}>Attend Consultation</h3>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', lineHeight: 1.5, margin: 0 }}>
              Meet with your doctor, discuss clinical findings, and receive comprehensive clinical notes.
            </p>
          </div>

          <div className="timeline-step-card">
            <div className="timeline-step-header">
              <div className="timeline-step-number">04</div>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--secondary)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10.5 20.5L3 13l7.5-7.5"></path>
                <path d="M21 13H4"></path>
              </svg>
            </div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.4rem', color: 'var(--text-main)' }}>Manage Follow-Up</h3>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', lineHeight: 1.5, margin: 0 }}>
              Access structured digital prescriptions and daily medication dosage notifications.
            </p>
          </div>
        </div>
      </section>

      {/* Section 2: Features Grid with Distinct Category Accents & SVG Icons */}
      <section id="features" className="landing-section">
        <div className="landing-section-header">
          <div className="landing-section-tag">Features</div>
          <h2 className="landing-section-title">Everything you need for your healthcare journey</h2>
          <p className="landing-section-desc">
            A comprehensive suite of clinical and patient tools designed to elevate care before, during, and after visits.
          </p>
        </div>

        <div className="features-grid-6">
          <div className="landing-feature-card patient-feature">
            <div className="feature-icon-box patient-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path>
                <circle cx="9" cy="7" r="4"></circle>
                <polyline points="16 11 18 13 22 9"></polyline>
              </svg>
            </div>
            <div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.35rem', color: 'var(--text-main)' }}>Find Certified Doctors</h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', lineHeight: 1.5, margin: 0 }}>
                Explore specialized physicians, credentials, working hours, and real-time consultation availability.
              </p>
            </div>
          </div>

          <div className="landing-feature-card patient-feature">
            <div className="feature-icon-box patient-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                <line x1="16" y1="2" x2="16" y2="6"></line>
                <line x1="8" y1="2" x2="8" y2="6"></line>
                <line x1="3" y1="10" x2="21" y2="10"></line>
              </svg>
            </div>
            <div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.35rem', color: 'var(--text-main)' }}>Guaranteed Slot Holds</h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', lineHeight: 1.5, margin: 0 }}>
                Lock your chosen appointment time with temporary holds while completing pre-visit details.
              </p>
            </div>
          </div>

          <div className="landing-feature-card patient-feature">
            <div className="feature-icon-box patient-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
                <polyline points="10 9 9 9 8 9"></polyline>
              </svg>
            </div>
            <div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.35rem', color: 'var(--text-main)' }}>Pre-Visit Symptom Intake</h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', lineHeight: 1.5, margin: 0 }}>
                Submit symptoms and chief complaints beforehand, generating AI clinical summaries for your doctor.
              </p>
            </div>
          </div>

          <div className="landing-feature-card clinical-feature">
            <div className="feature-icon-box clinical-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z"></path>
                <path d="m8.5 8.5 7 7"></path>
              </svg>
            </div>
            <div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.35rem', color: 'var(--text-main)' }}>Digital Prescriptions</h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', lineHeight: 1.5, margin: 0 }}>
                Physicians issue structured digital prescriptions with dosage instructions and automated reminders.
              </p>
            </div>
          </div>

          <div className="landing-feature-card clinical-feature">
            <div className="feature-icon-box clinical-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="16" x2="12" y2="12"></line>
                <line x1="12" y1="8" x2="12.01" y2="8"></line>
              </svg>
            </div>
            <div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.35rem', color: 'var(--text-main)' }}>Authoritative Medicine Search</h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', lineHeight: 1.5, margin: 0 }}>
                Look up dosage forms, brand names, indications, and safety information backed by RxNorm and DailyMed.
              </p>
            </div>
          </div>

          <div className="landing-feature-card connected-feature">
            <div className="feature-icon-box connected-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
                <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
              </svg>
            </div>
            <div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.35rem', color: 'var(--text-main)' }}>Connected Calendar & Alerts</h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', lineHeight: 1.5, margin: 0 }}>
                Two-way Google Calendar synchronization, email notifications, and automated medication reminders.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Section 3: Visual Split (Left Image, Right Narrative) - Connected Care */}
      <section className="landing-section" style={{ background: '#f8fafc', borderTop: '1px solid var(--border)', borderBottom: '1px solid var(--border)' }}>
        <div className="split-experience-section">
          <div className="experience-image-card photo-grade-overlay">
            <img
              src="/images/consultation.jpg"
              alt="Doctor discussing a patient's healthcare plan and follow-up care"
              loading="lazy"
            />
          </div>

          <div>
            <div className="landing-section-tag">Connected Care</div>
            <h2 style={{ fontSize: '2.1rem', fontWeight: 800, marginBottom: '1rem', color: 'var(--text-main)', lineHeight: 1.25, letterSpacing: '-0.02em' }}>
              From appointment to follow-up, everything stays connected.
            </h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '1rem', lineHeight: 1.6, marginBottom: '1.5rem' }}>
              No more fragmented healthcare steps. Keep your doctor appointments, pre-consultation symptom intake, physician notes, and medication schedules unified in a single secure account.
            </p>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.85rem', fontSize: '0.95rem', color: 'var(--text-main)', margin: 0, padding: 0 }}>
              <li style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <span className="trust-check">✓</span> Real-time appointment scheduling and Google Calendar sync
              </li>
              <li style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <span className="trust-check">✓</span> Pre-visit clinical intake notes for doctor review
              </li>
              <li style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <span className="trust-check">✓</span> Structured digital prescriptions and daily dosage notifications
              </li>
              <li style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <span className="trust-check">✓</span> Comprehensive medical profile with allergy tracking
              </li>
            </ul>
          </div>
        </div>
      </section>

      {/* Section 4: Inverted Visual Split (Left Narrative, Right Image) - Doctor Experience */}
      <section className="landing-section">
        <div className="split-experience-section">
          <div>
            <div className="landing-section-tag">Clinical Workflow</div>
            <h2 style={{ fontSize: '2.1rem', fontWeight: 800, marginBottom: '1rem', color: 'var(--text-main)', lineHeight: 1.25, letterSpacing: '-0.02em' }}>
              Designed for doctors, too.
            </h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '1rem', lineHeight: 1.6, marginBottom: '1.5rem' }}>
              Physicians can streamline their consultation workflow, review patient symptom summaries ahead of visits, and issue structured digital prescriptions with fast medicine autocomplete.
            </p>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.85rem', fontSize: '0.95rem', color: 'var(--text-main)', margin: 0, padding: 0 }}>
              <li style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <span className="trust-check">✓</span> Manage consultation schedules and view patient queues
              </li>
              <li style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <span className="trust-check">✓</span> Review pre-visit symptoms and author clinical notes
              </li>
              <li style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <span className="trust-check">✓</span> Author digital prescriptions with fast medicine autocomplete
              </li>
              <li style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <span className="trust-check">✓</span> Request leaves, adjust working hours, and manage coverage
              </li>
            </ul>
          </div>

          <div className="experience-image-card photo-grade-overlay">
            <img
              src="/images/healthcare-team.jpg"
              alt="Doctor reviewing patient information and clinical notes during a consultation"
              loading="lazy"
            />
          </div>
        </div>
      </section>

      {/* Section 5: Security & Privacy (Deep Dark Navy Background to Anchor Color Palette Higher Up) */}
      <section id="security" className="navy-security-section">
        <div className="navy-security-container">
          <div className="landing-section-header" style={{ marginBottom: '3rem' }}>
            <div className="landing-section-tag" style={{ color: 'var(--teal-accent)' }}>Security & Privacy</div>
            <h2 className="landing-section-title" style={{ color: '#ffffff' }}>
              Built with privacy and reliability in mind
            </h2>
            <p className="landing-section-desc" style={{ color: 'var(--navy-text-muted)' }}>
              Your healthcare records and clinical consultations are guarded by enterprise security controls and audit trails.
            </p>
          </div>

          <div className="security-grid-4">
            <div className="security-card">
              <div className="security-icon-box">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                </svg>
              </div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.4rem', color: '#ffffff' }}>Role-Based Access</h3>
              <p style={{ fontSize: '0.875rem', color: 'var(--navy-text-muted)', lineHeight: 1.5, margin: 0 }}>
                Strict permission boundaries isolating patient medical profiles, doctor credentials, and administrator roles.
              </p>
            </div>

            <div className="security-card">
              <div className="security-icon-box">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                  <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                </svg>
              </div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.4rem', color: '#ffffff' }}>Encrypted Credentials</h3>
              <p style={{ fontSize: '0.875rem', color: 'var(--navy-text-muted)', lineHeight: 1.5, margin: 0 }}>
                OAuth tokens and calendar authorizations are encrypted at rest using AES-256 GCM authenticated cryptography.
              </p>
            </div>

            <div className="security-card">
              <div className="security-icon-box">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10"></circle>
                  <polyline points="12 6 12 12 16 14"></polyline>
                </svg>
              </div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.4rem', color: '#ffffff' }}>Reliable Scheduling</h3>
              <p style={{ fontSize: '0.875rem', color: 'var(--navy-text-muted)', lineHeight: 1.5, margin: 0 }}>
                Transactional outbox architecture and temporary slot holds prevent double bookings and race conditions.
              </p>
            </div>

            <div className="security-card">
              <div className="security-icon-box">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                  <line x1="16" y1="13" x2="8" y2="13"></line>
                  <line x1="16" y1="17" x2="8" y2="17"></line>
                </svg>
              </div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.4rem', color: '#ffffff' }}>Audit Logging</h3>
              <p style={{ fontSize: '0.875rem', color: 'var(--navy-text-muted)', lineHeight: 1.5, margin: 0 }}>
                Comprehensive operational logs record all appointment actions, leave approvals, and profile modifications.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Section 6: High-Contrast CTA Banner */}
      <div className="cta-banner">
        <h2>Ready to manage your healthcare more easily?</h2>
        <p>
          Join patients and doctors streamlining appointments, clinical notes, and medication schedules in one place.
        </p>
        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
          {isAuthenticated ? (
            <Link to={getDashboardLink()} className="btn btn-primary btn-lg" style={{ fontWeight: 700 }}>
              Go to Dashboard →
            </Link>
          ) : (
            <>
              <Link to="/register" className="btn btn-primary btn-lg" style={{ fontWeight: 700 }}>
                Find a Doctor
              </Link>
              <Link to="/roles" className="btn btn-outline btn-lg" style={{ color: '#ffffff', borderColor: '#475569' }}>
                Sign In
              </Link>
            </>
          )}
        </div>
      </div>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="footer-content">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'white', fontWeight: 800, fontSize: '1.15rem', marginBottom: '0.65rem' }}>
              <div className="brand-icon">+</div>
              Healthcare Appointment Manager
            </div>
            <p style={{ fontSize: '0.875rem', color: 'var(--navy-text-muted)', lineHeight: 1.6, maxWidth: '320px', margin: 0 }}>
              A modern scheduling, clinical documentation, and medication reminder platform.
            </p>
          </div>

          <div>
            <h4 style={{ color: 'white', fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.85rem' }}>Product</h4>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.85rem', margin: 0, padding: 0 }}>
              <li><a href="#how-it-works" style={{ color: 'var(--navy-text-muted)', textDecoration: 'none' }}>How It Works</a></li>
              <li><a href="#features" style={{ color: 'var(--navy-text-muted)', textDecoration: 'none' }}>Features</a></li>
              <li><Link to="/medicine-information" style={{ color: 'var(--navy-text-muted)', textDecoration: 'none' }}>Search Medicine</Link></li>
            </ul>
          </div>

          <div>
            <h4 style={{ color: 'white', fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.85rem' }}>Account</h4>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.85rem', margin: 0, padding: 0 }}>
              <li><Link to="/roles" style={{ color: 'var(--navy-text-muted)', textDecoration: 'none' }}>Sign In</Link></li>
              <li><Link to="/register" style={{ color: 'var(--navy-text-muted)', textDecoration: 'none' }}>Register as Patient</Link></li>
            </ul>
          </div>

          <div>
            <h4 style={{ color: 'white', fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.85rem' }}>Information</h4>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.85rem', margin: 0, padding: 0 }}>
              <li><a href="#security" style={{ color: 'var(--navy-text-muted)', textDecoration: 'none' }}>Security & Privacy</a></li>
              <li><Link to="/medicine-information" style={{ color: 'var(--navy-text-muted)', textDecoration: 'none' }}>Medicine Information</Link></li>
            </ul>
          </div>
        </div>

        <div className="footer-bottom">
          <p style={{ margin: 0 }}>© {new Date().getFullYear()} Healthcare Appointment Manager. All rights reserved.</p>
          <p style={{ fontSize: '0.8rem', color: '#64748b', margin: 0 }}>
            Healthcare imagery licensed for open reuse from Unsplash.
          </p>
        </div>
      </footer>
    </div>
  );
}
