import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { patientApi, doctorApi, appointmentApi, clinicalApi, calendarApi, medicineApi, generateIdempotencyKey } from '../api/client';
import { formatDoctorName } from '../utils/format';
import { ProfileAvatar } from '../components/ProfileAvatar';

export function PatientDashboard() {
  const { user } = useAuth();
  const [profile, setProfile] = useState(null);
  const [doctors, setDoctors] = useState([]);
  const [myAppointments, setMyAppointments] = useState([]);
  const [myReminders, setMyReminders] = useState([]);
  const [calStatus, setCalStatus] = useState({ connected: false });
  const [activeTab, setActiveTab] = useState('book'); // 'book' | 'appointments' | 'medications' | 'medicines'
  const [searchSpec, setSearchSpec] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Medicine Knowledge State
  const [patientMedQuery, setPatientMedQuery] = useState('');
  const [patientMedResults, setPatientMedResults] = useState([]);
  const [patientSelectedMed, setPatientSelectedMed] = useState(null);
  const [searchingPatientMed, setSearchingPatientMed] = useState(false);
  const [loadingPatientMedDetails, setLoadingPatientMedDetails] = useState(false);

  // Booking Flow State
  const [selectedDoctor, setSelectedDoctor] = useState(null);
  const [selectedDate, setSelectedDate] = useState(() => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    return tomorrow.toISOString().split('T')[0];
  });
  const [availableSlots, setAvailableSlots] = useState([]);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [activeHold, setActiveHold] = useState(null);
  const [holdTimer, setHoldTimer] = useState(0);
  const [holdingSlot, setHoldingSlot] = useState(false);
  const [confirming, setConfirming] = useState(false);

  // Symptoms Submission Modal State
  const [symptomTarget, setSymptomTarget] = useState(null);
  const [symptomsText, setSymptomsText] = useState('');
  const [chiefComplaint, setChiefComplaint] = useState('');
  const [savingSymptoms, setSavingSymptoms] = useState(false);

  // Clinical Consultation Viewer Modal State
  const [consultationTarget, setConsultationTarget] = useState(null);
  const [consultationData, setConsultationData] = useState({ notes: null, rx: null, ai: [] });
  const [loadingConsultation, setLoadingConsultation] = useState(false);

  // Reschedule & Alternatives Flow State
  const [rescheduleTarget, setRescheduleTarget] = useState(null);
  const [alternativeSlots, setAlternativeSlots] = useState([]);
  const [loadingAlternatives, setLoadingAlternatives] = useState(false);

  // Cancel Flow State
  const [cancelTarget, setCancelTarget] = useState(null);
  const [cancelReason, setCancelReason] = useState('');
  const [cancelling, setCancelling] = useState(false);

  const loadData = async () => {
    try {
      const [profileData, doctorsData, appointmentsData, remindersData, calStatusData] = await Promise.all([
        patientApi.getMe(),
        doctorApi.list(searchSpec),
        appointmentApi.list(),
        clinicalApi.getMyMedicationReminders().catch(() => []),
        calendarApi.getStatus().catch(() => ({ connected: false })),
      ]);
      setProfile(profileData);
      setDoctors(doctorsData);
      setMyAppointments(appointmentsData);
      setMyReminders(remindersData);
      setCalStatus(calStatusData);
    } catch (err) {
      console.error('Error fetching dashboard data:', err);
      setError(err.message || 'Failed to load patient profile data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [searchSpec]);

  // Hold Timer countdown effect
  useEffect(() => {
    if (holdTimer <= 0) {
      if (activeHold) {
        setActiveHold(null);
        setError('Your slot hold has expired. Please select a slot again.');
      }
      return;
    }
    const interval = setInterval(() => {
      setHoldTimer((prev) => prev - 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [holdTimer, activeHold]);

  const handleOpenBooking = async (doctor) => {
    setSelectedDoctor(doctor);
    setActiveHold(null);
    setHoldTimer(0);
    fetchSlots(doctor.id, selectedDate);
  };

  const fetchSlots = async (doctorId, dateStr) => {
    setLoadingSlots(true);
    setError(null);
    try {
      const data = await doctorApi.getAvailability(doctorId, dateStr);
      setAvailableSlots(data.slots || []);
    } catch (err) {
      setError(err.message || 'Failed to load available slots');
      setAvailableSlots([]);
    } finally {
      setLoadingSlots(false);
    }
  };

  const handleSelectSlot = async (slot) => {
    if (!slot.available) return;
    setError(null);
    setHoldingSlot(true);
    try {
      const idempKey = generateIdempotencyKey();
      const holdRes = await appointmentApi.hold(
        {
          doctor_id: selectedDoctor.id,
          start_time: slot.start_time,
        },
        idempKey
      );
      setActiveHold(holdRes);
      setHoldTimer(holdRes.remaining_seconds || 300);
    } catch (err) {
      setError(err.message || 'Failed to hold slot. It may have just been booked.');
      fetchSlots(selectedDoctor.id, selectedDate);
    } finally {
      setHoldingSlot(false);
    }
  };

  const handleConfirmHold = async () => {
    if (!activeHold) return;
    setConfirming(true);
    setError(null);
    try {
      const idempKey = generateIdempotencyKey();
      const confirmed = await appointmentApi.confirm(activeHold.appointment_id, idempKey);
      setSuccessMsg(`Appointment confirmed with Dr. ${confirmed.doctor_name || selectedDoctor.name}!`);
      setActiveHold(null);
      setSelectedDoctor(null);
      setHoldTimer(0);
      await loadData();
      setActiveTab('appointments');
    } catch (err) {
      setError(err.message || 'Failed to confirm appointment');
    } finally {
      setConfirming(false);
    }
  };

  const handleSubmitSymptoms = async (e) => {
    e.preventDefault();
    if (!symptomTarget) return;
    setSavingSymptoms(true);
    setError(null);
    try {
      await clinicalApi.submitSymptoms(symptomTarget.id, {
        symptoms: symptomsText,
        chief_complaint: chiefComplaint || null,
      });
      setSuccessMsg('Symptoms submitted successfully! Clinical AI is preparing a pre-visit summary for the doctor.');
      setSymptomTarget(null);
      setSymptomsText('');
      setChiefComplaint('');
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to submit symptoms');
    } finally {
      setSavingSymptoms(false);
    }
  };

  const handleOpenConsultation = async (app) => {
    setConsultationTarget(app);
    setLoadingConsultation(true);
    try {
      const [notes, rx, ai] = await Promise.all([
        clinicalApi.getClinicalNotes(app.id).catch(() => null),
        clinicalApi.getPrescription(app.id).catch(() => null),
        clinicalApi.getAISummaries(app.id).catch(() => []),
      ]);
      setConsultationData({ notes, rx, ai });
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingConsultation(false);
    }
  };

  const handleConnectCalendar = async () => {
    try {
      const res = await calendarApi.getAuthUrl();
      // Simulate OAuth callback connection
      await calendarApi.callback("mock_auth_code_sample");
      setSuccessMsg('Google Calendar connected successfully! Your appointments will automatically synchronize.');
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to connect Google Calendar');
    }
  };

  const handleDisconnectCalendar = async () => {
    try {
      await calendarApi.disconnect();
      setSuccessMsg('Google Calendar disconnected.');
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to disconnect calendar');
    }
  };

  // Cancel flow
  const handleCancelAppointment = async () => {
    if (!cancelTarget) return;
    setCancelling(true);
    try {
      await appointmentApi.cancel(cancelTarget.id, cancelReason || 'Cancelled by patient');
      setSuccessMsg('Appointment cancelled successfully.');
      setCancelTarget(null);
      setCancelReason('');
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to cancel appointment');
    } finally {
      setCancelling(false);
    }
  };

  // Reschedule & Alternative Slots flow
  const handleOpenReschedule = async (app) => {
    setRescheduleTarget(app);
    setLoadingAlternatives(true);
    setError(null);
    try {
      const altData = await appointmentApi.getAlternatives(app.id);
      setAlternativeSlots(altData.suggestions || []);
    } catch (err) {
      setError(err.message || 'Failed to load alternative suggestions');
    } finally {
      setLoadingAlternatives(false);
    }
  };

  const handleSelectRescheduleSlot = async (slot) => {
    if (!rescheduleTarget) return;
    setError(null);
    try {
      const idempKey = generateIdempotencyKey();
      await appointmentApi.reschedule(rescheduleTarget.id, slot.start_time, idempKey);
      setSuccessMsg('Appointment rescheduled successfully!');
      setRescheduleTarget(null);
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to reschedule appointment');
    }
  };

  const handleSearchPatientMed = async (e) => {
    e.preventDefault();
    if (!patientMedQuery.trim() || patientMedQuery.trim().length < 2) return;
    setSearchingPatientMed(true);
    setError(null);
    try {
      const data = await medicineApi.search(patientMedQuery.trim());
      setPatientMedResults(data.results || []);
      if (data.results && data.results.length > 0) {
        handleSelectPatientMed(data.results[0].rxcui);
      } else {
        setPatientSelectedMed(null);
      }
    } catch (err) {
      setError(err.message || 'Medicine lookup failed');
    } finally {
      setSearchingPatientMed(false);
    }
  };

  const handleSelectPatientMed = async (rxcui) => {
    setLoadingPatientMedDetails(true);
    try {
      const details = await medicineApi.getDetails(rxcui);
      setPatientSelectedMed(details);
    } catch (err) {
      setError(err.message || 'Failed to load medicine details');
    } finally {
      setLoadingPatientMedDetails(false);
    }
  };

  const formatTimer = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  const getStatusBadge = (app) => {
    if (typeof app === 'string') {
      const status = app;
      if (status === 'CONFIRMED') return <span className="user-badge" style={{ background: '#dcfce7', color: '#15803d' }}>Confirmed</span>;
      if (status === 'HELD') return <span className="user-badge" style={{ background: '#fef3c7', color: '#b45309' }}>Temporary Hold</span>;
      if (status === 'RESCHEDULED') return <span className="user-badge" style={{ background: '#e0e7ff', color: '#4338ca' }}>Rescheduled</span>;
      if (status === 'CANCELLED') return <span className="user-badge" style={{ background: '#fee2e2', color: '#b91c1c' }}>Cancelled</span>;
      if (status === 'COMPLETED') return <span className="user-badge" style={{ background: '#f3e8ff', color: '#7e22ce' }}>Completed</span>;
      return <span className="user-badge">{status}</span>;
    }
    if (app.status === 'CANCELLED') {
      if (app.cancellation_reason && app.cancelled_by_user_id) {
        return <span className="user-badge" style={{ background: '#fee2e2', color: '#b91c1c', fontWeight: 700 }}>Doctor Declined</span>;
      }
      return <span className="user-badge" style={{ background: '#fee2e2', color: '#b91c1c' }}>Cancelled</span>;
    }
    switch (app.status) {
      case 'CONFIRMED':
        return <span className="user-badge" style={{ background: '#dcfce7', color: '#15803d' }}>Confirmed</span>;
      case 'HELD':
        return <span className="user-badge" style={{ background: '#fef3c7', color: '#b45309' }}>Temporary Hold</span>;
      case 'RESCHEDULED':
        return <span className="user-badge" style={{ background: '#e0e7ff', color: '#4338ca' }}>Rescheduled</span>;
      case 'COMPLETED':
        return <span className="user-badge" style={{ background: '#f3e8ff', color: '#7e22ce' }}>Completed</span>;
      case 'NO_SHOW':
        return <span className="user-badge" style={{ background: '#f1f5f9', color: '#475569' }}>No-Show</span>;
      default:
        return <span className="user-badge">{app.status}</span>;
    }
  };

  if (loading) {
    return <div style={{ textAlign: 'center', padding: '3rem' }}>Loading patient portal...</div>;
  }

  return (
    <div className="main-content">
      <div style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <ProfileAvatar
            src={user?.profile_image_url}
            name={user?.name}
            role="PATIENT"
            size={48}
          />
          <div>
            <h1 style={{ fontSize: '1.75rem', fontWeight: 800, margin: 0 }}>Welcome, {user?.name}</h1>
            <p style={{ color: 'var(--text-muted)', margin: '0.2rem 0 0 0' }}>Patient Portal • Healthcare Appointment Manager</p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          {calStatus.connected ? (
            <button className="btn btn-secondary btn-sm" onClick={handleDisconnectCalendar} title="Google Calendar Synced">
              📅 Synced with Google Calendar (Disconnect)
            </button>
          ) : (
            <button className="btn btn-secondary btn-sm" onClick={handleConnectCalendar}>
              📅 Connect Google Calendar
            </button>
          )}
          <button
            className={`btn ${activeTab === 'book' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('book')}
          >
            Find Doctor & Book
          </button>
          <button
            className={`btn ${activeTab === 'appointments' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('appointments')}
          >
            My Appointments ({myAppointments.length})
          </button>
          <button
            className={`btn ${activeTab === 'medications' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('medications')}
          >
            Medication Schedule ({myReminders.length})
          </button>
          <button
            className={`btn ${activeTab === 'medicines' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('medicines')}
          >
            💊 Medicine Information
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {successMsg && <div className="alert alert-success">{successMsg}</div>}

      {/* Tab 1: Booking Flow */}
      {activeTab === 'book' && (
        <>
          <div className="card" style={{ marginBottom: '1.5rem' }}>
            <div className="card-header">
              <div>
                <h3 className="card-title">Search Certified Doctors</h3>
                <p className="card-subtitle">Filter by medical specialty to schedule an in-person or telehealth visit</p>
              </div>
              <div style={{ width: '280px' }}>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Filter specialization (e.g. Cardiology)..."
                  value={searchSpec}
                  onChange={(e) => setSearchSpec(e.target.value)}
                />
              </div>
            </div>

            <div className="grid-3">
              {doctors.map((doc) => (
                <div key={doc.id} className="card" style={{ background: '#f8fafc', borderColor: '#cbd5e1' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
                    <ProfileAvatar
                      src={doc.profile_image_url}
                      name={doc.name}
                      role="DOCTOR"
                      size={42}
                    />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <h4 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {formatDoctorName(doc.name)}
                      </h4>
                      <span className="user-badge badge-doctor" style={{ fontSize: '0.75rem', marginTop: '2px', display: 'inline-block' }}>
                        {doc.specialization}
                      </span>
                    </div>
                  </div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1rem', minHeight: '40px' }}>
                    {doc.bio || 'General practice specialist committed to patient well-being.'}
                  </p>
                  <div style={{ fontSize: '0.825rem', color: 'var(--text-main)', marginBottom: '1rem' }}>
                    <div>⏱️ <strong>Slot Duration:</strong> {doc.slot_duration} minutes</div>
                    <div>🗓️ <strong>Availability:</strong> {doc.working_hours?.length ? `${doc.working_hours.length} day(s) configured` : 'Standard Schedule'}</div>
                  </div>
                  <button
                    className="btn btn-primary btn-block btn-sm"
                    onClick={() => handleOpenBooking(doc)}
                  >
                    Select & Book Slot
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Modal / Booking Panel */}
          {selectedDoctor && (
            <div className="card" style={{ border: '2px solid var(--primary)', background: '#ffffff', marginBottom: '2rem' }}>
              <div className="card-header">
                <div>
                  <h3 className="card-title">Book Appointment with {formatDoctorName(selectedDoctor.name)}</h3>
                  <p className="card-subtitle">{selectedDoctor.specialization} • {selectedDoctor.slot_duration} min consultations</p>
                </div>
                <button className="btn btn-secondary btn-sm" onClick={() => setSelectedDoctor(null)}>
                  Close
                </button>
              </div>

              {/* Date Picker */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem' }}>
                <label style={{ fontWeight: 600, fontSize: '0.9rem' }}>Select Date:</label>
                <input
                  type="date"
                  className="form-input"
                  style={{ width: '200px' }}
                  value={selectedDate}
                  min={new Date().toISOString().split('T')[0]}
                  onChange={(e) => {
                    setSelectedDate(e.target.value);
                    fetchSlots(selectedDoctor.id, e.target.value);
                  }}
                />
              </div>

              {/* Active Temporary Hold Countdown Banner */}
              {activeHold && (
                <div className="alert alert-info" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                  <div>
                    <strong>Slot Held:</strong> {new Date(activeHold.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} on {new Date(activeHold.start_time).toLocaleDateString()}
                    <div style={{ fontSize: '0.825rem', marginTop: '0.2rem' }}>
                      Time remaining to confirm: <span style={{ fontWeight: 800, color: '#0369a1' }}>{formatTimer(holdTimer)}</span>
                    </div>
                  </div>
                  <button
                    className="btn btn-primary"
                    onClick={handleConfirmHold}
                    disabled={confirming || holdTimer <= 0}
                  >
                    {confirming ? 'Confirming...' : 'Confirm Appointment Now'}
                  </button>
                </div>
              )}

              {/* Available Slots Grid */}
              <h4 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '0.75rem' }}>Available Time Slots</h4>
              {loadingSlots ? (
                <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>Calculating dynamic availability...</p>
              ) : availableSlots.length === 0 ? (
                <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', padding: '1rem 0' }}>
                  No available consultation slots for this date (Doctor may be off-shift or on leave).
                </p>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: '0.75rem' }}>
                  {availableSlots.map((slot, idx) => {
                    const timeLabel = new Date(slot.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                    const isCurrentHold = activeHold && activeHold.start_time === slot.start_time;

                    return (
                      <button
                        key={idx}
                        disabled={!slot.available || holdingSlot}
                        onClick={() => handleSelectSlot(slot)}
                        style={{
                          padding: '0.75rem 0.5rem',
                          borderRadius: '8px',
                          border: isCurrentHold ? '2px solid var(--primary)' : '1px solid var(--border)',
                          background: isCurrentHold ? 'var(--primary-light)' : slot.available ? '#ffffff' : '#f1f5f9',
                          color: slot.available ? 'var(--text-main)' : 'var(--text-light)',
                          cursor: slot.available ? 'pointer' : 'not-allowed',
                          fontWeight: 600,
                          fontSize: '0.875rem',
                          textAlign: 'center',
                        }}
                      >
                        {timeLabel}
                        <div style={{ fontSize: '0.7rem', color: isCurrentHold ? 'var(--primary-dark)' : slot.available ? 'var(--success)' : 'var(--danger)' }}>
                          {isCurrentHold ? 'Holding' : slot.available ? 'Available' : 'Unavailable'}
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* Tab 2: My Appointments */}
      {activeTab === 'appointments' && (
        <div className="card">
          <div className="card-header">
            <div>
              <h3 className="card-title">My Scheduled Appointments</h3>
              <p className="card-subtitle">Manage upcoming visits, submit pre-visit symptoms, and view consultation summaries</p>
            </div>
          </div>

          {myAppointments.length === 0 ? (
            <p style={{ color: 'var(--text-muted)', padding: '2rem 0', textAlign: 'center' }}>
              You have no scheduled appointments yet. Use the "Find Doctor & Book" tab above.
            </p>
          ) : (
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Doctor</th>
                    <th>Specialization</th>
                    <th>Date & Time</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {myAppointments.map((app) => (
                    <tr key={app.id}>
                      <td style={{ fontWeight: 600 }}>{formatDoctorName(app.doctor_name)}</td>
                      <td>
                        <span className="user-badge badge-doctor">{app.doctor_specialization}</span>
                      </td>
                      <td>
                        <div>{new Date(app.start_time).toLocaleDateString()}</div>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                          {new Date(app.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} -{' '}
                          {new Date(app.end_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>
                      </td>
                      <td>
                        <div>{getStatusBadge(app)}</div>
                        {app.status === 'CANCELLED' && app.cancellation_reason && (
                          <div style={{ fontSize: '0.75rem', color: '#b91c1c', marginTop: '0.25rem', maxWidth: '240px' }}>
                            <strong>Reason:</strong> {app.cancellation_reason}
                          </div>
                        )}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                          {app.status === 'CONFIRMED' && (
                            <>
                              <button
                                className="btn btn-secondary btn-sm"
                                onClick={() => setSymptomTarget(app)}
                              >
                                📝 Submit Symptoms
                              </button>
                              <button
                                className="btn btn-secondary btn-sm"
                                onClick={() => handleOpenReschedule(app)}
                              >
                                Reschedule
                              </button>
                              <button
                                className="btn btn-danger btn-sm"
                                onClick={() => setCancelTarget(app)}
                              >
                                Cancel
                              </button>
                            </>
                          )}
                          {app.status === 'CANCELLED' && (
                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={() => setActiveTab('book')}
                            >
                              🔍 Find Another Slot
                            </button>
                          )}
                          {app.status === 'COMPLETED' && (
                            <button
                              className="btn btn-primary btn-sm"
                              onClick={() => handleOpenConsultation(app)}
                            >
                              📋 View Visit Summary & Rx
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Medication Schedule */}
      {activeTab === 'medications' && (
        <div className="card">
          <div className="card-header">
            <div>
              <h3 className="card-title">Prescription Medication Reminders</h3>
              <p className="card-subtitle">Your personalized daily dosage schedule generated from doctor prescriptions</p>
            </div>
          </div>

          {myReminders.length === 0 ? (
            <p style={{ color: 'var(--text-muted)', padding: '2rem 0', textAlign: 'center' }}>
              No active medication reminders found. Reminders appear automatically when a doctor prescribes medication.
            </p>
          ) : (
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Medication Name</th>
                    <th>Dosage</th>
                    <th>Scheduled Time</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {myReminders.map((rem) => (
                    <tr key={rem.id}>
                      <td style={{ fontWeight: 600 }}>{rem.medication_name}</td>
                      <td>{rem.dosage}</td>
                      <td>
                        <div>{new Date(rem.scheduled_at).toLocaleDateString()}</div>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                          {new Date(rem.scheduled_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>
                      </td>
                      <td>
                        <span className="user-badge" style={{
                          background: rem.status === 'SENT' ? '#dcfce7' : rem.status === 'PENDING' ? '#fef3c7' : '#f1f5f9',
                          color: rem.status === 'SENT' ? '#15803d' : rem.status === 'PENDING' ? '#b45309' : '#475569',
                        }}>
                          {rem.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 4: Medicine Information & Clinical Knowledge */}
      {activeTab === 'medicines' && (
        <div>
          <div className="card" style={{ marginBottom: '1.5rem' }}>
            <div className="card-header">
              <div>
                <h3 className="card-title">Medicine Knowledge & Official Labeling</h3>
                <p className="card-subtitle">Search clinical drugs to inspect active substances, official FDA/DailyMed indications, and safety warnings</p>
              </div>
            </div>

            <form onSubmit={handleSearchPatientMed} style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
              <input
                type="text"
                className="form-input"
                placeholder="Search medicine (e.g. Paracetamol, Metformin, Amoxicillin)..."
                value={patientMedQuery}
                onChange={(e) => setPatientMedQuery(e.target.value)}
              />
              <button type="submit" className="btn btn-primary" disabled={searchingPatientMed || patientMedQuery.trim().length < 2}>
                {searchingPatientMed ? 'Searching...' : 'Search'}
              </button>
            </form>

            {/* Suggestions Chips */}
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>Quick search:</span>
              {['Paracetamol', 'Amoxicillin', 'Ibuprofen', 'Metformin', 'Cetirizine'].map((pill) => (
                <button
                  key={pill}
                  type="button"
                  className="btn btn-secondary btn-sm"
                  style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
                  onClick={() => {
                    setPatientMedQuery(pill);
                    medicineApi.search(pill).then((data) => {
                      setPatientMedResults(data.results || []);
                      if (data.results && data.results.length > 0) handleSelectPatientMed(data.results[0].rxcui);
                    });
                  }}
                >
                  {pill}
                </button>
              ))}
            </div>

            {/* Results pills list */}
            {patientMedResults.length > 0 && (
              <div style={{ marginTop: '1rem', display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                {patientMedResults.map((r) => (
                  <button
                    key={r.rxcui}
                    type="button"
                    className={`btn btn-sm ${patientSelectedMed?.rxcui === r.rxcui ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => handleSelectPatientMed(r.rxcui)}
                  >
                    {r.name}
                  </button>
                ))}
              </div>
            )}
          </div>

          {loadingPatientMedDetails && (
            <div className="card" style={{ textAlign: 'center', padding: '2rem' }}>
              <p style={{ color: 'var(--text-muted)' }}>Retrieving official pharmacological details from RxNorm & DailyMed...</p>
            </div>
          )}

          {!loadingPatientMedDetails && patientSelectedMed && (
            <div className="card" style={{ padding: '1.75rem', marginBottom: '1.5rem' }}>
              {/* Header */}
              <div style={{ borderBottom: '1px solid var(--border)', paddingBottom: '1rem', marginBottom: '1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.75rem' }}>
                <div>
                  <h3 style={{ fontSize: '1.4rem', fontWeight: 800, margin: 0, color: 'var(--text-main)' }}>{patientSelectedMed.name}</h3>
                  {patientSelectedMed.generic_name && (
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '0.25rem', marginBottom: 0 }}>
                      Generic name: <strong style={{ color: 'var(--text-main)' }}>{patientSelectedMed.generic_name}</strong>
                    </p>
                  )}
                  {patientSelectedMed.active_ingredients?.length > 0 && (
                    <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.4rem' }}>
                      Active ingredient: <strong style={{ color: 'var(--text-main)' }}>{patientSelectedMed.active_ingredients.join(', ')}</strong>
                    </div>
                  )}
                </div>
                <span className="user-badge" style={{ background: '#ecfdf5', color: '#047857', border: '1px solid #a7f3d0', fontWeight: 600, fontSize: '0.8rem' }}>
                  ✓ {patientSelectedMed.source?.name || 'DailyMed / RxNorm'}
                </span>
              </div>

              {/* 1. What is this medicine used for? */}
              <div style={{ marginBottom: '1.5rem' }}>
                <h4 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.5rem', color: 'var(--text-main)' }}>
                  What is this medicine used for?
                </h4>
                {patientSelectedMed.uses?.length > 0 ? (
                  <ul style={{ paddingLeft: '1.25rem', margin: 0, fontSize: '0.9rem', color: 'var(--text-main)', lineHeight: 1.5 }}>
                    {patientSelectedMed.uses.map((u, idx) => (
                      <li key={idx} style={{ marginBottom: '0.35rem' }}>{u}</li>
                    ))}
                  </ul>
                ) : (
                  <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', margin: 0 }}>
                    Used according to labeled medical indications.
                  </p>
                )}

                {patientSelectedMed.ai_summary && (
                  <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '0.85rem 1rem', marginTop: '0.85rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                      <span style={{ fontWeight: 700, color: '#334155' }}>AI-generated simplified explanation</span>
                      <span>Source: Official medicine labeling</span>
                    </div>
                    <p style={{ fontSize: '0.875rem', color: '#1e293b', margin: 0, lineHeight: 1.5 }}>
                      {patientSelectedMed.ai_summary}
                    </p>
                  </div>
                )}
              </div>

              {/* 2. Medicine Snapshot */}
              <div style={{ background: '#f8fafc', borderRadius: '8px', padding: '1rem', marginBottom: '1.25rem', border: '1px solid #e2e8f0' }}>
                <div className="grid-2" style={{ gap: '1rem' }}>
                  <div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>Active ingredient</div>
                    <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-main)', marginTop: '2px' }}>
                      {patientSelectedMed.active_ingredients?.join(', ') || patientSelectedMed.name}
                    </div>
                  </div>

                  {patientSelectedMed.dosage_forms?.length > 0 && (
                    <div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, marginBottom: '4px' }}>Available forms</div>
                      <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                        {patientSelectedMed.dosage_forms.map((f, idx) => (
                          <span key={idx} style={{ background: '#ffffff', color: '#334155', padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem', border: '1px solid #cbd5e1' }}>
                            {f}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {patientSelectedMed.brand_names?.length > 0 && (
                  <div style={{ marginTop: '0.75rem', paddingTop: '0.5rem', borderTop: '1px solid #e2e8f0' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>Also known as</div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>* Brand names may vary by country</div>
                    </div>
                    <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                      {patientSelectedMed.brand_names.map((b, idx) => (
                        <span key={idx} style={{ background: '#ffffff', color: '#475569', padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem', border: '1px solid #cbd5e1' }}>
                          {b}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* 3. Important Safety Information */}
              <div style={{ marginBottom: '1.25rem' }}>
                <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#991b1b', marginBottom: '0.35rem' }}>
                  Important safety information
                </h4>
                <ul style={{ paddingLeft: '1.25rem', margin: 0, color: '#7f1d1d', fontSize: '0.85rem', lineHeight: 1.5 }}>
                  {patientSelectedMed.warnings?.map((w, idx) => (
                    <li key={idx} style={{ marginBottom: '0.25rem' }}>{w}</li>
                  ))}
                </ul>
              </div>

              {/* 4. When Should I Ask a Doctor or Pharmacist? */}
              <div style={{ background: '#f8fafc', padding: '0.85rem 1rem', borderRadius: '6px', border: '1px solid #e2e8f0', marginBottom: '1.25rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                <strong style={{ color: 'var(--text-main)', display: 'block', marginBottom: '0.25rem' }}>When should I ask a doctor or pharmacist?</strong>
                <ul style={{ paddingLeft: '1.15rem', margin: 0, lineHeight: 1.5 }}>
                  <li>You are unsure whether this medicine is right for your symptoms.</li>
                  <li>You take other medicines or have an existing medical condition.</li>
                  <li>You are pregnant, planning pregnancy, or breastfeeding.</li>
                </ul>
              </div>

              {/* 5. Expandable Technical Information */}
              <details style={{ borderTop: '1px solid var(--border)', paddingTop: '0.75rem', marginBottom: '1rem', cursor: 'pointer', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                <summary style={{ fontWeight: 600, color: 'var(--text-main)' }}>Technical details ⌄</summary>
                <div style={{ marginTop: '0.5rem', lineHeight: 1.5 }}>
                  <div><strong>RxCUI:</strong> {patientSelectedMed.rxcui}</div>
                  <div><strong>Terminology Provider:</strong> NIH RxNorm & DailyMed Structured Product Labeling (SPL)</div>
                </div>
              </details>

              {/* Important Disclaimer */}
              <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '6px', padding: '0.75rem 1rem', fontSize: '0.75rem', color: '#64748b', lineHeight: 1.4 }}>
                <strong style={{ color: '#475569' }}>Important:</strong> {patientSelectedMed.disclaimer}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Symptoms Submission Modal */}
      {symptomTarget && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card" style={{ maxWidth: '500px', width: '90%' }}>
            <div className="card-header">
              <div>
                <h3 className="card-title">Pre-Visit Symptom Intake</h3>
                <p className="card-subtitle">Consultation with {formatDoctorName(symptomTarget.doctor_name)}</p>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={() => setSymptomTarget(null)}>✕</button>
            </div>

            <form onSubmit={handleSubmitSymptoms}>
              <div className="form-group">
                <label className="form-label">Describe your symptoms in detail *</label>
                <textarea
                  className="form-textarea"
                  rows={4}
                  placeholder="e.g. When did symptoms start? Any pain, fever, or breathing difficulty?"
                  value={symptomsText}
                  onChange={(e) => setSymptomsText(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Chief Complaint (Short summary)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Persistent cough and sore throat"
                  value={chiefComplaint}
                  onChange={(e) => setChiefComplaint(e.target.value)}
                />
              </div>
              <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setSymptomTarget(null)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={savingSymptoms}>
                  {savingSymptoms ? 'Analyzing...' : 'Submit Symptoms to Doctor'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Consultation Summary & Rx Modal */}
      {consultationTarget && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card" style={{ maxWidth: '640px', width: '90%', maxHeight: '85vh', overflowY: 'auto' }}>
            <div className="card-header">
              <div>
                <h3 className="card-title">Visit Outcomes & Prescription</h3>
                <p className="card-subtitle">{formatDoctorName(consultationTarget.doctor_name)} • {new Date(consultationTarget.start_time).toLocaleDateString()}</p>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={() => setConsultationTarget(null)}>✕</button>
            </div>

            {loadingConsultation ? (
              <p style={{ color: 'var(--text-muted)', padding: '2rem 0', textAlign: 'center' }}>Loading medical record...</p>
            ) : (
              <div>
                {/* AI Post-Visit Summary */}
                {consultationData.ai.find(a => a.summary_type === 'POST_VISIT') ? (
                  <div className="alert alert-info" style={{ marginBottom: '1.5rem', display: 'block' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                      <strong>✨ AI-Generated Patient Visit Summary</strong>
                      <span className="user-badge" style={{ background: '#e0f2fe', color: '#0369a1', fontSize: '0.75rem' }}>AI Synthesized</span>
                    </div>
                    <div style={{ marginTop: '0.5rem', whiteSpace: 'pre-line', fontSize: '0.85rem' }}>
                      {consultationData.ai.find(a => a.summary_type === 'POST_VISIT').content}
                    </div>
                  </div>
                ) : (
                  <div style={{ background: '#f8fafc', padding: '0.85rem', borderRadius: '8px', border: '1px solid var(--border)', marginBottom: '1.5rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    🤖 <em>Clinical AI is processing your post-visit summary in the background...</em>
                  </div>
                )}

                {/* Doctor Clinical Assessment */}
                <div style={{ marginBottom: '1.5rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <h4 style={{ fontSize: '0.95rem', fontWeight: 700 }}>🩺 Doctor's Authoritative Assessment & Diagnosis</h4>
                    <span className="user-badge" style={{ background: '#dcfce7', color: '#15803d', fontSize: '0.75rem' }}>Physician Certified</span>
                  </div>
                  <div style={{ background: '#f8fafc', padding: '0.75rem', borderRadius: '8px', border: '1px solid var(--border)', marginTop: '0.5rem' }}>
                    <div><strong>Primary Diagnosis:</strong> {consultationData.notes?.diagnosis || 'General Clinical Evaluation'}</div>
                    <div style={{ marginTop: '0.35rem', fontSize: '0.875rem', color: 'var(--text-main)' }}>{consultationData.notes?.notes || 'No written notes recorded.'}</div>
                  </div>
                </div>

                {/* Structured Prescription Table */}
                {consultationData.rx && consultationData.rx.medications?.length > 0 && (
                  <div>
                    <h4 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '0.5rem' }}>Prescribed Medications</h4>
                    <div className="table-container">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Medicine</th>
                            <th>Dosage</th>
                            <th>Frequency</th>
                            <th>Duration</th>
                            <th>Instructions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {consultationData.rx.medications.map((m) => (
                            <tr key={m.id}>
                              <td style={{ fontWeight: 600 }}>{m.name}</td>
                              <td>{m.dosage}</td>
                              <td>{m.frequency}</td>
                              <td>{m.start_date} to {m.end_date}</td>
                              <td>{m.instructions || 'As directed'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Reschedule Modal with Smart Alternatives */}
      {rescheduleTarget && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card" style={{ maxWidth: '540px', width: '90%' }}>
            <div className="card-header">
              <div>
                <h3 className="card-title">Reschedule Visit</h3>
                <p className="card-subtitle">Original: {new Date(rescheduleTarget.start_time).toLocaleString()}</p>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={() => setRescheduleTarget(null)}>✕</button>
            </div>

            <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.5rem' }}>Smart Alternative Suggestions:</h4>
            {loadingAlternatives ? (
              <p style={{ color: 'var(--text-muted)' }}>Calculating closest available slots...</p>
            ) : alternativeSlots.length === 0 ? (
              <p style={{ color: 'var(--text-muted)' }}>No alternative slots found nearby.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1.5rem' }}>
                {alternativeSlots.map((alt, idx) => (
                  <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.75rem', background: '#f8fafc', borderRadius: '8px', border: '1px solid var(--border)' }}>
                    <div>
                      <strong>{new Date(alt.start_time).toLocaleDateString()}</strong> at {new Date(alt.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      <div style={{ fontSize: '0.75rem', color: 'var(--primary)' }}>{alt.reason}</div>
                    </div>
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={() => handleSelectRescheduleSlot(alt)}
                    >
                      Reschedule Here
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Cancel Modal */}
      {cancelTarget && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card" style={{ maxWidth: '440px', width: '90%' }}>
            <div className="card-header">
              <h3 className="card-title">Cancel Appointment</h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setCancelTarget(null)}>✕</button>
            </div>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
              Are you sure you want to cancel your visit with {formatDoctorName(cancelTarget.doctor_name)} on {new Date(cancelTarget.start_time).toLocaleDateString()}?
            </p>
            <div className="form-group">
              <label className="form-label">Reason for cancellation:</label>
              <textarea
                className="form-textarea"
                rows={3}
                placeholder="Optional reason..."
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
              />
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
              <button className="btn btn-secondary" onClick={() => setCancelTarget(null)}>Keep Visit</button>
              <button className="btn btn-danger" onClick={handleCancelAppointment} disabled={cancelling}>
                {cancelling ? 'Cancelling...' : 'Confirm Cancellation'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
