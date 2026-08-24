import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { profileApi, formatApiError } from '../api/client';
import { formatDoctorName } from '../utils/format';

export function ProfilePage() {
  const { user, logout } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const currentTab = searchParams.get('tab') || 'basic';

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Profile data
  const [profileData, setProfileData] = useState({
    name: '',
    email: '',
    phone: '',
    date_of_birth: '',
    age: null,
    role: '',
    status: '',
    gender: '',
    address: '',
    emergency_contact_name: '',
    emergency_contact_phone: '',
    specialization: '',
    bio: '',
    slot_duration: 30,
    created_at: '',
  });

  // Medical profile data
  const [medicalData, setMedicalData] = useState({
    blood_group: '',
    height_cm: '',
    weight_kg: '',
    allergies: '',
    chronic_conditions: '',
    current_medications: '',
    past_surgeries: '',
    family_history: '',
    medical_notes: '',
  });

  // Appointment history
  const [appointments, setAppointments] = useState({
    upcoming: [],
    past: [],
    cancelled: [],
    total: 0,
  });
  const [apptFilter, setApptFilter] = useState('all');

  // Password change state
  const [passwordForm, setPasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });
  const [showPasswords, setShowPasswords] = useState(false);

  useEffect(() => {
    loadAllProfileData();
  }, []);

  const loadAllProfileData = async () => {
    setLoading(true);
    setError(null);
    try {
      const p = await profileApi.getMe();
      setProfileData({
        name: p.name || '',
        email: p.email || '',
        phone: p.phone || '',
        date_of_birth: p.date_of_birth || '',
        age: p.age,
        role: p.role || '',
        status: p.status || '',
        gender: p.gender || '',
        address: p.address || '',
        emergency_contact_name: p.emergency_contact_name || '',
        emergency_contact_phone: p.emergency_contact_phone || '',
        specialization: p.specialization || '',
        bio: p.bio || '',
        slot_duration: p.slot_duration || 30,
        created_at: p.created_at || '',
      });

      if (p.role === 'PATIENT') {
        const m = await profileApi.getMedical();
        setMedicalData({
          blood_group: m.blood_group || '',
          height_cm: m.height_cm !== null ? m.height_cm : '',
          weight_kg: m.weight_kg !== null ? m.weight_kg : '',
          allergies: m.allergies || '',
          chronic_conditions: m.chronic_conditions || '',
          current_medications: m.current_medications || '',
          past_surgeries: m.past_surgeries || '',
          family_history: m.family_history || '',
          medical_notes: m.medical_notes || '',
        });
      }

      if (p.role === 'PATIENT' || p.role === 'DOCTOR') {
        const appts = await profileApi.getAppointments();
        setAppointments(appts);
      }
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (tabName) => {
    setSearchParams({ tab: tabName });
    setError(null);
    setSuccessMsg(null);
  };

  const handleSaveBasicProfile = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const payload = {
        name: profileData.name,
        phone: profileData.phone || null,
        date_of_birth: profileData.date_of_birth || null,
        gender: profileData.gender || null,
        address: profileData.address || null,
        emergency_contact_name: profileData.emergency_contact_name || null,
        emergency_contact_phone: profileData.emergency_contact_phone || null,
        bio: profileData.bio || null,
        specialization: profileData.specialization || null,
      };
      const updated = await profileApi.updateMe(payload);
      setProfileData((prev) => ({
        ...prev,
        name: updated.name,
        phone: updated.phone || '',
        date_of_birth: updated.date_of_birth || '',
        age: updated.age,
        gender: updated.gender || '',
        address: updated.address || '',
        emergency_contact_name: updated.emergency_contact_name || '',
        emergency_contact_phone: updated.emergency_contact_phone || '',
        bio: updated.bio || '',
        specialization: updated.specialization || '',
      }));
      setSuccessMsg('Profile updated successfully.');
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setSaving(false);
    }
  };

  const handleSaveMedicalProfile = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const payload = {
        blood_group: medicalData.blood_group || null,
        height_cm: medicalData.height_cm ? parseFloat(medicalData.height_cm) : null,
        weight_kg: medicalData.weight_kg ? parseFloat(medicalData.weight_kg) : null,
        allergies: medicalData.allergies || null,
        chronic_conditions: medicalData.chronic_conditions || null,
        current_medications: medicalData.current_medications || null,
        past_surgeries: medicalData.past_surgeries || null,
        family_history: medicalData.family_history || null,
        medical_notes: medicalData.medical_notes || null,
      };
      const updated = await profileApi.updateMedical(payload);
      setMedicalData({
        blood_group: updated.blood_group || '',
        height_cm: updated.height_cm !== null ? updated.height_cm : '',
        weight_kg: updated.weight_kg !== null ? updated.weight_kg : '',
        allergies: updated.allergies || '',
        chronic_conditions: updated.chronic_conditions || '',
        current_medications: updated.current_medications || '',
        past_surgeries: updated.past_surgeries || '',
        family_history: updated.family_history || '',
        medical_notes: updated.medical_notes || '',
      });
      setSuccessMsg('Medical profile saved successfully.');
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setSaving(false);
    }
  };

  const handleChangePassword = async (e) => {
    e.preventDefault();
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      setError('New password and confirm password do not match.');
      return;
    }
    if (passwordForm.new_password === passwordForm.current_password) {
      setError('New password must be different from current password.');
      return;
    }
    if (passwordForm.new_password.length < 8) {
      setError('New password must be at least 8 characters long.');
      return;
    }

    setSaving(true);
    setError(null);
    setSuccessMsg(null);
    try {
      await profileApi.changePassword(passwordForm);
      await logout();
      navigate('/roles', {
        state: { message: 'Password changed successfully. Please sign in with your new password.' },
      });
    } catch (err) {
      setError(formatApiError(err));
      setSaving(false);
    }
  };

  const getDashboardBackLink = () => {
    if (!user) return '/';
    if (user.role === 'PATIENT') return { to: '/patient/dashboard', label: '← Back to Patient Dashboard' };
    if (user.role === 'DOCTOR') return { to: '/doctor/dashboard', label: '← Back to Doctor Console' };
    if (user.role === 'ADMIN') return { to: '/admin/dashboard', label: '← Back to Admin Console' };
    return { to: '/', label: '← Back to Home' };
  };

  const backLink = getDashboardBackLink();

  const getFilteredAppointments = () => {
    if (apptFilter === 'upcoming') return appointments.upcoming;
    if (apptFilter === 'past') return appointments.past;
    if (apptFilter === 'cancelled') return appointments.cancelled;
    return [...appointments.upcoming, ...appointments.past, ...appointments.cancelled];
  };

  if (loading) {
    return (
      <div className="main-content" style={{ maxWidth: '960px', margin: '2rem auto', padding: '0 1rem', textAlign: 'center' }}>
        <div className="card" style={{ padding: '3rem' }}>
          <div style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--primary)' }}>Loading account profile...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="main-content" style={{ maxWidth: '980px', margin: '2rem auto', padding: '0 1.5rem' }}>
      {/* Contextual Navigation Link */}
      <div style={{ marginBottom: '1.25rem' }}>
        <Link to={backLink.to} style={{ color: 'var(--primary)', fontWeight: 600, textDecoration: 'none', fontSize: '0.9rem' }}>
          {backLink.label}
        </Link>
      </div>

      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.85rem', fontWeight: 800, margin: 0, color: 'var(--text-main)' }}>
            Account & Profile
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', margin: '0.25rem 0 0 0' }}>
            Manage your personal information, security, and account preferences.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span className="user-badge" style={{ fontSize: '0.85rem', padding: '4px 10px' }}>
            {profileData.role}
          </span>
          <span style={{ fontSize: '0.8rem', color: '#047857', background: '#ecfdf5', padding: '3px 8px', borderRadius: '4px', border: '1px solid #a7f3d0', fontWeight: 600 }}>
            {profileData.status}
          </span>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '2px solid var(--border)', marginBottom: '1.5rem', overflowX: 'auto' }}>
        <button
          type="button"
          onClick={() => handleTabChange('basic')}
          style={{
            padding: '0.75rem 1.25rem',
            fontWeight: 600,
            fontSize: '0.95rem',
            background: 'none',
            border: 'none',
            borderBottom: currentTab === 'basic' ? '3px solid var(--primary)' : '3px solid transparent',
            color: currentTab === 'basic' ? 'var(--primary)' : 'var(--text-muted)',
            cursor: 'pointer',
            marginBottom: '-2px',
          }}
        >
          Basic Information
        </button>

        {profileData.role === 'PATIENT' && (
          <button
            type="button"
            onClick={() => handleTabChange('medical')}
            style={{
              padding: '0.75rem 1.25rem',
              fontWeight: 600,
              fontSize: '0.95rem',
              background: 'none',
              border: 'none',
              borderBottom: currentTab === 'medical' ? '3px solid var(--primary)' : '3px solid transparent',
              color: currentTab === 'medical' ? 'var(--primary)' : 'var(--text-muted)',
              cursor: 'pointer',
              marginBottom: '-2px',
            }}
          >
            Medical Profile
          </button>
        )}

        {profileData.role === 'DOCTOR' && (
          <button
            type="button"
            onClick={() => handleTabChange('professional')}
            style={{
              padding: '0.75rem 1.25rem',
              fontWeight: 600,
              fontSize: '0.95rem',
              background: 'none',
              border: 'none',
              borderBottom: currentTab === 'professional' ? '3px solid var(--primary)' : '3px solid transparent',
              color: currentTab === 'professional' ? 'var(--primary)' : 'var(--text-muted)',
              cursor: 'pointer',
              marginBottom: '-2px',
            }}
          >
            Professional Profile
          </button>
        )}

        {(profileData.role === 'PATIENT' || profileData.role === 'DOCTOR') && (
          <button
            type="button"
            onClick={() => handleTabChange('appointments')}
            style={{
              padding: '0.75rem 1.25rem',
              fontWeight: 600,
              fontSize: '0.95rem',
              background: 'none',
              border: 'none',
              borderBottom: currentTab === 'appointments' ? '3px solid var(--primary)' : '3px solid transparent',
              color: currentTab === 'appointments' ? 'var(--primary)' : 'var(--text-muted)',
              cursor: 'pointer',
              marginBottom: '-2px',
            }}
          >
            Appointment History
          </button>
        )}

        <button
          type="button"
          onClick={() => handleTabChange('password')}
          style={{
            padding: '0.75rem 1.25rem',
            fontWeight: 600,
            fontSize: '0.95rem',
            background: 'none',
            border: 'none',
            borderBottom: currentTab === 'password' ? '3px solid var(--primary)' : '3px solid transparent',
            color: currentTab === 'password' ? 'var(--primary)' : 'var(--text-muted)',
            cursor: 'pointer',
            marginBottom: '-2px',
          }}
        >
          Change Password
        </button>
      </div>

      {/* Notifications */}
      {error && <div className="alert alert-error" role="alert" style={{ marginBottom: '1.25rem' }}>{error}</div>}
      {successMsg && <div className="alert alert-success" role="status" style={{ marginBottom: '1.25rem', background: '#ecfdf5', color: '#065f46', border: '1px solid #a7f3d0' }}>{successMsg}</div>}

      {/* TAB 1: Basic Information */}
      {currentTab === 'basic' && (
        <div className="card" style={{ padding: '2rem' }}>
          <h2 style={{ fontSize: '1.3rem', fontWeight: 700, marginBottom: '1.25rem', color: 'var(--text-main)' }}>
            Personal Details
          </h2>
          <form onSubmit={handleSaveBasicProfile}>
            <div className="grid-2" style={{ gap: '1.25rem' }}>
              <div className="form-group">
                <label className="form-label" htmlFor="profile-name">Full Name *</label>
                <input
                  id="profile-name"
                  type="text"
                  className="form-input"
                  required
                  value={profileData.name}
                  onChange={(e) => setProfileData({ ...profileData, name: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="profile-email">Email Address (Registered Login)</label>
                <input
                  id="profile-email"
                  type="email"
                  className="form-input"
                  disabled
                  value={profileData.email}
                  style={{ background: '#f1f5f9', cursor: 'not-allowed', color: 'var(--text-muted)' }}
                />
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '3px', display: 'block' }}>
                  Login identity is verified and locked to your registered account.
                </span>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="profile-phone">Contact Phone</label>
                <input
                  id="profile-phone"
                  type="tel"
                  className="form-input"
                  placeholder="+1-555-0100"
                  value={profileData.phone}
                  onChange={(e) => setProfileData({ ...profileData, phone: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="profile-dob">Date of Birth</label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <input
                    id="profile-dob"
                    type="date"
                    className="form-input"
                    max={new Date().toISOString().split('T')[0]}
                    value={profileData.date_of_birth}
                    onChange={(e) => setProfileData({ ...profileData, date_of_birth: e.target.value })}
                  />
                  {profileData.age !== null && (
                    <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--primary)', whiteSpace: 'nowrap', background: 'var(--primary-light)', padding: '0.4rem 0.75rem', borderRadius: '6px' }}>
                      {profileData.age} yrs old
                    </span>
                  )}
                </div>
              </div>

              {profileData.role === 'PATIENT' && (
                <>
                  <div className="form-group">
                    <label className="form-label" htmlFor="profile-gender">Gender</label>
                    <select
                      id="profile-gender"
                      className="form-input"
                      value={profileData.gender}
                      onChange={(e) => setProfileData({ ...profileData, gender: e.target.value })}
                    >
                      <option value="">Select Gender</option>
                      <option value="Male">Male</option>
                      <option value="Female">Female</option>
                      <option value="Non-Binary">Non-Binary</option>
                      <option value="Other">Other</option>
                      <option value="Prefer not to say">Prefer not to say</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="form-label" htmlFor="profile-address">Address</label>
                    <input
                      id="profile-address"
                      type="text"
                      className="form-input"
                      placeholder="Street, City, Postal Code"
                      value={profileData.address}
                      onChange={(e) => setProfileData({ ...profileData, address: e.target.value })}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label" htmlFor="profile-emg-name">Emergency Contact Name</label>
                    <input
                      id="profile-emg-name"
                      type="text"
                      className="form-input"
                      placeholder="e.g. Next of Kin"
                      value={profileData.emergency_contact_name}
                      onChange={(e) => setProfileData({ ...profileData, emergency_contact_name: e.target.value })}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label" htmlFor="profile-emg-phone">Emergency Contact Phone</label>
                    <input
                      id="profile-emg-phone"
                      type="tel"
                      className="form-input"
                      placeholder="+1-555-0199"
                      value={profileData.emergency_contact_phone}
                      onChange={(e) => setProfileData({ ...profileData, emergency_contact_phone: e.target.value })}
                    />
                  </div>
                </>
              )}
            </div>

            <div style={{ marginTop: '1.75rem', display: 'flex', gap: '0.75rem' }}>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* TAB 2: Medical Profile (PATIENTS) */}
      {currentTab === 'medical' && profileData.role === 'PATIENT' && (
        <div className="card" style={{ padding: '2rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.5rem' }}>
            <h2 style={{ fontSize: '1.3rem', fontWeight: 700, margin: 0, color: 'var(--text-main)' }}>
              Medical History & Health Profile
            </h2>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', background: '#f8fafc', padding: '4px 8px', borderRadius: '4px', border: '1px solid #e2e8f0' }}>
              🔒 Protected Health Data
            </span>
          </div>

          <form onSubmit={handleSaveMedicalProfile}>
            <div className="grid-3" style={{ gap: '1rem', marginBottom: '1.25rem' }}>
              <div className="form-group">
                <label className="form-label" htmlFor="med-blood-group">Blood Group</label>
                <select
                  id="med-blood-group"
                  className="form-input"
                  value={medicalData.blood_group}
                  onChange={(e) => setMedicalData({ ...medicalData, blood_group: e.target.value })}
                >
                  <option value="">Select Group</option>
                  <option value="A+">A+</option>
                  <option value="A-">A-</option>
                  <option value="B+">B+</option>
                  <option value="B-">B-</option>
                  <option value="O+">O+</option>
                  <option value="O-">O-</option>
                  <option value="AB+">AB+</option>
                  <option value="AB-">AB-</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="med-height">Height (cm)</label>
                <input
                  id="med-height"
                  type="number"
                  step="0.1"
                  min="30"
                  max="300"
                  className="form-input"
                  placeholder="e.g. 175"
                  value={medicalData.height_cm}
                  onChange={(e) => setMedicalData({ ...medicalData, height_cm: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="med-weight">Weight (kg)</label>
                <input
                  id="med-weight"
                  type="number"
                  step="0.1"
                  min="1"
                  max="500"
                  className="form-input"
                  placeholder="e.g. 70"
                  value={medicalData.weight_kg}
                  onChange={(e) => setMedicalData({ ...medicalData, weight_kg: e.target.value })}
                />
              </div>
            </div>

            <div className="grid-2" style={{ gap: '1.25rem', marginBottom: '1.25rem' }}>
              <div className="form-group">
                <label className="form-label" htmlFor="med-allergies">Allergies</label>
                <textarea
                  id="med-allergies"
                  className="form-input"
                  rows={2}
                  placeholder="e.g. Penicillin, Peanuts, Sulfa drugs"
                  value={medicalData.allergies}
                  onChange={(e) => setMedicalData({ ...medicalData, allergies: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="med-conditions">Existing / Chronic Conditions</label>
                <textarea
                  id="med-conditions"
                  className="form-input"
                  rows={2}
                  placeholder="e.g. Asthma, Hypertension, Diabetes Type 2"
                  value={medicalData.chronic_conditions}
                  onChange={(e) => setMedicalData({ ...medicalData, chronic_conditions: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="med-medications">Current Medications</label>
                <textarea
                  id="med-medications"
                  className="form-input"
                  rows={2}
                  placeholder="e.g. Metformin 500mg daily, Inhaler as needed"
                  value={medicalData.current_medications}
                  onChange={(e) => setMedicalData({ ...medicalData, current_medications: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="med-surgeries">Past Surgeries / Procedures</label>
                <textarea
                  id="med-surgeries"
                  className="form-input"
                  rows={2}
                  placeholder="e.g. Appendectomy (2018), Knee Arthroscopy (2021)"
                  value={medicalData.past_surgeries}
                  onChange={(e) => setMedicalData({ ...medicalData, past_surgeries: e.target.value })}
                />
              </div>
            </div>

            <div className="form-group" style={{ marginBottom: '1.25rem' }}>
              <label className="form-label" htmlFor="med-family-history">Family Medical History</label>
              <textarea
                id="med-family-history"
                className="form-input"
                rows={2}
                placeholder="e.g. Maternal history of cardiac conditions"
                value={medicalData.family_history}
                onChange={(e) => setMedicalData({ ...medicalData, family_history: e.target.value })}
              />
            </div>

            <div className="form-group" style={{ marginBottom: '1.5rem' }}>
              <label className="form-label" htmlFor="med-notes">General Health & Medical Notes</label>
              <textarea
                id="med-notes"
                className="form-input"
                rows={3}
                placeholder="Any additional information relevant to your care..."
                value={medicalData.medical_notes}
                onChange={(e) => setMedicalData({ ...medicalData, medical_notes: e.target.value })}
              />
            </div>

            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Saving...' : 'Save Medical Profile'}
            </button>
          </form>
        </div>
      )}

      {/* TAB 3: Professional Profile (DOCTORS) */}
      {currentTab === 'professional' && profileData.role === 'DOCTOR' && (
        <div className="card" style={{ padding: '2rem' }}>
          <h2 style={{ fontSize: '1.3rem', fontWeight: 700, marginBottom: '1.25rem', color: 'var(--text-main)' }}>
            Clinical & Professional Settings
          </h2>
          <form onSubmit={handleSaveBasicProfile}>
            <div className="form-group" style={{ marginBottom: '1.25rem' }}>
              <label className="form-label" htmlFor="doc-specialization">Medical Specialization</label>
              <input
                id="doc-specialization"
                type="text"
                className="form-input"
                required
                value={profileData.specialization}
                onChange={(e) => setProfileData({ ...profileData, specialization: e.target.value })}
              />
            </div>

            <div className="form-group" style={{ marginBottom: '1.25rem' }}>
              <label className="form-label" htmlFor="doc-bio">Professional Biography</label>
              <textarea
                id="doc-bio"
                className="form-input"
                rows={4}
                placeholder="Describe your medical education, experience, and clinical interests..."
                value={profileData.bio}
                onChange={(e) => setProfileData({ ...profileData, bio: e.target.value })}
              />
            </div>

            <div className="form-group" style={{ marginBottom: '1.5rem' }}>
              <label className="form-label" htmlFor="doc-slot-duration">Default Slot Duration (Minutes)</label>
              <input
                id="doc-slot-duration"
                type="number"
                disabled
                className="form-input"
                value={profileData.slot_duration}
                style={{ background: '#f1f5f9', cursor: 'not-allowed' }}
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '3px', display: 'block' }}>
                Slot durations are managed via the Doctor Console schedule settings.
              </span>
            </div>

            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Saving...' : 'Save Professional Profile'}
            </button>
          </form>
        </div>
      )}

      {/* TAB 4: Appointment History */}
      {currentTab === 'appointments' && (
        <div className="card" style={{ padding: '2rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
            <h2 style={{ fontSize: '1.3rem', fontWeight: 700, margin: 0, color: 'var(--text-main)' }}>
              Appointment History
            </h2>

            {/* Filter Buttons */}
            <div style={{ display: 'flex', gap: '0.35rem' }}>
              {['all', 'upcoming', 'past', 'cancelled'].map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => setApptFilter(f)}
                  className={`btn btn-sm ${apptFilter === f ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ textTransform: 'capitalize' }}
                >
                  {f} {f === 'all' ? `(${appointments.total})` : `(${appointments[f]?.length || 0})`}
                </button>
              ))}
            </div>
          </div>

          {getFilteredAppointments().length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {getFilteredAppointments().map((appt) => (
                <div
                  key={appt.id}
                  style={{
                    border: '1px solid var(--border)',
                    borderRadius: '8px',
                    padding: '1.25rem',
                    background: '#ffffff',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    flexWrap: 'wrap',
                    gap: '1rem',
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                      <span style={{ fontWeight: 700, fontSize: '1.05rem', color: 'var(--text-main)' }}>
                        {profileData.role === 'PATIENT' ? formatDoctorName(appt.doctor_name) : appt.patient_name}
                      </span>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', background: '#f1f5f9', padding: '2px 6px', borderRadius: '4px' }}>
                        {appt.doctor_specialization}
                      </span>
                    </div>

                    <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
                      📅 {new Date(appt.start_time).toLocaleDateString(undefined, { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' })} at{' '}
                      {new Date(appt.start_time).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                    </div>

                    {appt.chief_complaint && (
                      <div style={{ fontSize: '0.85rem', color: '#334155' }}>
                        <strong>Reason:</strong> {appt.chief_complaint}
                      </div>
                    )}

                    {appt.cancellation_reason && (
                      <div style={{ fontSize: '0.85rem', color: '#b91c1c', marginTop: '0.25rem' }}>
                        <strong>Reason:</strong> {appt.cancellation_reason}
                      </div>
                    )}
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.5rem' }}>
                    <span
                      style={{
                        padding: '4px 10px',
                        borderRadius: '6px',
                        fontSize: '0.8rem',
                        fontWeight: 700,
                        background:
                          appt.status === 'CONFIRMED'
                            ? '#ecfdf5'
                            : appt.status === 'CANCELLED' || appt.status === 'DECLINED'
                            ? '#fee2e2'
                            : appt.status === 'COMPLETED'
                            ? '#eff6ff'
                            : '#f8fafc',
                        color:
                          appt.status === 'CONFIRMED'
                            ? '#047857'
                            : appt.status === 'CANCELLED' || appt.status === 'DECLINED'
                            ? '#b91c1c'
                            : appt.status === 'COMPLETED'
                            ? '#1d4ed8'
                            : '#475569',
                      }}
                    >
                      {appt.status}
                    </span>

                    {appt.has_prescription && (
                      <span style={{ fontSize: '0.75rem', color: '#047857', fontWeight: 600 }}>
                        ✓ Digital Rx Issued
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '2.5rem', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
              <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.95rem' }}>
                No {apptFilter !== 'all' ? apptFilter : ''} appointment history found.
              </p>
            </div>
          )}
        </div>
      )}

      {/* TAB 5: Change Password */}
      {currentTab === 'password' && (
        <div className="card" style={{ padding: '2rem', maxWidth: '520px' }}>
          <h2 style={{ fontSize: '1.3rem', fontWeight: 700, marginBottom: '1.25rem', color: 'var(--text-main)' }}>
            Change Password
          </h2>
          <form onSubmit={handleChangePassword}>
            <div className="form-group" style={{ marginBottom: '1.25rem' }}>
              <label className="form-label" htmlFor="current-pwd">Current Password *</label>
              <input
                id="current-pwd"
                type={showPasswords ? 'text' : 'password'}
                required
                className="form-input"
                value={passwordForm.current_password}
                onChange={(e) => setPasswordForm({ ...passwordForm, current_password: e.target.value })}
              />
            </div>

            <div className="form-group" style={{ marginBottom: '1.25rem' }}>
              <label className="form-label" htmlFor="new-pwd">New Password * (Min 8 characters)</label>
              <input
                id="new-pwd"
                type={showPasswords ? 'text' : 'password'}
                required
                minLength={8}
                className="form-input"
                value={passwordForm.new_password}
                onChange={(e) => setPasswordForm({ ...passwordForm, new_password: e.target.value })}
              />
            </div>

            <div className="form-group" style={{ marginBottom: '1.25rem' }}>
              <label className="form-label" htmlFor="confirm-pwd">Confirm New Password *</label>
              <input
                id="confirm-pwd"
                type={showPasswords ? 'text' : 'password'}
                required
                minLength={8}
                className="form-input"
                value={passwordForm.confirm_password}
                onChange={(e) => setPasswordForm({ ...passwordForm, confirm_password: e.target.value })}
              />
            </div>

            <div style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <input
                id="show-passwords-toggle"
                type="checkbox"
                checked={showPasswords}
                onChange={(e) => setShowPasswords(e.target.checked)}
              />
              <label htmlFor="show-passwords-toggle" style={{ fontSize: '0.85rem', color: 'var(--text-muted)', cursor: 'pointer' }}>
                Show password characters
              </label>
            </div>

            <button type="submit" className="btn btn-primary" disabled={saving} style={{ width: '100%' }}>
              {saving ? 'Updating Password...' : 'Change Password'}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
