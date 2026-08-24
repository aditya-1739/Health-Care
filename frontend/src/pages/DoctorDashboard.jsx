import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { doctorApi, appointmentApi, clinicalApi, medicineApi } from '../api/client';
import { formatDoctorName } from '../utils/format';
import { ProfileAvatar } from '../components/ProfileAvatar';

export function DoctorDashboard() {
  const { user } = useAuth();
  const [doctorProfile, setDoctorProfile] = useState(null);
  const [appointments, setAppointments] = useState([]);
  const [leaves, setLeaves] = useState([]);
  const [activeTab, setActiveTab] = useState('appointments'); // 'appointments' | 'schedule' | 'leaves'
  const [apptFilter, setApptFilter] = useState('all'); // 'all' | 'today' | 'upcoming' | 'completed'
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Consultation Modal State
  const [consultTarget, setConsultTarget] = useState(null);
  const [patientSymptoms, setPatientSymptoms] = useState(null);
  const [aiPrevisit, setAiPrevisit] = useState(null);
  const [loadingPreconsult, setLoadingPreconsult] = useState(false);

  // View Past Consultation Modal State
  const [viewPastTarget, setViewPastTarget] = useState(null);
  const [pastConsultData, setPastConsultData] = useState({ notes: null, rx: null, ai: [] });
  const [loadingPastConsult, setLoadingPastConsult] = useState(false);

  // Appointment Decline Modal State
  const [declineTarget, setDeclineTarget] = useState(null);
  const [declineRemarks, setDeclineRemarks] = useState('');
  const [declining, setDeclining] = useState(false);

  // Clinical Notes & Prescription Form State
  const [clinicalNotes, setClinicalNotes] = useState('');
  const [diagnosis, setDiagnosis] = useState('');
  const [rxInstructions, setRxInstructions] = useState('');
  const [medications, setMedications] = useState([
    {
      name: '',
      dosage: '',
      frequency: 'ONCE_DAILY',
      start_date: new Date().toISOString().split('T')[0],
      end_date: new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0],
      instructions: '',
    },
  ]);
  const [savingConsultation, setSavingConsultation] = useState(false);

  // Working Hours & Leaves
  const [whDay, setWhDay] = useState('0');
  const [whStart, setWhStart] = useState('09:00');
  const [whEnd, setWhEnd] = useState('17:00');
  const [leaveStart, setLeaveStart] = useState('');
  const [leaveEnd, setLeaveEnd] = useState('');
  const [leaveReason, setLeaveReason] = useState('');
  const [submittingLeave, setSubmittingLeave] = useState(false);
  const [leaveConflicts, setLeaveConflicts] = useState(null);

  const loadData = async () => {
    try {
      const [appointmentsData, leavesData] = await Promise.all([
        appointmentApi.list(),
        doctorApi.getMyLeaves().catch(() => []),
      ]);
      setAppointments(appointmentsData);
      setLeaves(leavesData);

      if (user?.doctor_id) {
        const profile = await doctorApi.getById(user.doctor_id);
        setDoctorProfile(profile);
      }
    } catch (err) {
      console.error('Failed to load doctor dashboard:', err);
      setError(err.message || 'Error loading doctor portal');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [user]);

  const handleOpenConsultation = async (app) => {
    setConsultTarget(app);
    setLoadingPreconsult(true);
    setError(null);
    setClinicalNotes('');
    setDiagnosis('');
    setRxInstructions('');
    setMedications([
      {
        name: '',
        dosage: '',
        frequency: 'ONCE_DAILY',
        start_date: new Date().toISOString().split('T')[0],
        end_date: new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0],
        instructions: '',
      },
    ]);
    try {
      const [symptoms, summaries] = await Promise.all([
        clinicalApi.getSymptoms(app.id).catch(() => null),
        clinicalApi.getAISummaries(app.id).catch(() => []),
      ]);
      setPatientSymptoms(symptoms);
      const previsit = summaries.find((s) => s.summary_type === 'PRE_VISIT');
      setAiPrevisit(previsit || null);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingPreconsult(false);
    }
  };

  const handleOpenViewPast = async (app) => {
    setViewPastTarget(app);
    setLoadingPastConsult(true);
    try {
      const [notes, rx, ai] = await Promise.all([
        clinicalApi.getClinicalNotes(app.id).catch(() => null),
        clinicalApi.getPrescription(app.id).catch(() => null),
        clinicalApi.getAISummaries(app.id).catch(() => []),
      ]);
      setPastConsultData({ notes, rx, ai });
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingPastConsult(false);
    }
  };

  const handleOpenDecline = (app) => {
    setDeclineTarget(app);
    setDeclineRemarks('');
    setError(null);
  };

  const handleConfirmDecline = async (e) => {
    e.preventDefault();
    if (!declineTarget) return;
    if (!declineRemarks.trim()) {
      setError('Please provide remarks explaining why this appointment is being declined.');
      return;
    }
    setDeclining(true);
    setError(null);
    try {
      await appointmentApi.decline(declineTarget.id, declineRemarks.trim());
      setSuccessMsg(`Appointment #${declineTarget.id} declined. Patient has been notified and the slot released.`);
      setDeclineTarget(null);
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to decline appointment');
    } finally {
      setDeclining(false);
    }
  };

  const [activeMedRowIdx, setActiveMedRowIdx] = useState(null);
  const [rxSuggestions, setRxSuggestions] = useState([]);
  const rxDebounceRef = useRef(null);

  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (!e.target.closest('.rx-autocomplete-container')) {
        setActiveMedRowIdx(null);
      }
    };
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        setActiveMedRowIdx(null);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  const handleAddMedicationRow = () => {
    setMedications([
      ...medications,
      {
        name: '',
        dosage: '',
        frequency: 'ONCE_DAILY',
        start_date: new Date().toISOString().split('T')[0],
        end_date: new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0],
        instructions: '',
      },
    ]);
  };

  const handleRemoveMedicationRow = (idx) => {
    if (medications.length <= 1) return;
    setMedications(medications.filter((_, i) => i !== idx));
  };

  const handleMedicationChange = (idx, field, val) => {
    const updated = [...medications];
    updated[idx][field] = val;
    setMedications(updated);
  };

  const handleMedNameInput = (idx, val) => {
    handleMedicationChange(idx, 'name', val);
    setActiveMedRowIdx(idx);

    if (rxDebounceRef.current) clearTimeout(rxDebounceRef.current);

    if (!val || val.trim().length < 2) {
      setRxSuggestions([]);
      return;
    }

    rxDebounceRef.current = setTimeout(async () => {
      try {
        const data = await medicineApi.search(val.trim());
        setRxSuggestions(data.results || []);
      } catch {
        setRxSuggestions([]);
      }
    }, 250);
  };

  const handleSelectRxSuggestion = (idx, item) => {
    handleMedicationChange(idx, 'name', item.name);
    setRxSuggestions([]);
    setActiveMedRowIdx(null);
  };

  const handleSaveConsultation = async (e) => {
    e.preventDefault();
    if (!consultTarget) return;
    setSavingConsultation(true);
    setError(null);
    try {
      // 1. Save Authoritative Clinical Notes & Diagnosis
      await clinicalApi.saveClinicalNotes(consultTarget.id, {
        notes: clinicalNotes.trim(),
        diagnosis: diagnosis.trim() || null,
      });

      // 2. Save Prescription (if structured items entered)
      const validMeds = medications.filter((m) => m.name.trim() && m.dosage.trim());
      if (validMeds.length > 0) {
        await clinicalApi.createPrescription(consultTarget.id, {
          general_instructions: rxInstructions.trim() || null,
          medications: validMeds.map((m) => ({
            name: m.name.trim(),
            dosage: m.dosage.trim(),
            frequency: m.frequency,
            start_date: m.start_date,
            end_date: m.end_date,
            instructions: m.instructions.trim() || null,
          })),
        });
      }

      // 3. Complete Appointment
      await appointmentApi.complete(consultTarget.id);

      setSuccessMsg(`Consultation completed for ${consultTarget.patient_name || 'Patient'}! Post-visit summaries and reminders generated.`);
      setConsultTarget(null);
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to finalize consultation');
    } finally {
      setSavingConsultation(false);
    }
  };

  const handleNoShow = async (appId) => {
    setError(null);
    try {
      await appointmentApi.noShow(appId);
      setSuccessMsg('Appointment marked as No-Show.');
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to update appointment');
    }
  };

  const handleAddWorkingHours = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      await doctorApi.addMyWorkingHours({
        day_of_week: Number(whDay),
        start_time: whStart,
        end_time: whEnd,
      });
      setSuccessMsg('Working hours added successfully.');
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to add working hours');
    }
  };

  const handleAddLeave = async (e) => {
    e.preventDefault();
    setError(null);
    setLeaveConflicts(null);
    setSubmittingLeave(true);
    try {
      const res = await doctorApi.addMyLeave({
        start_date: leaveStart,
        end_date: leaveEnd,
        reason: leaveReason.trim(),
      });
      setSuccessMsg('Your leave request has been submitted for admin approval.');
      if (res.affected_appointments && res.affected_appointments.length > 0) {
        setLeaveConflicts(res.affected_appointments);
      }
      setLeaveStart('');
      setLeaveEnd('');
      setLeaveReason('');
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to submit leave request');
    } finally {
      setSubmittingLeave(false);
    }
  };

  const handleDeleteLeave = async (leaveId) => {
    try {
      await doctorApi.deleteMyLeave(leaveId);
      setSuccessMsg('Leave request cancelled.');
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to cancel leave request');
    }
  };

  const getDayName = (day) => {
    const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
    return days[day] || `Day ${day}`;
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'CONFIRMED':
        return <span className="user-badge" style={{ background: '#dcfce7', color: '#15803d' }}>Confirmed</span>;
      case 'HELD':
        return <span className="user-badge" style={{ background: '#fef3c7', color: '#b45309' }}>Held</span>;
      case 'COMPLETED':
        return <span className="user-badge" style={{ background: '#f3e8ff', color: '#7e22ce' }}>Completed</span>;
      case 'NO_SHOW':
        return <span className="user-badge" style={{ background: '#f1f5f9', color: '#475569' }}>No-Show</span>;
      case 'CANCELLED':
        return <span className="user-badge" style={{ background: '#fee2e2', color: '#b91c1c' }}>Cancelled</span>;
      case 'RESCHEDULED':
        return <span className="user-badge" style={{ background: '#e0e7ff', color: '#4338ca' }}>Rescheduled</span>;
      default:
        return <span className="user-badge">{status}</span>;
    }
  };

  const getLeaveStatusBadge = (status) => {
    switch (status) {
      case 'APPROVED':
        return <span className="user-badge" style={{ background: '#dcfce7', color: '#15803d', fontWeight: 700 }}>Approved</span>;
      case 'PENDING':
        return <span className="user-badge" style={{ background: '#fef3c7', color: '#b45309', fontWeight: 700 }}>Pending Review</span>;
      case 'DECLINED':
        return <span className="user-badge" style={{ background: '#fee2e2', color: '#b91c1c', fontWeight: 700 }}>Declined</span>;
      case 'CANCELLED':
        return <span className="user-badge" style={{ background: '#f1f5f9', color: '#475569' }}>Cancelled</span>;
      default:
        return <span className="user-badge">{status}</span>;
    }
  };

  const filteredAppointments = appointments.filter((app) => {
    if (apptFilter === 'all') return true;
    const appDate = new Date(app.start_time).toDateString();
    const todayStr = new Date().toDateString();
    if (apptFilter === 'today') return appDate === todayStr;
    if (apptFilter === 'upcoming') return new Date(app.start_time) > new Date() && app.status !== 'COMPLETED';
    if (apptFilter === 'completed') return app.status === 'COMPLETED';
    return true;
  });

  if (loading) {
    return (
      <div className="main-content" style={{ textAlign: 'center', padding: '4rem 2rem' }}>
        <h2 style={{ fontSize: '1.25rem', color: 'var(--text-muted)' }}>Loading Doctor Portal...</h2>
      </div>
    );
  }

  return (
    <div className="main-content">
      <div style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <ProfileAvatar
            src={user?.profile_image_url}
            name={user?.name}
            role="DOCTOR"
            size={48}
          />
          <div>
            <h1 style={{ fontSize: '1.75rem', fontWeight: 800, margin: 0 }}>{formatDoctorName(user?.name)}</h1>
            <p style={{ color: 'var(--text-muted)', margin: '0.2rem 0 0 0' }}>
              Doctor Console • {doctorProfile?.specialization || 'General Practice'} • {doctorProfile?.slot_duration || 30}m consultations
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            className={`btn ${activeTab === 'appointments' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('appointments')}
          >
            Consultations & Schedule ({appointments.length})
          </button>
          <button
            className={`btn ${activeTab === 'schedule' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('schedule')}
          >
            Working Hours
          </button>
          <button
            className={`btn ${activeTab === 'leaves' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('leaves')}
          >
            Leave Requests ({leaves.length})
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error" role="alert">{error}</div>}
      {successMsg && <div className="alert alert-success" role="status">{successMsg}</div>}

      {/* Tab 1: Appointments List */}
      {activeTab === 'appointments' && (
        <div className="card">
          <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h3 className="card-title">Patient Consultations</h3>
              <p className="card-subtitle">Perform examinations, review pre-visit AI insights, record diagnoses, and issue prescriptions</p>
            </div>
            <div style={{ display: 'flex', gap: '0.35rem' }}>
              <button className={`btn btn-sm ${apptFilter === 'all' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setApptFilter('all')}>All</button>
              <button className={`btn btn-sm ${apptFilter === 'today' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setApptFilter('today')}>Today</button>
              <button className={`btn btn-sm ${apptFilter === 'upcoming' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setApptFilter('upcoming')}>Upcoming</button>
              <button className={`btn btn-sm ${apptFilter === 'completed' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setApptFilter('completed')}>Completed</button>
            </div>
          </div>

          {filteredAppointments.length === 0 ? (
            <p style={{ color: 'var(--text-muted)', padding: '2.5rem 0', textAlign: 'center' }}>
              No appointments matching the selected view.
            </p>
          ) : (
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Patient Name</th>
                    <th>Date & Time</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredAppointments.map((app) => (
                    <tr key={app.id}>
                      <td style={{ fontWeight: 600 }}>{app.patient_name || `Patient #${app.patient_id}`}</td>
                      <td>
                        <div>{new Date(app.start_time).toLocaleDateString()}</div>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                          {new Date(app.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} -{' '}
                          {new Date(app.end_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>
                      </td>
                      <td>{getStatusBadge(app.status)}</td>
                      <td>
                        {app.status === 'CONFIRMED' && (
                          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                            <button
                              className="btn btn-primary btn-sm"
                              onClick={() => handleOpenConsultation(app)}
                            >
                              🩺 Begin Consultation
                            </button>
                            <button
                              className="btn btn-danger btn-sm"
                              onClick={() => handleOpenDecline(app)}
                            >
                              Decline
                            </button>
                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={() => handleNoShow(app.id)}
                            >
                              No-Show
                            </button>
                          </div>
                        )}
                        {app.status === 'COMPLETED' && (
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleOpenViewPast(app)}
                          >
                            📋 View Record & Rx
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Working Hours Configuration */}
      {activeTab === 'schedule' && (
        <div className="grid-2">
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">Configured Working Shifts</h3>
            </div>
            {doctorProfile?.working_hours?.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', padding: '1rem 0' }}>No shifts configured. Add working hours below.</p>
            ) : (
              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Day of Week</th>
                      <th>Shift Start</th>
                      <th>Shift End</th>
                    </tr>
                  </thead>
                  <tbody>
                    {doctorProfile?.working_hours?.map((wh) => (
                      <tr key={wh.id}>
                        <td style={{ fontWeight: 600 }}>{getDayName(wh.day_of_week)}</td>
                        <td>{wh.start_time}</td>
                        <td>{wh.end_time}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="card">
            <div className="card-header">
              <h3 className="card-title">Add Working Shift</h3>
            </div>
            <form onSubmit={handleAddWorkingHours}>
              <div className="form-group">
                <label className="form-label">Day of Week</label>
                <select className="form-select" value={whDay} onChange={(e) => setWhDay(e.target.value)}>
                  <option value="0">Monday</option>
                  <option value="1">Tuesday</option>
                  <option value="2">Wednesday</option>
                  <option value="3">Thursday</option>
                  <option value="4">Friday</option>
                  <option value="5">Saturday</option>
                  <option value="6">Sunday</option>
                </select>
              </div>
              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">Start Time</label>
                  <input type="time" className="form-input" value={whStart} onChange={(e) => setWhStart(e.target.value)} required />
                </div>
                <div className="form-group">
                  <label className="form-label">End Time</label>
                  <input type="time" className="form-input" value={whEnd} onChange={(e) => setWhEnd(e.target.value)} required />
                </div>
              </div>
              <button type="submit" className="btn btn-primary btn-block">Add Shift</button>
            </form>
          </div>
        </div>
      )}

      {/* Tab 3: Leaves Management */}
      {activeTab === 'leaves' && (
        <div>
          {leaveConflicts && (
            <div className="alert alert-error" style={{ marginBottom: '1.5rem', display: 'block' }}>
              <strong>⚠️ Potential Booking Notice</strong>
              <p style={{ fontSize: '0.85rem', marginTop: '0.25rem' }}>
                You have {leaveConflicts.length} scheduled appointment(s) during requested dates. The request is submitted as PENDING review.
              </p>
            </div>
          )}

          <div className="grid-2">
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">Submitted Leave Requests</h3>
                <p className="card-subtitle">Track administrator reviews and decision remarks</p>
              </div>
              {leaves.length === 0 ? (
                <p style={{ color: 'var(--text-muted)', padding: '1.5rem 0', textAlign: 'center' }}>No leave requests submitted yet.</p>
              ) : (
                <div className="table-container">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Dates</th>
                        <th>Reason</th>
                        <th>Status</th>
                        <th>Admin Remarks</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {leaves.map((l) => (
                        <tr key={l.id}>
                          <td style={{ fontSize: '0.85rem' }}>
                            <strong>{l.start_date}</strong> to <strong>{l.end_date}</strong>
                          </td>
                          <td style={{ fontSize: '0.85rem' }}>{l.reason || 'Personal'}</td>
                          <td>{getLeaveStatusBadge(l.status)}</td>
                          <td style={{ fontSize: '0.8rem', color: l.admin_remarks ? 'var(--text-main)' : 'var(--text-muted)' }}>
                            {l.admin_remarks || '—'}
                          </td>
                          <td>
                            {l.status === 'PENDING' && (
                              <button className="btn btn-secondary btn-sm" onClick={() => handleDeleteLeave(l.id)}>
                                Cancel Request
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="card">
              <div className="card-header">
                <h3 className="card-title">Request Absence / Leave</h3>
                <p className="card-subtitle">Submits a request to the administrator for review before blocking schedule</p>
              </div>
              <form onSubmit={handleAddLeave}>
                <div className="grid-2">
                  <div className="form-group">
                    <label className="form-label">Start Date *</label>
                    <input type="date" className="form-input" value={leaveStart} onChange={(e) => setLeaveStart(e.target.value)} required />
                  </div>
                  <div className="form-group">
                    <label className="form-label">End Date *</label>
                    <input type="date" className="form-input" value={leaveEnd} onChange={(e) => setLeaveEnd(e.target.value)} required />
                  </div>
                </div>
                <div className="form-group">
                  <label className="form-label">Reason *</label>
                  <input type="text" className="form-input" placeholder="e.g. Annual Medical Conference / Family Emergency" value={leaveReason} onChange={(e) => setLeaveReason(e.target.value)} required />
                </div>
                <button type="submit" className="btn btn-primary btn-block" disabled={submittingLeave}>
                  {submittingLeave ? 'Submitting...' : 'Submit Leave Request'}
                </button>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Appointment Decline Modal */}
      {declineTarget && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card" style={{ maxWidth: '480px', width: '90%' }}>
            <div className="card-header">
              <h3 className="card-title">Decline Patient Appointment</h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setDeclineTarget(null)}>✕</button>
            </div>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
              Decline consultation with <strong>{declineTarget.patient_name || `Patient #${declineTarget.patient_id}`}</strong> scheduled on <strong>{new Date(declineTarget.start_time).toLocaleString()}</strong>.
            </p>
            <form onSubmit={handleConfirmDecline}>
              <div className="form-group">
                <label className="form-label">Decline Remarks (Provided to Patient) *</label>
                <textarea
                  className="form-textarea"
                  rows={3}
                  placeholder="e.g. Due to an urgent clinical emergency, I am unable to attend this consultation. Please select another slot."
                  value={declineRemarks}
                  onChange={(e) => setDeclineRemarks(e.target.value)}
                  required
                />
              </div>
              <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setDeclineTarget(null)}>Cancel</button>
                <button type="submit" className="btn btn-danger" disabled={declining}>
                  {declining ? 'Declining...' : 'Confirm Decline & Release Slot'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Active Doctor Consultation Modal */}
      {consultTarget && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card" style={{ maxWidth: '800px', width: '95%', maxHeight: '90vh', overflowY: 'auto' }}>
            <div className="card-header">
              <div>
                <h3 className="card-title">Clinical Consultation: {consultTarget.patient_name || 'Patient'}</h3>
                <p className="card-subtitle">Appointment #{consultTarget.id} • {new Date(consultTarget.start_time).toLocaleString()}</p>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={() => setConsultTarget(null)}>✕</button>
            </div>

            {loadingPreconsult ? (
              <p style={{ color: 'var(--text-muted)', padding: '2rem 0', textAlign: 'center' }}>Loading pre-visit intake and clinical records...</p>
            ) : (
              <div>
                {/* Pre-Visit AI Insights & Patient Symptoms Panel */}
                <div style={{ background: '#f8fafc', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border)', marginBottom: '1.5rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <h4 style={{ fontSize: '0.95rem', fontWeight: 700 }}>📋 Pre-Visit Intake & AI Summary</h4>
                    {aiPrevisit && (
                      <span className="user-badge" style={{
                        background: aiPrevisit.urgency_level === 'High' ? '#fee2e2' : aiPrevisit.urgency_level === 'Medium' ? '#fef3c7' : '#dcfce7',
                        color: aiPrevisit.urgency_level === 'High' ? '#b91c1c' : aiPrevisit.urgency_level === 'Medium' ? '#b45309' : '#15803d',
                        fontWeight: 700,
                      }}>
                        AI Urgency: {aiPrevisit.urgency_level}
                      </span>
                    )}
                  </div>

                  <div style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                    <strong>Patient-Reported Symptoms:</strong> {patientSymptoms ? patientSymptoms.symptoms : 'No pre-visit symptoms submitted.'}
                  </div>

                  {patientSymptoms?.chief_complaint && (
                    <div style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                      <strong>Chief Complaint:</strong> {patientSymptoms.chief_complaint}
                    </div>
                  )}

                  {aiPrevisit && aiPrevisit.suggested_questions?.length > 0 && (
                    <div style={{ marginTop: '0.75rem' }}>
                      <strong style={{ fontSize: '0.85rem' }}>Suggested Diagnostic Questions (AI-Generated):</strong>
                      <ul style={{ marginLeft: '1.2rem', marginTop: '0.25rem', fontSize: '0.8rem', color: '#0369a1' }}>
                        {aiPrevisit.suggested_questions.map((q, idx) => (
                          <li key={idx}>{q}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                {/* Consultation Form */}
                <form onSubmit={handleSaveConsultation}>
                  <div className="form-group">
                    <label className="form-label">Primary Diagnosis (Doctor Authoritative) *</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="e.g. Contact Dermatitis / Acute Bronchitis"
                      value={diagnosis}
                      onChange={(e) => setDiagnosis(e.target.value)}
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Clinical Examination & Assessment Notes *</label>
                    <textarea
                      className="form-textarea"
                      rows={3}
                      placeholder="Enter detailed clinical examination findings, vitals, and physician observations..."
                      value={clinicalNotes}
                      onChange={(e) => setClinicalNotes(e.target.value)}
                      required
                    />
                  </div>

                  {/* Multi-Medication Structured Prescription Builder */}
                  <div style={{ marginTop: '1.5rem', marginBottom: '1.5rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                      <h4 style={{ fontSize: '0.95rem', fontWeight: 700 }}>Structured Prescription Items</h4>
                      <button type="button" className="btn btn-secondary btn-sm" onClick={handleAddMedicationRow}>
                        + Add Medicine
                      </button>
                    </div>

                    {medications.map((m, idx) => (
                      <div key={idx} style={{ background: '#ffffff', padding: '0.75rem', borderRadius: '8px', border: '1px solid var(--border)', marginBottom: '0.75rem' }}>
                        <div className="grid-3" style={{ marginBottom: '0.5rem' }}>
                          <div className="form-group rx-autocomplete-container" style={{ marginBottom: 0, position: 'relative' }}>
                            <label className="form-label">Medicine Name</label>
                            <input
                              type="text"
                              className="form-input"
                              placeholder="e.g. Amoxicillin / Cetirizine..."
                              value={m.name}
                              onChange={(e) => handleMedNameInput(idx, e.target.value)}
                              onFocus={() => {
                                if (m.name && m.name.length >= 2) handleMedNameInput(idx, m.name);
                              }}
                            />
                            {activeMedRowIdx === idx && rxSuggestions.length > 0 && (
                              <div
                                style={{
                                  position: 'absolute',
                                  top: '100%',
                                  left: 0,
                                  right: 0,
                                  background: '#ffffff',
                                  border: '1px solid var(--border)',
                                  borderRadius: '6px',
                                  boxShadow: '0 8px 20px rgba(0,0,0,0.15)',
                                  zIndex: 100,
                                  maxHeight: '180px',
                                  overflowY: 'auto',
                                }}
                              >
                                {rxSuggestions.map((s) => (
                                  <div
                                    key={s.rxcui}
                                    style={{
                                      padding: '0.5rem 0.75rem',
                                      cursor: 'pointer',
                                      borderBottom: '1px solid #f1f5f9',
                                      fontSize: '0.825rem',
                                      display: 'flex',
                                      justifyContent: 'space-between',
                                      alignItems: 'center',
                                    }}
                                    onMouseDown={() => handleSelectRxSuggestion(idx, s)}
                                  >
                                    <span style={{ fontWeight: 600 }}>{s.name}</span>
                                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                      Select →
                                    </span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                          <div className="form-group" style={{ marginBottom: 0 }}>
                            <label className="form-label">Dosage</label>
                            <input
                              type="text"
                              className="form-input"
                              placeholder="e.g. 1 tablet"
                              value={m.dosage}
                              onChange={(e) => handleMedicationChange(idx, 'dosage', e.target.value)}
                            />
                          </div>
                          <div className="form-group" style={{ marginBottom: 0 }}>
                            <label className="form-label">Frequency</label>
                            <select
                              className="form-select"
                              value={m.frequency}
                              onChange={(e) => handleMedicationChange(idx, 'frequency', e.target.value)}
                            >
                              <option value="ONCE_DAILY">Once Daily (09:00)</option>
                              <option value="TWICE_DAILY">Twice Daily (09:00, 21:00)</option>
                              <option value="THREE_TIMES_DAILY">Three Times Daily</option>
                              <option value="AFTER_MEAL">After Meals</option>
                              <option value="BEDTIME">At Bedtime</option>
                            </select>
                          </div>
                        </div>
                        <div className="grid-2">
                          <div className="form-group" style={{ marginBottom: 0 }}>
                            <label className="form-label">Treatment Period</label>
                            <div style={{ display: 'flex', gap: '0.5rem' }}>
                              <input
                                type="date"
                                className="form-input"
                                value={m.start_date}
                                onChange={(e) => handleMedicationChange(idx, 'start_date', e.target.value)}
                              />
                              <input
                                type="date"
                                className="form-input"
                                value={m.end_date}
                                onChange={(e) => handleMedicationChange(idx, 'end_date', e.target.value)}
                              />
                            </div>
                          </div>
                          <div className="form-group" style={{ marginBottom: 0 }}>
                            <label className="form-label">Patient Instructions & Actions</label>
                            <div style={{ display: 'flex', gap: '0.5rem' }}>
                              <input
                                type="text"
                                className="form-input"
                                placeholder="e.g. Take with plenty of water"
                                value={m.instructions}
                                onChange={(e) => handleMedicationChange(idx, 'instructions', e.target.value)}
                              />
                              {medications.length > 1 && (
                                <button
                                  type="button"
                                  className="btn btn-danger btn-sm"
                                  onClick={() => handleRemoveMedicationRow(idx)}
                                >
                                  ✕
                                </button>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="form-group">
                    <label className="form-label">General Care & Follow-Up Instructions</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="e.g. Rest, maintain hydration, contact clinic if symptoms persist after 5 days"
                      value={rxInstructions}
                      onChange={(e) => setRxInstructions(e.target.value)}
                    />
                  </div>

                  <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', marginTop: '1.5rem' }}>
                    <button type="button" className="btn btn-secondary" onClick={() => setConsultTarget(null)}>Cancel</button>
                    <button type="submit" className="btn btn-primary" disabled={savingConsultation}>
                      {savingConsultation ? 'Saving & Finalizing...' : 'Complete Consultation & Generate Summaries'}
                    </button>
                  </div>
                </form>
              </div>
            )}
          </div>
        </div>
      )}

      {/* View Past Consultation Modal */}
      {viewPastTarget && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card" style={{ maxWidth: '640px', width: '90%', maxHeight: '85vh', overflowY: 'auto' }}>
            <div className="card-header">
              <div>
                <h3 className="card-title">Completed Consultation Record</h3>
                <p className="card-subtitle">{viewPastTarget.patient_name || `Patient #${viewPastTarget.patient_id}`} • {new Date(viewPastTarget.start_time).toLocaleDateString()}</p>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={() => setViewPastTarget(null)}>✕</button>
            </div>

            {loadingPastConsult ? (
              <p style={{ color: 'var(--text-muted)', padding: '2rem 0', textAlign: 'center' }}>Loading medical record...</p>
            ) : (
              <div>
                {/* Clinical Notes */}
                <div style={{ marginBottom: '1.5rem' }}>
                  <h4 style={{ fontSize: '0.95rem', fontWeight: 700 }}>Doctor Authoritative Assessment</h4>
                  <div style={{ background: '#f8fafc', padding: '0.75rem', borderRadius: '8px', border: '1px solid var(--border)', marginTop: '0.5rem' }}>
                    <div><strong>Diagnosis:</strong> {pastConsultData.notes?.diagnosis || 'General Evaluation'}</div>
                    <div style={{ marginTop: '0.25rem', fontSize: '0.875rem' }}>{pastConsultData.notes?.notes}</div>
                  </div>
                </div>

                {/* Prescribed Medications */}
                {pastConsultData.rx && pastConsultData.rx.medications?.length > 0 && (
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
                          </tr>
                        </thead>
                        <tbody>
                          {pastConsultData.rx.medications.map((m) => (
                            <tr key={m.id}>
                              <td style={{ fontWeight: 600 }}>{m.name}</td>
                              <td>{m.dosage}</td>
                              <td>{m.frequency}</td>
                              <td>{m.start_date} to {m.end_date}</td>
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
    </div>
  );
}
