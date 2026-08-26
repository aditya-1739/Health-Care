import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { patientApi, doctorApi, appointmentApi, clinicalApi, calendarApi, medicineApi, generateIdempotencyKey } from '../api/client';
import { formatDoctorName } from '../utils/format';
import { ProfileAvatar } from '../components/ProfileAvatar';

/* Clean SVG Icons */
const Icons = {
  Doctor: () => (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M19 8v6" />
      <path d="M22 11h-6" />
    </svg>
  ),
  Calendar: () => (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  ),
  Pill: () => (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z" />
      <path d="m8.5 8.5 7 7" />
    </svg>
  ),
  MedicineSearch: () => (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
      <path d="M11 8v6" />
      <path d="M8 11h6" />
    </svg>
  ),
  Profile: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  ),
  Clock: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  ),
  CheckCircle: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  ),
  ArrowRight: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  ),
  AlertTriangle: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  ),
};

export function PatientDashboard() {
  const { user } = useAuth();
  const [profile, setProfile] = useState(null);
  const [doctors, setDoctors] = useState([]);
  const [myAppointments, setMyAppointments] = useState([]);
  const [myReminders, setMyReminders] = useState([]);
  const [medSchedule, setMedSchedule] = useState({
    next_dose: null,
    today_doses: [],
    upcoming_doses: [],
    active_medications: [],
    history: [],
    total_active_reminders_count: 0,
    adherence_percentage: null,
  });
  const [markingTakenId, setMarkingTakenId] = useState(null);
  const [calStatus, setCalStatus] = useState({ connected: false });
  const [activeTab, setActiveTab] = useState('home'); // 'home' | 'book' | 'appointments' | 'medications' | 'medicines'
  const [medSubTab, setMedSubTab] = useState('today'); // 'today' | 'active' | 'history' | 'all'
  const [searchSpec, setSearchSpec] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Live Countdown State
  const [countdownStr, setCountdownStr] = useState('');
  const [isDueNow, setIsDueNow] = useState(false);

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
      const tzOffsetHours = -Math.round(new Date().getTimezoneOffset() / 60);
      const [profileData, doctorsData, appointmentsData, remindersData, scheduleData, calStatusData] = await Promise.all([
        patientApi.getMe(),
        doctorApi.list(searchSpec),
        appointmentApi.list(),
        clinicalApi.getMyMedicationReminders().catch(() => []),
        clinicalApi.getMyMedicationSchedule(tzOffsetHours).catch(() => ({
          next_dose: null,
          today_doses: [],
          upcoming_doses: [],
          active_medications: [],
          history: [],
          total_active_reminders_count: 0,
          adherence_percentage: null,
        })),
        calendarApi.getStatus().catch(() => ({ connected: false })),
      ]);
      setProfile(profileData);
      setDoctors(doctorsData);
      setMyAppointments(appointmentsData);
      setMyReminders(remindersData);
      setMedSchedule(scheduleData);
      setCalStatus(calStatusData);
    } catch (err) {
      console.error('Error fetching dashboard data:', err);
      setError(err.message || 'Failed to load patient profile data');
    } finally {
      setLoading(false);
    }
  };

  const loadMedicationSchedule = async () => {
    try {
      const tzOffsetHours = -Math.round(new Date().getTimezoneOffset() / 60);
      const [scheduleData, remindersData] = await Promise.all([
        clinicalApi.getMyMedicationSchedule(tzOffsetHours),
        clinicalApi.getMyMedicationReminders().catch(() => []),
      ]);
      setMedSchedule(scheduleData);
      setMyReminders(remindersData);
    } catch (err) {
      console.error('Error refreshing medication schedule:', err);
    }
  };

  useEffect(() => {
    loadData();
  }, [searchSpec]);

  // Live countdown timer calculation effect (updates every second)
  useEffect(() => {
    const nextDose = medSchedule?.next_dose;
    if (!nextDose || !nextDose.scheduled_at) {
      setCountdownStr('');
      setIsDueNow(false);
      return;
    }

    const targetTimestamp = new Date(nextDose.scheduled_at).getTime();

    const updateTimer = () => {
      const diff = targetTimestamp - Date.now();
      if (diff <= 0) {
        setIsDueNow(true);
        setCountdownStr('Due now');
      } else {
        setIsDueNow(false);
        const hours = Math.floor(diff / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((diff % (1000 * 60)) / 1000);
        const pad = (n) => (n < 10 ? '0' : '') + n;
        setCountdownStr(`${pad(hours)}:${pad(minutes)}:${pad(seconds)}`);
      }
    };

    updateTimer();
    const interval = setInterval(updateTimer, 1000);
    return () => clearInterval(interval);
  }, [medSchedule?.next_dose?.scheduled_at]);

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

  const handleMarkTaken = async (reminderId) => {
    if (!reminderId || markingTakenId) return;
    setMarkingTakenId(reminderId);
    setError(null);
    try {
      await clinicalApi.markReminderTaken(reminderId);
      setSuccessMsg('Medication recorded as taken.');
      await loadMedicationSchedule();
    } catch (err) {
      setError(err.message || 'Failed to mark dose as taken');
    } finally {
      setMarkingTakenId(null);
    }
  };

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
      await appointmentApi.confirm(activeHold.appointment_id, idempKey);
      setSuccessMsg('Appointment confirmed successfully!');
      setActiveHold(null);
      setSelectedDoctor(null);
      await loadData();
      setActiveTab('appointments');
    } catch (err) {
      setError(err.message || 'Confirmation failed');
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
      await appointmentApi.submitSymptoms(symptomTarget.id, {
        symptoms: symptomsText.trim(),
        chief_complaint: chiefComplaint.trim() || null,
      });
      setSuccessMsg('Symptoms submitted successfully. AI Pre-visit summary will be ready for your doctor.');
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
        clinicalApi.getAiSummaries(app.id).catch(() => []),
      ]);
      setConsultationData({ notes, rx, ai });
    } catch (err) {
      console.error('Error fetching consultation details:', err);
    } finally {
      setLoadingConsultation(false);
    }
  };

  const handleCancelAppointment = async () => {
    if (!cancelTarget) return;
    setCancelling(true);
    setError(null);
    try {
      const idempKey = generateIdempotencyKey();
      await appointmentApi.cancel(cancelTarget.id, cancelReason.trim(), idempKey);
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

  const handleConnectCalendar = async () => {
    setError(null);
    try {
      const data = await calendarApi.getAuthUrl();
      if (data.auth_url) {
        window.location.href = data.auth_url;
      }
    } catch (err) {
      setError(err.message || 'Failed to initialize Google Calendar connection');
    }
  };

  const handleDisconnectCalendar = async () => {
    setError(null);
    try {
      await calendarApi.disconnect();
      setCalStatus({ connected: false });
      setSuccessMsg('Google Calendar disconnected successfully');
    } catch (err) {
      setError(err.message || 'Failed to disconnect Google Calendar');
    }
  };

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

  const getTimeGreeting = (fullName) => {
    const hour = new Date().getHours();
    let timeGreeting = 'Good morning';
    if (hour >= 12 && hour < 17) {
      timeGreeting = 'Good afternoon';
    } else if (hour >= 17 || hour < 5) {
      timeGreeting = 'Good evening';
    }
    const firstName = fullName ? fullName.split(' ')[0] : 'there';
    return `${timeGreeting}, ${firstName}`;
  };

  const upcomingAppointments = myAppointments
    .filter((a) => ['CONFIRMED', 'HELD', 'RESCHEDULED'].includes(a.status))
    .sort((a, b) => new Date(a.start_time) - new Date(b.start_time));
  const nextAppointment = upcomingAppointments.length > 0 ? upcomingAppointments[0] : null;

  // Next Dose helper from structured schedule
  const nextDose = medSchedule.next_dose;

  // Check if there is an appointment within the next 24 hours
  const isAppointmentTomorrow = nextAppointment && (() => {
    const appTime = new Date(nextAppointment.start_time).getTime();
    const now = Date.now();
    const diffHours = (appTime - now) / (1000 * 60 * 60);
    return diffHours > 0 && diffHours <= 36;
  })();

  // Check if doctor recently declined an appointment
  const recentDeclinedAppt = myAppointments.find(
    (a) => a.status === 'CANCELLED' && a.cancellation_reason && a.cancelled_by_user_id
  );

  if (loading) {
    return <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>Loading patient portal...</div>;
  }

  return (
    <div className="main-content">
      {/* Top Header & Navigation Bar */}
      <div style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <ProfileAvatar
            src={user?.profile_image_url}
            name={user?.name}
            role="PATIENT"
            size={48}
          />
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 800, margin: 0, color: 'var(--text-main)' }}>
              {activeTab === 'home' ? getTimeGreeting(user?.name) : user?.name}
            </h1>
            <p style={{ color: 'var(--text-muted)', margin: '0.15rem 0 0 0', fontSize: '0.875rem' }}>
              Manage your appointments, medicines, and healthcare information in one place.
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            className={`btn btn-sm ${activeTab === 'home' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('home')}
            style={{ fontWeight: 600 }}
          >
            Home
          </button>
          <button
            className={`btn btn-sm ${activeTab === 'book' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('book')}
            style={{ fontWeight: 600 }}
          >
            Find Doctor & Book
          </button>
          <button
            className={`btn btn-sm ${activeTab === 'appointments' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('appointments')}
            style={{ fontWeight: 600 }}
          >
            My Appointments ({myAppointments.length})
          </button>
          <button
            className={`btn btn-sm ${activeTab === 'medications' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('medications')}
            style={{ fontWeight: 600 }}
          >
            Medication Schedule ({medSchedule.total_active_reminders_count || myReminders.length})
          </button>
          <button
            className={`btn btn-sm ${activeTab === 'medicines' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('medicines')}
            style={{ fontWeight: 600 }}
          >
            Medicine Info
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: '1.25rem' }}>{error}</div>}
      {successMsg && <div className="alert alert-success" style={{ marginBottom: '1.25rem' }}>{successMsg}</div>}

      {/* Sub-view Back Breadcrumb when not on Home */}
      {activeTab !== 'home' && (
        <div style={{ marginBottom: '1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#f8fafc', padding: '0.75rem 1rem', borderRadius: '8px', border: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => setActiveTab('home')}
              style={{ fontWeight: 600 }}
            >
              ← Patient Home
            </button>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>/</span>
            <span style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--text-main)' }}>
              {activeTab === 'book' && 'Find a Doctor & Book'}
              {activeTab === 'appointments' && 'My Scheduled Appointments'}
              {activeTab === 'medications' && 'Prescription Medication Schedule'}
              {activeTab === 'medicines' && 'Medicine Knowledge & Information'}
            </span>
          </div>
        </div>
      )}

      {/* TAB 0: Patient Home Overview */}
      {activeTab === 'home' && (
        <>
          {/* Welcome Area Card */}
          <div
            className="card"
            style={{
              padding: '1.5rem 1.75rem',
              background: 'linear-gradient(135deg, #ffffff 0%, #f0fdfa 100%)',
              border: '1px solid #ccfbf1',
              marginBottom: '1.5rem',
              borderRadius: 'var(--radius-lg)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '1.25rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
              <ProfileAvatar
                src={user?.profile_image_url}
                name={user?.name}
                role="PATIENT"
                size={54}
              />
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                  <h2 style={{ fontSize: '1.4rem', fontWeight: 800, margin: 0, color: 'var(--text-main)' }}>
                    {getTimeGreeting(user?.name)}
                  </h2>
                  <span className="user-badge badge-patient" style={{ fontSize: '0.75rem', padding: '2px 8px' }}>
                    Registered Patient
                  </span>
                </div>
                <p style={{ color: 'var(--text-muted)', margin: '0.25rem 0 0 0', fontSize: '0.9rem' }}>
                  Manage your appointments, medicines, and healthcare information in one place.
                </p>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
              <Link to="/profile?tab=basic" className="btn btn-secondary btn-sm">
                View & Edit Profile
              </Link>
            </div>
          </div>

          {/* Important Alerts Area (if relevant) */}
          {isAppointmentTomorrow && (
            <div className="alert alert-info" style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <Icons.Clock />
              <div style={{ flex: 1, fontSize: '0.875rem' }}>
                <strong>Upcoming Consultation Reminder:</strong> You have an appointment with {formatDoctorName(nextAppointment.doctor_name)} on {new Date(nextAppointment.start_time).toLocaleDateString()} at {new Date(nextAppointment.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}.
              </div>
              <button className="btn btn-primary btn-sm" onClick={() => setActiveTab('appointments')}>
                View Visit
              </button>
            </div>
          )}

          {recentDeclinedAppt && (
            <div className="alert alert-error" style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <Icons.AlertTriangle />
              <div style={{ flex: 1, fontSize: '0.875rem' }}>
                <strong>Appointment Update:</strong> An appointment was declined by the physician. Reason: "{recentDeclinedAppt.cancellation_reason}". The slot has been released.
              </div>
              <button className="btn btn-secondary btn-sm" onClick={() => setActiveTab('book')}>
                Book Another Slot
              </button>
            </div>
          )}

          {/* Primary Interactive Action Area (4 prominent cards) */}
          <div style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, margin: '0 0 0.85rem 0', color: 'var(--text-main)' }}>
              Primary Services & Actions
            </h2>
            <div className="grid-2" style={{ gap: '1.25rem' }}>
              {/* Card 1: Find a Doctor & Book */}
              <div
                className="card"
                role="button"
                tabIndex={0}
                onClick={() => setActiveTab('book')}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('book'); } }}
                style={{
                  padding: '1.5rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  border: '1px solid var(--border)',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '1.25rem',
                  background: '#ffffff',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-2px)';
                  e.currentTarget.style.boxShadow = '0 10px 25px -5px rgba(0, 0, 0, 0.08)';
                  e.currentTarget.style.borderColor = 'var(--primary)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = 'none';
                  e.currentTarget.style.borderColor = 'var(--border)';
                }}
              >
                <div
                  style={{
                    width: '46px',
                    height: '46px',
                    borderRadius: '10px',
                    background: '#e0f2fe',
                    color: '#0369a1',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                  }}
                >
                  <Icons.Doctor />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                    <h3 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0, color: 'var(--text-main)' }}>
                      Find a Doctor & Book
                    </h3>
                    <Icons.ArrowRight />
                  </div>
                  <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
                    Find a doctor and book an available appointment.
                  </p>
                </div>
              </div>

              {/* Card 2: My Appointments */}
              <div
                className="card"
                role="button"
                tabIndex={0}
                onClick={() => setActiveTab('appointments')}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('appointments'); } }}
                style={{
                  padding: '1.5rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  border: '1px solid var(--border)',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '1.25rem',
                  background: '#ffffff',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-2px)';
                  e.currentTarget.style.boxShadow = '0 10px 25px -5px rgba(0, 0, 0, 0.08)';
                  e.currentTarget.style.borderColor = 'var(--primary)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = 'none';
                  e.currentTarget.style.borderColor = 'var(--border)';
                }}
              >
                <div
                  style={{
                    width: '46px',
                    height: '46px',
                    borderRadius: '10px',
                    background: '#f0fdf4',
                    color: '#15803d',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                  }}
                >
                  <Icons.Calendar />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <h3 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0, color: 'var(--text-main)' }}>
                        My Appointments
                      </h3>
                      <span className="user-badge badge-patient" style={{ fontSize: '0.75rem', padding: '1px 6px' }}>
                        {myAppointments.length} Total
                      </span>
                    </div>
                    <Icons.ArrowRight />
                  </div>
                  <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
                    View upcoming and past appointments.
                  </p>
                </div>
              </div>

              {/* Card 3: Medication Schedule */}
              <div
                className="card"
                role="button"
                tabIndex={0}
                onClick={() => setActiveTab('medications')}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('medications'); } }}
                style={{
                  padding: '1.5rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  border: '1px solid var(--border)',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '1.25rem',
                  background: '#ffffff',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-2px)';
                  e.currentTarget.style.boxShadow = '0 10px 25px -5px rgba(0, 0, 0, 0.08)';
                  e.currentTarget.style.borderColor = 'var(--primary)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = 'none';
                  e.currentTarget.style.borderColor = 'var(--border)';
                }}
              >
                <div
                  style={{
                    width: '46px',
                    height: '46px',
                    borderRadius: '10px',
                    background: '#fef3c7',
                    color: '#b45309',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                  }}
                >
                  <Icons.Pill />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <h3 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0, color: 'var(--text-main)' }}>
                        Medication Schedule
                      </h3>
                      {medSchedule.total_active_reminders_count > 0 && (
                        <span className="user-badge" style={{ fontSize: '0.75rem', padding: '1px 6px', background: '#fef3c7', color: '#b45309' }}>
                          {medSchedule.total_active_reminders_count} Active
                        </span>
                      )}
                    </div>
                    <Icons.ArrowRight />
                  </div>
                  <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
                    View your medicines, countdown timers, and upcoming reminders.
                  </p>
                </div>
              </div>

              {/* Card 4: Medicine Information */}
              <div
                className="card"
                role="button"
                tabIndex={0}
                onClick={() => setActiveTab('medicines')}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('medicines'); } }}
                style={{
                  padding: '1.5rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  border: '1px solid var(--border)',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '1.25rem',
                  background: '#ffffff',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-2px)';
                  e.currentTarget.style.boxShadow = '0 10px 25px -5px rgba(0, 0, 0, 0.08)';
                  e.currentTarget.style.borderColor = 'var(--primary)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = 'none';
                  e.currentTarget.style.borderColor = 'var(--border)';
                }}
              >
                <div
                  style={{
                    width: '46px',
                    height: '46px',
                    borderRadius: '10px',
                    background: '#f3e8ff',
                    color: '#7e22ce',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                  }}
                >
                  <Icons.MedicineSearch />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                    <h3 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0, color: 'var(--text-main)' }}>
                      Medicine Information
                    </h3>
                    <Icons.ArrowRight />
                  </div>
                  <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
                    Learn what a medicine is commonly used for.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* 2-Column Information Area: Upcoming Appointment & Next Medication */}
          <div style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, margin: '0 0 0.85rem 0', color: 'var(--text-main)' }}>
              Current Healthcare Timeline
            </h2>
            <div className="grid-2" style={{ gap: '1.25rem' }}>
              {/* Card A: Upcoming Appointment Widget */}
              <div className="card" style={{ padding: '1.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.75rem' }}>
                  <h3 style={{ fontSize: '0.95rem', fontWeight: 700, margin: 0, color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Icons.Calendar />
                    <span>Upcoming Appointment</span>
                  </h3>
                  {nextAppointment && getStatusBadge(nextAppointment)}
                </div>

                {nextAppointment ? (
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', marginBottom: '1rem' }}>
                      <ProfileAvatar
                        src={nextAppointment.doctor_image_url}
                        name={nextAppointment.doctor_name}
                        role="DOCTOR"
                        size={44}
                      />
                      <div>
                        <h4 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700 }}>
                          {formatDoctorName(nextAppointment.doctor_name)}
                        </h4>
                        <p style={{ margin: '0.15rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                          {nextAppointment.doctor_specialization || 'Specialist Consultation'}
                        </p>
                      </div>
                    </div>

                    <div style={{ background: '#f8fafc', padding: '0.75rem 1rem', borderRadius: '8px', border: '1px solid var(--border)', fontSize: '0.875rem', marginBottom: '1rem' }}>
                      <div style={{ fontWeight: 600, color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <Icons.Clock />
                        <span>
                          {new Date(nextAppointment.start_time).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })} at {new Date(nextAppointment.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                    </div>

                    <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => setActiveTab('appointments')}
                      >
                        View Appointment
                      </button>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => {
                          setSymptomTarget(nextAppointment);
                          setSymptomsText(nextAppointment.symptoms || '');
                          setChiefComplaint(nextAppointment.chief_complaint || '');
                        }}
                      >
                        {nextAppointment.symptoms ? 'Update Symptoms' : 'Submit Symptoms'}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', padding: '1.5rem 1rem', color: 'var(--text-muted)' }}>
                    <p style={{ margin: '0 0 1rem 0', fontSize: '0.9rem' }}>No upcoming appointments.</p>
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={() => setActiveTab('book')}
                    >
                      Find a Doctor
                    </button>
                  </div>
                )}
              </div>

              {/* Card B: Next Medication Widget (Reactive Countdown) */}
              <div className="card" style={{ padding: '1.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.75rem' }}>
                  <h3 style={{ fontSize: '0.95rem', fontWeight: 700, margin: 0, color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Icons.Pill />
                    <span>Next Medication</span>
                  </h3>
                  {nextDose ? (
                    <span className="user-badge" style={{
                      background: isDueNow ? '#fee2e2' : '#e0f2fe',
                      color: isDueNow ? '#b91c1c' : '#0369a1',
                      fontWeight: 700,
                    }}>
                      {isDueNow ? 'Due Now' : 'Scheduled'}
                    </span>
                  ) : null}
                </div>

                {nextDose ? (
                  <div>
                    <div style={{ background: '#f8fafc', padding: '0.9rem 1rem', borderRadius: '8px', border: '1px solid var(--border)', marginBottom: '1rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                          <h4 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-main)' }}>
                            {nextDose.medication_name}
                          </h4>
                          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                            {nextDose.dosage} • Take at {new Date(nextDose.scheduled_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </div>
                        </div>
                        <span className="user-badge" style={{ background: '#e0f2fe', color: '#0369a1', fontWeight: 600 }}>
                          {nextDose.doses_remaining} doses left
                        </span>
                      </div>

                      {/* Countdown badge */}
                      <div style={{ marginTop: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <Icons.Clock />
                        <span style={{ fontSize: '0.9rem', fontWeight: 700, color: isDueNow ? '#b91c1c' : 'var(--primary)' }}>
                          {countdownStr || 'Calculating...'}
                        </span>
                        {!isDueNow && <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>until next dose</span>}
                      </div>

                      {nextDose.instructions && (
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
                          Instructions: {nextDose.instructions}
                        </div>
                      )}
                    </div>

                    <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => handleMarkTaken(nextDose.reminder_id)}
                        disabled={markingTakenId === nextDose.reminder_id}
                      >
                        {markingTakenId === nextDose.reminder_id ? 'Recording...' : 'Mark as Taken'}
                      </button>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => setActiveTab('medications')}
                      >
                        View Full Schedule
                      </button>
                    </div>
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', padding: '1.5rem 1rem', color: 'var(--text-muted)' }}>
                    <p style={{ margin: '0 0 1rem 0', fontSize: '0.9rem' }}>No medications scheduled.</p>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => setActiveTab('medicines')}
                    >
                      Search Medicine Information
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Health Profile Snapshot + Google Calendar Status */}
          <div style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, margin: '0 0 0.85rem 0', color: 'var(--text-main)' }}>
              Account & Integrations
            </h2>
            <div className="grid-2" style={{ gap: '1.25rem' }}>
              {/* Snapshot: Your Health Profile */}
              <div className="card" style={{ padding: '1.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.75rem' }}>
                  <h3 style={{ fontSize: '0.95rem', fontWeight: 700, margin: 0, color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Icons.Profile />
                    <span>Your Health Profile</span>
                  </h3>
                  <Link to="/profile" className="btn btn-secondary btn-sm" style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}>
                    View Profile
                  </Link>
                </div>

                <div style={{ fontSize: '0.875rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Name:</span>
                    <strong style={{ color: 'var(--text-main)' }}>{profile?.name || user?.name}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Phone:</span>
                    <strong style={{ color: 'var(--text-main)' }}>{profile?.phone || 'Not provided'}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Appointment History:</span>
                    <strong style={{ color: 'var(--text-main)' }}>{myAppointments.length} visits</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Profile Status:</span>
                    <span className="user-badge" style={{ background: profile?.phone ? '#ecfdf5' : '#fef3c7', color: profile?.phone ? '#047857' : '#b45309', fontSize: '0.75rem' }}>
                      {profile?.phone ? 'Complete' : 'Incomplete'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Snapshot: Google Calendar Status */}
              <div className="card" style={{ padding: '1.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.75rem' }}>
                  <h3 style={{ fontSize: '0.95rem', fontWeight: 700, margin: 0, color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Icons.Calendar />
                    <span>Google Calendar</span>
                  </h3>
                  <span className="user-badge" style={{ background: calStatus.connected ? '#ecfdf5' : '#f1f5f9', color: calStatus.connected ? '#047857' : '#475569', fontSize: '0.75rem' }}>
                    {calStatus.connected ? 'Connected ✓' : 'Not connected'}
                  </span>
                </div>

                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.45, marginBottom: '1rem' }}>
                  Synchronize your confirmed consultations directly with Google Calendar for timely reminders.
                </p>

                <div>
                  {calStatus.connected ? (
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={handleDisconnectCalendar}
                      style={{ color: '#b91c1c' }}
                    >
                      Disconnect Calendar
                    </button>
                  ) : (
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={handleConnectCalendar}
                    >
                      Connect Google Calendar
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Quick Actions Bar */}
          <div className="card" style={{ padding: '1.25rem 1.5rem', background: '#f8fafc', marginBottom: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
              <span style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-main)' }}>
                Quick Actions:
              </span>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <button className="btn btn-primary btn-sm" onClick={() => setActiveTab('book')}>
                  Book Appointment
                </button>
                <button className="btn btn-secondary btn-sm" onClick={() => setActiveTab('appointments')}>
                  View Appointments
                </button>
                <Link to="/profile" className="btn btn-secondary btn-sm">
                  View Profile
                </Link>
                <button className="btn btn-secondary btn-sm" onClick={() => setActiveTab('medicines')}>
                  Search Medicine
                </button>
              </div>
            </div>
          </div>
        </>
      )}

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
                    <div><strong>Slot Duration:</strong> {doc.slot_duration} minutes</div>
                    <div><strong>Availability:</strong> {doc.working_hours?.length ? `${doc.working_hours.length} day(s) configured` : 'Standard Schedule'}</div>
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
            <div style={{ textAlign: 'center', padding: '3rem 1rem', color: 'var(--text-muted)' }}>
              <p style={{ margin: '0 0 1rem 0' }}>You have no scheduled appointments yet.</p>
              <button className="btn btn-primary" onClick={() => setActiveTab('book')}>
                Find Doctor & Book
              </button>
            </div>
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
                                Submit Symptoms
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
                              Find Another Slot
                            </button>
                          )}
                          {app.status === 'COMPLETED' && (
                            <button
                              className="btn btn-primary btn-sm"
                              onClick={() => handleOpenConsultation(app)}
                            >
                              View Visit Summary & Rx
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

      {/* Tab 3: Medication Schedule (Phase 11 Redesign) */}
      {activeTab === 'medications' && (
        <div>
          {/* Header & Sub-Navigation */}
          <div className="card" style={{ marginBottom: '1.5rem', padding: '1.5rem 1.75rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1rem' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  <h2 style={{ fontSize: '1.35rem', fontWeight: 800, margin: 0, color: 'var(--text-main)' }}>
                    Medication Schedule
                  </h2>
                  {medSchedule.adherence_percentage !== null && (
                    <span className="user-badge" style={{ background: '#ecfdf5', color: '#047857', fontWeight: 700, fontSize: '0.75rem' }}>
                      {medSchedule.adherence_percentage}% Adherence
                    </span>
                  )}
                </div>
                <p style={{ color: 'var(--text-muted)', margin: '0.25rem 0 0 0', fontSize: '0.875rem' }}>
                  Your personalized daily dosage schedule, live countdown, and adherence tracker.
                </p>
              </div>

              <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                <button
                  className={`btn btn-sm ${medSubTab === 'today' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setMedSubTab('today')}
                >
                  Today & Next Dose
                </button>
                <button
                  className={`btn btn-sm ${medSubTab === 'active' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setMedSubTab('active')}
                >
                  Active Medications ({medSchedule.active_medications.length})
                </button>
                <button
                  className={`btn btn-sm ${medSubTab === 'history' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setMedSubTab('history')}
                >
                  Dose History ({medSchedule.history.length})
                </button>
              </div>
            </div>

            {/* If no medications exist across the whole schedule */}
            {medSchedule.active_medications.length === 0 && medSchedule.today_doses.length === 0 && (
              <div style={{ textAlign: 'center', padding: '2.5rem 1rem', color: 'var(--text-muted)' }}>
                <div style={{ marginBottom: '0.5rem', color: 'var(--primary)' }}>
                  <Icons.Pill />
                </div>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: '0 0 0.5rem 0', color: 'var(--text-main)' }}>
                  No medications scheduled
                </h3>
                <p style={{ margin: '0 0 1rem 0', fontSize: '0.875rem' }}>
                  No medications have been prescribed for you yet. Prescribed medicines will automatically appear with reminder schedules.
                </p>
                <button className="btn btn-secondary btn-sm" onClick={() => setActiveTab('medicines')}>
                  Search Medicine Information
                </button>
              </div>
            )}
          </div>

          {/* SUB-VIEW 1: Today & Next Dose */}
          {medSubTab === 'today' && medSchedule.active_medications.length > 0 && (
            <>
              {/* Next Dose Hero Card */}
              {nextDose ? (
                <div
                  className="card"
                  style={{
                    padding: '1.75rem 2rem',
                    background: isDueNow ? 'linear-gradient(135deg, #ffffff 0%, #fef2f2 100%)' : 'linear-gradient(135deg, #ffffff 0%, #f0fdf4 100%)',
                    border: isDueNow ? '2px solid #fecaca' : '2px solid #bbf7d0',
                    borderRadius: 'var(--radius-lg)',
                    marginBottom: '2rem',
                    boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.05)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.25rem' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
                        <span className="user-badge" style={{
                          background: isDueNow ? '#fee2e2' : '#dcfce7',
                          color: isDueNow ? '#b91c1c' : '#15803d',
                          fontWeight: 800,
                          fontSize: '0.8rem',
                        }}>
                          {isDueNow ? 'DUE NOW' : 'NEXT DOSE'}
                        </span>
                        <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                          Scheduled for {new Date(nextDose.scheduled_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <h3 style={{ fontSize: '1.65rem', fontWeight: 800, margin: '0 0 0.25rem 0', color: 'var(--text-main)' }}>
                        {nextDose.medication_name}
                      </h3>
                      <div style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--primary)' }}>
                        {nextDose.dosage} {nextDose.frequency ? `• ${nextDose.frequency.replace('_', ' ')}` : ''}
                      </div>
                    </div>

                    {/* Countdown Display Widget */}
                    <div style={{
                      background: '#ffffff',
                      border: '1px solid var(--border)',
                      borderRadius: '12px',
                      padding: '0.75rem 1.25rem',
                      textAlign: 'center',
                      minWidth: '170px',
                    }}>
                      <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        {isDueNow ? 'Status' : 'Countdown'}
                      </div>
                      <div style={{
                        fontSize: '1.5rem',
                        fontWeight: 900,
                        fontFamily: 'monospace',
                        color: isDueNow ? '#b91c1c' : 'var(--primary)',
                        margin: '0.2rem 0',
                      }}>
                        {countdownStr || 'Calculating...'}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {isDueNow ? 'Please take your dose' : 'until next dose'}
                      </div>
                    </div>
                  </div>

                  {/* Metadata Row */}
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1.5rem', marginBottom: '1.25rem', fontSize: '0.875rem', color: 'var(--text-muted)', borderTop: '1px solid rgba(0,0,0,0.06)', paddingTop: '0.75rem' }}>
                    {nextDose.doctor_name && (
                      <div>Prescribed by: <strong style={{ color: 'var(--text-main)' }}>{formatDoctorName(nextDose.doctor_name)}</strong></div>
                    )}
                    <div>Remaining in course: <strong style={{ color: 'var(--text-main)' }}>{nextDose.doses_remaining} doses left</strong></div>
                    {nextDose.instructions && (
                      <div style={{ width: '100%' }}>
                        Instructions: <span style={{ color: 'var(--text-main)', fontWeight: 600 }}>{nextDose.instructions}</span>
                      </div>
                    )}
                  </div>

                  {/* Action */}
                  <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                    <button
                      className="btn btn-primary"
                      onClick={() => handleMarkTaken(nextDose.reminder_id)}
                      disabled={markingTakenId === nextDose.reminder_id}
                      style={{ padding: '0.65rem 1.5rem', fontWeight: 700 }}
                    >
                      {markingTakenId === nextDose.reminder_id ? 'Recording...' : '✓ Mark as Taken'}
                    </button>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      Clicking will record this dose in your adherence history.
                    </span>
                  </div>
                </div>
              ) : (
                <div className="card" style={{ padding: '1.5rem', marginBottom: '2rem', textAlign: 'center', background: '#f8fafc' }}>
                  <p style={{ margin: 0, fontSize: '0.95rem', color: 'var(--text-muted)' }}>
                    All scheduled doses for right now have been completed.
                  </p>
                </div>
              )}

              {/* Today's Medicines Grouped Chronologically */}
              <div style={{ marginBottom: '2rem' }}>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 700, margin: '0 0 1rem 0', color: 'var(--text-main)' }}>
                  Today's Medicines & Schedule
                </h3>

                {medSchedule.today_doses.length === 0 ? (
                  <div className="card" style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                    No doses scheduled specifically for today.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                    {medSchedule.today_doses.map((dose) => {
                      const isTaken = (dose.status === 'TAKEN');
                      const isMissed = (dose.status === 'MISSED');
                      const isDue = (dose.status === 'DUE_NOW');

                      return (
                        <div
                          key={dose.reminder_id}
                          className="card"
                          style={{
                            padding: '1.15rem 1.5rem',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            flexWrap: 'wrap',
                            gap: '1rem',
                            borderLeft: isTaken ? '4px solid #10b981' : isDue ? '4px solid #ef4444' : isMissed ? '4px solid #f59e0b' : '4px solid var(--primary)',
                            background: isTaken ? '#f0fdf4' : '#ffffff',
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
                            <div style={{ minWidth: '85px', fontWeight: 700, fontSize: '0.95rem', color: 'var(--text-main)' }}>
                              {new Date(dose.scheduled_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </div>

                            <div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                                <h4 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-main)' }}>
                                  {dose.medication_name}
                                </h4>
                                <span className="user-badge" style={{ fontSize: '0.75rem' }}>
                                  {dose.dosage}
                                </span>
                              </div>
                              {dose.instructions && (
                                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                                  {dose.instructions}
                                </div>
                              )}
                            </div>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                            {isTaken ? (
                              <span className="user-badge" style={{ background: '#dcfce7', color: '#15803d', fontWeight: 700 }}>
                                ✓ Taken {dose.taken_at ? `at ${new Date(dose.taken_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : ''}
                              </span>
                            ) : isMissed ? (
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <span className="user-badge" style={{ background: '#fef3c7', color: '#b45309', fontWeight: 700 }}>
                                  Missed
                                </span>
                                <button
                                  className="btn btn-secondary btn-sm"
                                  onClick={() => handleMarkTaken(dose.reminder_id)}
                                  disabled={markingTakenId === dose.reminder_id}
                                >
                                  Take Now
                                </button>
                              </div>
                            ) : (
                              <button
                                className={`btn btn-sm ${isDue ? 'btn-primary' : 'btn-secondary'}`}
                                onClick={() => handleMarkTaken(dose.reminder_id)}
                                disabled={markingTakenId === dose.reminder_id}
                              >
                                {isDue ? 'Mark as Taken' : 'Take Early'}
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Upcoming Doses (Later Schedule) */}
              {medSchedule.upcoming_doses.length > 0 && (
                <div style={{ marginBottom: '2rem' }}>
                  <h3 style={{ fontSize: '1.15rem', fontWeight: 700, margin: '0 0 1rem 0', color: 'var(--text-main)' }}>
                    Upcoming Doses
                  </h3>
                  <div className="grid-3" style={{ gap: '1rem' }}>
                    {medSchedule.upcoming_doses.slice(0, 6).map((up) => (
                      <div key={up.reminder_id} className="card" style={{ padding: '1rem 1.25rem', background: '#f8fafc' }}>
                        <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--primary)', marginBottom: '0.25rem' }}>
                          {new Date(up.scheduled_at).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })} at {new Date(up.scheduled_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>
                        <h4 style={{ margin: '0 0 0.15rem 0', fontSize: '0.95rem', fontWeight: 700 }}>
                          {up.medication_name}
                        </h4>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                          {up.dosage} {up.frequency ? `• ${up.frequency.replace('_', ' ')}` : ''}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {/* SUB-VIEW 2: Active Medications & Treatment Progress */}
          {medSubTab === 'active' && (
            <div className="grid-2" style={{ gap: '1.25rem', marginBottom: '2rem' }}>
              {medSchedule.active_medications.map((med) => {
                const total = med.total_doses || 1;
                const completed = med.completed_doses || 0;
                const percent = Math.min(100, Math.round((completed / total) * 100));

                return (
                  <div key={med.medication_id} className="card" style={{ padding: '1.5rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                      <div>
                        <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 800, color: 'var(--text-main)' }}>
                          {med.name}
                        </h3>
                        <div style={{ fontSize: '0.9rem', color: 'var(--primary)', fontWeight: 600, marginTop: '2px' }}>
                          {med.dosage} • {med.frequency.replace('_', ' ')}
                        </div>
                      </div>
                      <span className="user-badge" style={{
                        background: med.course_completed ? '#dcfce7' : '#e0f2fe',
                        color: med.course_completed ? '#15803d' : '#0369a1',
                        fontWeight: 700,
                      }}>
                        {med.course_completed ? 'Course Completed ✓' : `${med.remaining_doses} doses remaining`}
                      </span>
                    </div>

                    <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                      <div>Duration: {med.start_date} to {med.end_date}</div>
                      {med.doctor_name && <div>Prescribed by: {formatDoctorName(med.doctor_name)}</div>}
                      {med.instructions && <div>Instructions: <strong style={{ color: 'var(--text-main)' }}>{med.instructions}</strong></div>}
                    </div>

                    {/* Progress Bar */}
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
                        <span>Treatment Progress</span>
                        <span>{completed} of {total} doses completed ({percent}%)</span>
                      </div>
                      <div style={{ width: '100%', height: '8px', background: '#e2e8f0', borderRadius: '4px', overflow: 'hidden' }}>
                        <div style={{ width: `${percent}%`, height: '100%', background: med.course_completed ? '#10b981' : 'var(--primary)', borderRadius: '4px', transition: 'width 0.3s ease' }} />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* SUB-VIEW 3: Dose History & Adherence */}
          {medSubTab === 'history' && (
            <div className="card" style={{ marginBottom: '2rem' }}>
              <div className="card-header">
                <div>
                  <h3 className="card-title">Medication Intake History</h3>
                  <p className="card-subtitle">Complete record of completed and missed doses for adherence verification</p>
                </div>
              </div>

              {medSchedule.history.length === 0 ? (
                <p style={{ color: 'var(--text-muted)', padding: '2rem 0', textAlign: 'center' }}>
                  No historical medication records yet.
                </p>
              ) : (
                <div className="table-container">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Medication</th>
                        <th>Dosage</th>
                        <th>Scheduled Time</th>
                        <th>Taken Time</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {medSchedule.history.map((h, idx) => (
                        <tr key={idx}>
                          <td style={{ fontWeight: 600 }}>{h.medication_name}</td>
                          <td>{h.dosage}</td>
                          <td>
                            <div>{new Date(h.scheduled_at).toLocaleDateString()}</div>
                            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                              {new Date(h.scheduled_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </div>
                          </td>
                          <td>
                            {h.taken_at ? (
                              <div>
                                <div>{new Date(h.taken_at).toLocaleDateString()}</div>
                                <div style={{ fontSize: '0.8rem', color: '#15803d' }}>
                                  {new Date(h.taken_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </div>
                              </div>
                            ) : (
                              <span style={{ color: 'var(--text-muted)' }}>—</span>
                            )}
                          </td>
                          <td>
                            <span className="user-badge" style={{
                              background: h.status === 'TAKEN' ? '#dcfce7' : h.status === 'MISSED' ? '#fef3c7' : '#f1f5f9',
                              color: h.status === 'TAKEN' ? '#15803d' : h.status === 'MISSED' ? '#b45309' : '#475569',
                              fontWeight: 700,
                            }}>
                              {h.status}
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

          {/* Secondary Collapsible Database Archive */}
          <details style={{ marginTop: '1.5rem', background: '#f8fafc', padding: '1rem 1.25rem', borderRadius: '8px', border: '1px solid var(--border)', cursor: 'pointer' }}>
            <summary style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--text-muted)' }}>
              View all reminder records (Database Archive) ⌄
            </summary>
            <div style={{ marginTop: '1rem' }}>
              <div className="table-container">
                <table className="data-table" style={{ fontSize: '0.85rem' }}>
                  <thead>
                    <tr>
                      <th>Medication Name</th>
                      <th>Dosage</th>
                      <th>Scheduled Time</th>
                      <th>System Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {myReminders.map((rem) => (
                      <tr key={rem.id}>
                        <td style={{ fontWeight: 600 }}>{rem.medication_name}</td>
                        <td>{rem.dosage}</td>
                        <td>{new Date(rem.scheduled_at).toLocaleString()}</td>
                        <td>
                          <span className="user-badge" style={{
                            background: rem.intake_status === 'TAKEN' ? '#dcfce7' : rem.status === 'PENDING' ? '#fef3c7' : '#f1f5f9',
                            color: rem.intake_status === 'TAKEN' ? '#15803d' : rem.status === 'PENDING' ? '#b45309' : '#475569',
                          }}>
                            {rem.intake_status || rem.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </details>
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
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600, alignSelf: 'center' }}>Quick search:</span>
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
                  {patientSelectedMed.source?.name || 'DailyMed / RxNorm'}
                </span>
              </div>

              {/* What is this medicine used for? */}
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

              {/* Medicine Snapshot */}
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

              {/* Safety Information */}
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

              {/* Medical Disclaimer */}
              <div className="alert alert-error" style={{ background: '#fef2f2', borderColor: '#fecaca', color: '#991b1b' }}>
                <strong style={{ fontSize: '0.8rem' }}>Educational Disclaimer:</strong>
                <p style={{ fontSize: '0.75rem', margin: 0 }}>{patientSelectedMed.disclaimer}</p>
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
                <label className="form-label">Chief Complaint (Summary)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Persistent Cough / Joint Pain"
                  value={chiefComplaint}
                  onChange={(e) => setChiefComplaint(e.target.value)}
                />
              </div>
              <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', marginTop: '1.5rem' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setSymptomTarget(null)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={savingSymptoms}>
                  {savingSymptoms ? 'Submitting...' : 'Submit Symptoms'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Consultation Summary & Rx Viewer Modal */}
      {consultationTarget && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card" style={{ maxWidth: '650px', width: '90%', maxHeight: '85vh', overflowY: 'auto' }}>
            <div className="card-header">
              <div>
                <h3 className="card-title">Clinical Consultation Summary</h3>
                <p className="card-subtitle">Visit with {formatDoctorName(consultationTarget.doctor_name)} on {new Date(consultationTarget.start_time).toLocaleDateString()}</p>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={() => setConsultationTarget(null)}>✕</button>
            </div>

            {loadingConsultation ? (
              <p style={{ color: 'var(--text-muted)', padding: '2rem 0', textAlign: 'center' }}>Loading clinical visit records...</p>
            ) : (
              <div>
                {/* AI Post-Visit Summary */}
                {consultationData.ai.find((s) => s.summary_type === 'POST_VISIT') && (
                  <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', padding: '1rem', marginBottom: '1.25rem' }}>
                    <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#15803d', marginBottom: '0.5rem' }}>
                      Patient-Friendly Visit Summary (AI)
                    </h4>
                    <p style={{ fontSize: '0.875rem', color: '#166534', margin: 0, lineHeight: 1.5 }}>
                      {consultationData.ai.find((s) => s.summary_type === 'POST_VISIT').summary_text}
                    </p>
                  </div>
                )}

                {/* Doctor's Authoritative Notes */}
                <div style={{ marginBottom: '1.25rem' }}>
                  <h4 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '0.5rem' }}>Doctor's Assessment & Diagnosis</h4>
                  {consultationData.notes?.diagnosis && (
                    <div style={{ fontWeight: 600, color: 'var(--primary)', marginBottom: '0.25rem', fontSize: '0.9rem' }}>
                      Diagnosis: {consultationData.notes.diagnosis}
                    </div>
                  )}
                  <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', background: '#f8fafc', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--border)' }}>
                    {consultationData.notes?.notes || 'No doctor clinical notes recorded.'}
                  </p>
                </div>

                {/* Structured Prescription Items */}
                {consultationData.rx && (
                  <div>
                    <h4 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '0.5rem' }}>Prescribed Medications</h4>
                    {consultationData.rx.medications && consultationData.rx.medications.length > 0 ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                        {consultationData.rx.medications.map((m) => (
                          <div key={m.id} style={{ background: '#ffffff', border: '1px solid var(--border)', borderRadius: '6px', padding: '0.75rem' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <strong style={{ fontSize: '0.9rem' }}>{m.name}</strong>
                              <span className="user-badge" style={{ fontSize: '0.75rem', background: '#ecfdf5', color: '#047857' }}>{m.dosage}</span>
                            </div>
                            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                              Frequency: {m.frequency} • {m.start_date} to {m.end_date}
                            </div>
                            {m.instructions && (
                              <div style={{ fontSize: '0.8rem', color: 'var(--text-main)', marginTop: '0.25rem' }}>
                                Instructions: {m.instructions}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>No prescription medications issued.</p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Reschedule Alternatives Modal */}
      {rescheduleTarget && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card" style={{ maxWidth: '500px', width: '90%' }}>
            <div className="card-header">
              <div>
                <h3 className="card-title">Reschedule Appointment</h3>
                <p className="card-subtitle">Consultation with {formatDoctorName(rescheduleTarget.doctor_name)}</p>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={() => setRescheduleTarget(null)}>✕</button>
            </div>

            <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
              Select a recommended alternative slot below:
            </p>

            {loadingAlternatives ? (
              <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '1rem 0' }}>Loading alternative slots...</p>
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
