import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { adminApi, doctorApi, appointmentApi } from '../api/client';
import { formatDoctorName } from '../utils/format';
import { ProfileAvatar } from '../components/ProfileAvatar';

export function AdminDashboard() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [stats, setStats] = useState(null);
  const [reliabilityMetrics, setReliabilityMetrics] = useState(null);
  const [patients, setPatients] = useState([]);
  const [patientSearch, setPatientSearch] = useState('');
  const [loadingPatients, setLoadingPatients] = useState(false);
  const [doctors, setDoctors] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [leaveRequests, setLeaveRequests] = useState([]);
  const [leaveFilter, setLeaveFilter] = useState('ALL'); // 'ALL' | 'PENDING' | 'APPROVED' | 'DECLINED'
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'overview'); // 'overview' | 'users' | 'patients' | 'doctors' | 'leaves' | 'appointments' | 'reliability' | 'audit'
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // User Profiles Tab state
  const [allUsers, setAllUsers] = useState([]);
  const [userSearch, setUserSearch] = useState('');
  const [userRoleFilter, setUserRoleFilter] = useState('ALL');
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [selectedUserDetail, setSelectedUserDetail] = useState(null);
  const [loadingUserDetail, setLoadingUserDetail] = useState(false);

  // New User Form state
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    role: 'DOCTOR',
    specialization: 'General Medicine',
    bio: '',
    slot_duration: 30,
  });
  const [submitting, setSubmitting] = useState(false);

  // Doctor Edit Modal
  const [editDoctor, setEditDoctor] = useState(null);
  const [editSpec, setEditSpec] = useState('');
  const [editBio, setEditBio] = useState('');
  const [editDuration, setEditDuration] = useState(30);

  // Admin Leave Assignment Modal
  const [leaveDoctor, setLeaveDoctor] = useState(null);
  const [adminLeaveStart, setAdminLeaveStart] = useState('');
  const [adminLeaveEnd, setAdminLeaveEnd] = useState('');
  const [adminLeaveReason, setAdminLeaveReason] = useState('');
  const [leaveConflicts, setLeaveConflicts] = useState(null);

  // Leave Request Review Modal
  const [reviewTarget, setReviewTarget] = useState(null);
  const [reviewRemarks, setReviewRemarks] = useState('');
  const [reviewingLeave, setReviewingLeave] = useState(false);

  const fetchAdminData = async () => {
    try {
      const [statsData, doctorsData, appointmentsData, logsData, metricsData, patientsData, leavesData, usersData] = await Promise.all([
        adminApi.getDashboard(),
        doctorApi.list(),
        appointmentApi.list(),
        adminApi.getAuditLogs(25),
        adminApi.getReliabilityMetrics().catch(() => null),
        adminApi.getPatients(patientSearch).catch(() => []),
        adminApi.getLeaveRequests().catch(() => []),
        adminApi.getUsers(userSearch, userRoleFilter).catch(() => []),
      ]);
      setStats(statsData);
      setDoctors(doctorsData);
      setAppointments(appointmentsData);
      setAuditLogs(logsData);
      setReliabilityMetrics(metricsData);
      setPatients(patientsData);
      setLeaveRequests(leavesData);
      setAllUsers(usersData);
    } catch (err) {
      console.error('Failed to load admin data:', err);
      setError(err.message || 'Error loading administrator dashboard');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAdminData();
  }, []);

  useEffect(() => {
    const tabFromUrl = searchParams.get('tab');
    if (tabFromUrl && tabFromUrl !== activeTab) {
      setActiveTab(tabFromUrl);
    }
  }, [searchParams]);

  const handleTabChange = (tabName) => {
    setActiveTab(tabName);
    setSearchParams({ tab: tabName });
    setError(null);
    setSuccessMsg(null);
    if (tabName === 'users') {
      fetchUsers(userSearch, userRoleFilter);
    }
  };

  const fetchUsers = async (search, role) => {
    setLoadingUsers(true);
    try {
      const data = await adminApi.getUsers(search, role);
      setAllUsers(data);
    } catch (err) {
      console.error('Failed to fetch users:', err);
    } finally {
      setLoadingUsers(false);
    }
  };

  const handleSearchUsers = (e) => {
    e.preventDefault();
    fetchUsers(userSearch, userRoleFilter);
  };

  const handleRoleFilterChange = (role) => {
    setUserRoleFilter(role);
    fetchUsers(userSearch, role);
  };

  const handleViewUserProfile = async (userId) => {
    setLoadingUserDetail(true);
    try {
      const detail = await adminApi.getUserProfile(userId);
      setSelectedUserDetail(detail);
    } catch (err) {
      setError('Failed to load user profile details.');
    } finally {
      setLoadingUserDetail(false);
    }
  };

  const handleSearchPatients = async (query) => {
    setPatientSearch(query);
    setLoadingPatients(true);
    try {
      const data = await adminApi.getPatients(query);
      setPatients(data);
    } catch (err) {
      console.error('Failed to search patients:', err);
    } finally {
      setLoadingPatients(false);
    }
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);
    setSubmitting(true);

    try {
      await adminApi.createUser(formData);
      setSuccessMsg(`Successfully provisioned new ${formData.role} account for ${formData.name}`);
      setFormData({
        name: '',
        email: '',
        password: '',
        role: 'DOCTOR',
        specialization: 'General Medicine',
        bio: '',
        slot_duration: 30,
      });
      fetchAdminData();
    } catch (err) {
      setError(err.message || 'Failed to create user account');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleDoctorStatus = async (id, currentActive) => {
    try {
      await adminApi.toggleDoctorStatus(id, !currentActive);
      fetchAdminData();
    } catch (err) {
      setError(err.message || 'Failed to update doctor active status');
    }
  };

  const handleOpenEditModal = (doctor) => {
    setEditDoctor(doctor);
    setEditSpec(doctor.specialization);
    setEditBio(doctor.bio || '');
    setEditDuration(doctor.slot_duration);
  };

  const handleSaveDoctorEdit = async (e) => {
    e.preventDefault();
    try {
      await adminApi.updateDoctor(editDoctor.id, {
        specialization: editSpec,
        bio: editBio,
        slot_duration: parseInt(editDuration, 10),
      });
      setEditDoctor(null);
      setSuccessMsg('Doctor profile settings updated successfully.');
      fetchAdminData();
    } catch (err) {
      setError(err.message || 'Failed to update doctor profile');
    }
  };

  const handleOpenLeaveModal = (doctor) => {
    setLeaveDoctor(doctor);
    setAdminLeaveStart('');
    setAdminLeaveEnd('');
    setAdminLeaveReason('');
    setLeaveConflicts(null);
  };

  const handleAssignLeave = async (e) => {
    e.preventDefault();
    try {
      const res = await adminApi.addDoctorLeave(leaveDoctor.id, {
        start_date: adminLeaveStart,
        end_date: adminLeaveEnd,
        reason: adminLeaveReason,
      });
      if (res.affected_appointments && res.affected_appointments.length > 0) {
        setLeaveConflicts(res.affected_appointments);
        setSuccessMsg(`Leave scheduled! Note: ${res.affected_appointments.length} existing patient appointments were affected.`);
      } else {
        setLeaveDoctor(null);
        setSuccessMsg('Doctor leave scheduled successfully without booking conflicts.');
        fetchAdminData();
      }
    } catch (err) {
      setError(err.message || 'Failed to schedule doctor leave');
    }
  };

  const handleOpenReview = (leave) => {
    setReviewTarget(leave);
    setReviewRemarks(leave.admin_remarks || '');
  };

  const handleApproveLeave = async () => {
    if (!reviewTarget) return;
    setReviewingLeave(true);
    try {
      await adminApi.approveLeaveRequest(reviewTarget.id, reviewRemarks);
      setSuccessMsg(`Leave request #${reviewTarget.id} approved successfully.`);
      setReviewTarget(null);
      fetchAdminData();
    } catch (err) {
      setError(err.message || 'Failed to approve leave request');
    } finally {
      setReviewingLeave(false);
    }
  };

  const handleDeclineLeave = async () => {
    if (!reviewTarget) return;
    if (!reviewRemarks || !reviewRemarks.strip()) {
      setError('Remarks are required when declining a leave request.');
      return;
    }
    setReviewingLeave(true);
    try {
      await adminApi.declineLeaveRequest(reviewTarget.id, reviewRemarks);
      setSuccessMsg(`Leave request #${reviewTarget.id} declined.`);
      setReviewTarget(null);
      fetchAdminData();
    } catch (err) {
      setError(err.message || 'Failed to decline leave request');
    } finally {
      setReviewingLeave(false);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'CONFIRMED':
        return <span className="user-badge" style={{ background: '#ecfdf5', color: '#047857', fontWeight: 600 }}>CONFIRMED</span>;
      case 'CANCELLED':
        return <span className="user-badge" style={{ background: '#fee2e2', color: '#b91c1c', fontWeight: 600 }}>CANCELLED</span>;
      case 'COMPLETED':
        return <span className="user-badge" style={{ background: '#eff6ff', color: '#1d4ed8', fontWeight: 600 }}>COMPLETED</span>;
      default:
        return <span className="user-badge">{status}</span>;
    }
  };

  const getLeaveStatusBadge = (status) => {
    switch (status) {
      case 'APPROVED':
        return <span className="user-badge" style={{ background: '#ecfdf5', color: '#047857', fontWeight: 700 }}>APPROVED</span>;
      case 'PENDING':
        return <span className="user-badge" style={{ background: '#fef3c7', color: '#b45309', fontWeight: 700 }}>PENDING REVIEW</span>;
      case 'DECLINED':
        return <span className="user-badge" style={{ background: '#fee2e2', color: '#b91c1c', fontWeight: 700 }}>DECLINED</span>;
      default:
        return <span className="user-badge">{status}</span>;
    }
  };

  const filteredLeaveRequests = leaveRequests.filter((l) => {
    if (leaveFilter === 'ALL') return true;
    return l.status === leaveFilter;
  });

  const pendingLeavesCount = leaveRequests.filter((l) => l.status === 'PENDING').length;

  if (loading) {
    return (
      <div className="main-content" style={{ maxWidth: '1200px', margin: '2rem auto', padding: '0 1rem', textAlign: 'center' }}>
        <div className="card" style={{ padding: '3rem' }}>
          <div style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--primary)' }}>Loading System Administration...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="main-content" style={{ maxWidth: '1240px', margin: '0 auto', padding: '2rem 1.5rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <ProfileAvatar
            src={user?.profile_image_url}
            name={user?.name}
            role="ADMIN"
            size={48}
          />
          <div>
            <h1 style={{ fontSize: '1.85rem', fontWeight: 800, margin: 0, color: 'var(--text-main)' }}>
              System Administration Console
            </h1>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', margin: '0.25rem 0 0 0' }}>
              Multi-clinic operations, staff provisioning, user profiles, clinical leaves, and reliability metrics.
            </p>
          </div>
        </div>
        <span className="user-badge badge-admin" style={{ fontSize: '0.85rem', padding: '4px 10px' }}>
          ROOT ADMINISTRATOR
        </span>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '2px solid var(--border)', marginBottom: '1.5rem', overflowX: 'auto' }}>
        <button
          type="button"
          onClick={() => handleTabChange('overview')}
          style={{
            padding: '0.75rem 1.15rem',
            fontWeight: 600,
            fontSize: '0.9rem',
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'overview' ? '3px solid var(--primary)' : '3px solid transparent',
            color: activeTab === 'overview' ? 'var(--primary)' : 'var(--text-muted)',
            cursor: 'pointer',
            marginBottom: '-2px',
          }}
        >
          System Overview
        </button>

        <button
          type="button"
          onClick={() => handleTabChange('users')}
          style={{
            padding: '0.75rem 1.15rem',
            fontWeight: 600,
            fontSize: '0.9rem',
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'users' ? '3px solid var(--primary)' : '3px solid transparent',
            color: activeTab === 'users' ? 'var(--primary)' : 'var(--text-muted)',
            cursor: 'pointer',
            marginBottom: '-2px',
          }}
        >
          User Profiles ({allUsers.length})
        </button>

        <button
          type="button"
          onClick={() => handleTabChange('patients')}
          style={{
            padding: '0.75rem 1.15rem',
            fontWeight: 600,
            fontSize: '0.9rem',
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'patients' ? '3px solid var(--primary)' : '3px solid transparent',
            color: activeTab === 'patients' ? 'var(--primary)' : 'var(--text-muted)',
            cursor: 'pointer',
            marginBottom: '-2px',
          }}
        >
          Patients Directory ({patients.length})
        </button>

        <button
          type="button"
          onClick={() => handleTabChange('doctors')}
          style={{
            padding: '0.75rem 1.15rem',
            fontWeight: 600,
            fontSize: '0.9rem',
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'doctors' ? '3px solid var(--primary)' : '3px solid transparent',
            color: activeTab === 'doctors' ? 'var(--primary)' : 'var(--text-muted)',
            cursor: 'pointer',
            marginBottom: '-2px',
          }}
        >
          Practitioners & Staff ({doctors.length})
        </button>

        <button
          type="button"
          onClick={() => handleTabChange('leaves')}
          style={{
            padding: '0.75rem 1.15rem',
            fontWeight: 600,
            fontSize: '0.9rem',
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'leaves' ? '3px solid var(--primary)' : '3px solid transparent',
            color: activeTab === 'leaves' ? 'var(--primary)' : 'var(--text-muted)',
            cursor: 'pointer',
            marginBottom: '-2px',
            display: 'flex',
            alignItems: 'center',
            gap: '0.35rem',
          }}
        >
          Leave Management
          {pendingLeavesCount > 0 && (
            <span style={{ background: '#dc2626', color: '#ffffff', borderRadius: '10px', padding: '1px 6px', fontSize: '0.75rem', fontWeight: 800 }}>
              {pendingLeavesCount}
            </span>
          )}
        </button>

        <button
          type="button"
          onClick={() => handleTabChange('appointments')}
          style={{
            padding: '0.75rem 1.15rem',
            fontWeight: 600,
            fontSize: '0.9rem',
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'appointments' ? '3px solid var(--primary)' : '3px solid transparent',
            color: activeTab === 'appointments' ? 'var(--primary)' : 'var(--text-muted)',
            cursor: 'pointer',
            marginBottom: '-2px',
          }}
        >
          Appointments Ledger
        </button>

        <button
          type="button"
          onClick={() => handleTabChange('reliability')}
          style={{
            padding: '0.75rem 1.15rem',
            fontWeight: 600,
            fontSize: '0.9rem',
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'reliability' ? '3px solid var(--primary)' : '3px solid transparent',
            color: activeTab === 'reliability' ? 'var(--primary)' : 'var(--text-muted)',
            cursor: 'pointer',
            marginBottom: '-2px',
          }}
        >
          Reliability Engine
        </button>

        <button
          type="button"
          onClick={() => handleTabChange('audit')}
          style={{
            padding: '0.75rem 1.15rem',
            fontWeight: 600,
            fontSize: '0.9rem',
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'audit' ? '3px solid var(--primary)' : '3px solid transparent',
            color: activeTab === 'audit' ? 'var(--primary)' : 'var(--text-muted)',
            cursor: 'pointer',
            marginBottom: '-2px',
          }}
        >
          Security Audit Logs
        </button>
      </div>

      {/* Notifications */}
      {error && <div className="alert alert-error" role="alert" style={{ marginBottom: '1.25rem' }}>{error}</div>}
      {successMsg && <div className="alert alert-success" role="status" style={{ marginBottom: '1.25rem', background: '#ecfdf5', color: '#065f46', border: '1px solid #a7f3d0' }}>{successMsg}</div>}

      {/* TAB 1: Overview */}
      {activeTab === 'overview' && (
        <div>
          <div className="grid-4" style={{ marginBottom: '1.5rem' }}>
            <div className="stat-card">
              <span className="stat-label">Total Registered Users</span>
              <span className="stat-value">{stats?.total_users ?? 0}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Total Patients</span>
              <span className="stat-value">{stats?.total_patients ?? 0}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Active Doctors</span>
              <span className="stat-value" style={{ color: 'var(--primary)' }}>
                {stats?.active_doctors ?? 0} / {stats?.total_doctors ?? 0}
              </span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Total Appointments</span>
              <span className="stat-value">{stats?.total_appointments ?? 0}</span>
            </div>
          </div>

          {/* User Provisioning Form */}
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">Provision Healthcare Staff Accounts</h3>
            </div>
            <form onSubmit={handleCreateUser}>
              <div className="grid-3" style={{ gap: '1rem', marginBottom: '1rem' }}>
                <div className="form-group">
                  <label className="form-label" htmlFor="prov-name">Full Name *</label>
                  <input
                    id="prov-name"
                    type="text"
                    required
                    className="form-input"
                    placeholder="e.g. Dr. John Doe"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="prov-email">Email Address *</label>
                  <input
                    id="prov-email"
                    type="email"
                    required
                    className="form-input"
                    placeholder="john.doe@hospital.com"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="prov-pwd">Initial Password * (Min 8)</label>
                  <input
                    id="prov-pwd"
                    type="password"
                    required
                    minLength={8}
                    className="form-input"
                    placeholder="••••••••"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  />
                </div>
              </div>

              <div className="grid-3" style={{ gap: '1rem', marginBottom: '1.25rem' }}>
                <div className="form-group">
                  <label className="form-label" htmlFor="prov-role">Account Role *</label>
                  <select
                    id="prov-role"
                    className="form-input"
                    value={formData.role}
                    onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  >
                    <option value="DOCTOR">DOCTOR</option>
                    <option value="ADMIN">ADMIN</option>
                  </select>
                </div>

                {formData.role === 'DOCTOR' && (
                  <>
                    <div className="form-group">
                      <label className="form-label" htmlFor="prov-spec">Specialization *</label>
                      <input
                        id="prov-spec"
                        type="text"
                        required
                        className="form-input"
                        placeholder="e.g. Cardiology"
                        value={formData.specialization}
                        onChange={(e) => setFormData({ ...formData, specialization: e.target.value })}
                      />
                    </div>

                    <div className="form-group">
                      <label className="form-label" htmlFor="prov-slot">Slot Duration (Minutes)</label>
                      <input
                        id="prov-slot"
                        type="number"
                        min="10"
                        max="120"
                        className="form-input"
                        value={formData.slot_duration}
                        onChange={(e) => setFormData({ ...formData, slot_duration: parseInt(e.target.value, 10) })}
                      />
                    </div>
                  </>
                )}
              </div>

              {formData.role === 'DOCTOR' && (
                <div className="form-group" style={{ marginBottom: '1.25rem' }}>
                  <label className="form-label" htmlFor="prov-bio">Professional Biography</label>
                  <textarea
                    id="prov-bio"
                    className="form-input"
                    rows={2}
                    placeholder="Credentials, qualifications, and clinical background..."
                    value={formData.bio}
                    onChange={(e) => setFormData({ ...formData, bio: e.target.value })}
                  />
                </div>
              )}

              <button type="submit" className="btn btn-primary" disabled={submitting}>
                {submitting ? 'Provisioning Account...' : 'Provision Account'}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* TAB 2: User Profiles (Phase 8) */}
      {activeTab === 'users' && (
        <div className="card">
          <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <h3 className="card-title" style={{ margin: 0 }}>System User Profiles & Directory</h3>

            {/* Search & Filter */}
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <form onSubmit={handleSearchUsers} style={{ display: 'flex', gap: '0.35rem' }}>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Search name, email, phone..."
                  value={userSearch}
                  onChange={(e) => setUserSearch(e.target.value)}
                  style={{ width: '220px', padding: '0.4rem 0.75rem', fontSize: '0.85rem' }}
                />
                <button type="submit" className="btn btn-secondary btn-sm">Search</button>
              </form>

              <select
                className="form-input"
                value={userRoleFilter}
                onChange={(e) => handleRoleFilterChange(e.target.value)}
                style={{ width: '130px', padding: '0.4rem 0.5rem', fontSize: '0.85rem' }}
              >
                <option value="ALL">All Roles</option>
                <option value="PATIENT">Patients</option>
                <option value="DOCTOR">Doctors</option>
                <option value="ADMIN">Admins</option>
              </select>
            </div>
          </div>

          {loadingUsers ? (
            <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>Loading users...</div>
          ) : allUsers.length > 0 ? (
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Registered</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {allUsers.map((u) => (
                    <tr key={u.id}>
                      <td>#{u.id}</td>
                      <td style={{ fontWeight: 600 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                          <ProfileAvatar src={u.profile_image_url} name={u.name} role={u.role} size={28} />
                          <span>{u.role === 'DOCTOR' ? formatDoctorName(u.name) : u.name}</span>
                        </div>
                      </td>
                      <td style={{ fontSize: '0.85rem' }}>{u.email}</td>
                      <td>
                        <span className={`user-badge ${u.role === 'PATIENT' ? 'badge-patient' : u.role === 'DOCTOR' ? 'badge-doctor' : 'badge-admin'}`}>
                          {u.role}
                        </span>
                      </td>
                      <td>
                        <span style={{ fontSize: '0.75rem', color: u.status === 'active' ? '#047857' : '#b91c1c', fontWeight: 600 }}>
                          {u.status}
                        </span>
                      </td>
                      <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        {new Date(u.created_at).toLocaleDateString()}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleViewUserProfile(u.id)}
                          style={{ fontSize: '0.8rem' }}
                        >
                          View Profile
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
              No users match your search criteria.
            </div>
          )}
        </div>
      )}

      {/* TAB 3: Patients Directory */}
      {activeTab === 'patients' && (
        <div className="card">
          <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <h3 className="card-title" style={{ margin: 0 }}>Registered Patients Directory</h3>
            <input
              type="text"
              className="form-input"
              placeholder="Search by name, email, or phone..."
              value={patientSearch}
              onChange={(e) => handleSearchPatients(e.target.value)}
              style={{ width: '280px', padding: '0.45rem 0.75rem', fontSize: '0.85rem' }}
            />
          </div>

          {loadingPatients ? (
            <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>Searching patients...</div>
          ) : patients.length > 0 ? (
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Patient ID</th>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Phone</th>
                    <th>Total Bookings</th>
                    <th>Registered</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {patients.map((p) => (
                    <tr key={p.id}>
                      <td>#{p.id}</td>
                      <td style={{ fontWeight: 600 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                          <ProfileAvatar src={p.profile_image_url} name={p.name} role="PATIENT" size={28} />
                          <span>{p.name}</span>
                        </div>
                      </td>
                      <td style={{ fontSize: '0.85rem' }}>{p.email}</td>
                      <td style={{ fontSize: '0.85rem' }}>{p.phone || '—'}</td>
                      <td><span className="user-badge">{p.appointments_count} visit(s)</span></td>
                      <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        {new Date(p.created_at).toLocaleDateString()}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleViewUserProfile(p.user_id)}
                          style={{ fontSize: '0.8rem' }}
                        >
                          View Profile
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
              No patients found matching search query.
            </div>
          )}
        </div>
      )}

      {/* TAB 4: Doctors */}
      {activeTab === 'doctors' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Practitioners & Clinical Staff Roster</h3>
          </div>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Doctor</th>
                  <th>Specialization</th>
                  <th>Slot Duration</th>
                  <th>Status</th>
                  <th>Working Hours</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {doctors.map((d) => (
                  <tr key={d.id}>
                    <td style={{ fontWeight: 600 }}>{formatDoctorName(d.name)}</td>
                    <td><span className="user-badge badge-doctor">{d.specialization}</span></td>
                    <td>{d.slot_duration} mins</td>
                    <td>
                      <span style={{ fontSize: '0.8rem', fontWeight: 600, color: d.active ? '#047857' : '#dc2626' }}>
                        {d.active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      {d.working_hours?.length > 0 ? `${d.working_hours.length} shifts configured` : 'No shifts set'}
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                        <button className="btn btn-secondary btn-sm" onClick={() => handleOpenEditModal(d)}>
                          Edit Settings
                        </button>
                        <button className="btn btn-secondary btn-sm" onClick={() => handleOpenLeaveModal(d)}>
                          Assign Leave
                        </button>
                        <button
                          className={`btn btn-sm ${d.active ? 'btn-danger' : 'btn-primary'}`}
                          onClick={() => handleToggleDoctorStatus(d.id, d.active)}
                        >
                          {d.active ? 'Deactivate' : 'Activate'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 5: Leaves */}
      {activeTab === 'leaves' && (
        <div className="card">
          <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <h3 className="card-title" style={{ margin: 0 }}>Doctor Leave Requests & Absence Ledger</h3>
            <div style={{ display: 'flex', gap: '0.35rem' }}>
              {['ALL', 'PENDING', 'APPROVED', 'DECLINED'].map((st) => (
                <button
                  key={st}
                  type="button"
                  onClick={() => setLeaveFilter(st)}
                  className={`btn btn-sm ${leaveFilter === st ? 'btn-primary' : 'btn-secondary'}`}
                >
                  {st}
                </button>
              ))}
            </div>
          </div>

          {filteredLeaveRequests.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
              No leave records found for filter: <strong>{leaveFilter}</strong>.
            </div>
          ) : (
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Doctor</th>
                    <th>Specialization</th>
                    <th>Date Range</th>
                    <th>Reason</th>
                    <th>Status</th>
                    <th>Affected Visits</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredLeaveRequests.map((l) => (
                    <tr key={l.id}>
                      <td style={{ fontWeight: 600 }}>{formatDoctorName(l.doctor_name)}</td>
                      <td><span className="user-badge badge-doctor">{l.doctor_specialization}</span></td>
                      <td style={{ fontSize: '0.85rem' }}>
                        <div><strong>{l.start_date}</strong> to <strong>{l.end_date}</strong></div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Req: {new Date(l.requested_at).toLocaleDateString()}</div>
                      </td>
                      <td style={{ fontSize: '0.85rem' }}>{l.reason || 'Personal'}</td>
                      <td>{getLeaveStatusBadge(l.status)}</td>
                      <td>
                        {l.affected_appointments_count > 0 ? (
                          <span className="user-badge" style={{ background: '#fee2e2', color: '#b91c1c', fontWeight: 700 }}>
                            ⚠️ {l.affected_appointments_count} visit(s)
                          </span>
                        ) : (
                          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>None</span>
                        )}
                      </td>
                      <td>
                        {l.status === 'PENDING' ? (
                          <button className="btn btn-primary btn-sm" onClick={() => handleOpenReview(l)}>
                            Review Request
                          </button>
                        ) : (
                          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                            {l.admin_remarks ? `Remarks: ${l.admin_remarks}` : 'Completed'}
                          </span>
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

      {/* TAB 6: Appointments Ledger */}
      {activeTab === 'appointments' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">System Appointments Ledger</h3>
          </div>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Patient</th>
                  <th>Doctor</th>
                  <th>Date & Time</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {appointments.map((a) => (
                  <tr key={a.id}>
                    <td>#{a.id}</td>
                    <td>{a.patient_name || `Patient #${a.patient_id}`}</td>
                    <td>{formatDoctorName(a.doctor_name)}</td>
                    <td>
                      {new Date(a.start_time).toLocaleDateString()} {new Date(a.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </td>
                    <td>{getStatusBadge(a.status)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 7: Reliability Engine */}
      {activeTab === 'reliability' && (
        <div>
          <div className="grid-4" style={{ marginBottom: '1.5rem' }}>
            <div className="stat-card">
              <span className="stat-label">AI Summaries (Completed)</span>
              <span className="stat-value" style={{ color: 'var(--primary)' }}>{reliabilityMetrics?.ai_jobs?.COMPLETED ?? 0}</span>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                Failed: {reliabilityMetrics?.ai_jobs?.FAILED ?? 0} | Processing: {reliabilityMetrics?.ai_jobs?.PROCESSING ?? 0}
              </div>
            </div>
            <div className="stat-card">
              <span className="stat-label">Notifications Sent</span>
              <span className="stat-value" style={{ color: '#047857' }}>{reliabilityMetrics?.notifications?.SENT ?? 0}</span>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                Queued: {reliabilityMetrics?.notifications?.QUEUED ?? 0} | Failed: {reliabilityMetrics?.notifications?.FAILED ?? 0}
              </div>
            </div>
            <div className="stat-card">
              <span className="stat-label">Calendar Syncs</span>
              <span className="stat-value" style={{ color: 'var(--primary)' }}>{reliabilityMetrics?.calendar_syncs?.SYNCED ?? 0}</span>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                Pending: {reliabilityMetrics?.calendar_syncs?.PENDING ?? 0} | Failed: {reliabilityMetrics?.calendar_syncs?.FAILED ?? 0}
              </div>
            </div>
            <div className="stat-card">
              <span className="stat-label">Med Reminders Dispatched</span>
              <span className="stat-value">{reliabilityMetrics?.medication_reminders?.SENT ?? 0}</span>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                Pending: {reliabilityMetrics?.medication_reminders?.PENDING ?? 0}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 8: Security Audit Logs */}
      {activeTab === 'audit' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Security & System Audit Trail</h3>
          </div>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Action</th>
                  <th>Resource</th>
                  <th>User ID</th>
                  <th>IP Address</th>
                </tr>
              </thead>
              <tbody>
                {auditLogs.map((log) => (
                  <tr key={log.id}>
                    <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{new Date(log.created_at).toLocaleString()}</td>
                    <td><span className="user-badge">{log.action}</span></td>
                    <td>{log.resource}</td>
                    <td>{log.user_id ? `#${log.user_id}` : 'System'}</td>
                    <td style={{ fontSize: '0.85rem' }}>{log.ip_address || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* User Profile Detail Modal (Phase 8) */}
      {selectedUserDetail && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1rem' }}>
          <div className="card" style={{ maxWidth: '680px', width: '100%', maxHeight: '90vh', overflowY: 'auto', padding: '1.75rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <ProfileAvatar
                  src={selectedUserDetail.user.profile_image_url}
                  name={selectedUserDetail.user.name}
                  role={selectedUserDetail.user.role}
                  size={52}
                />
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.3rem', fontWeight: 800 }}>
                    User Profile #{selectedUserDetail.user.id}: {selectedUserDetail.user.name}
                  </h3>
                  <span className={`user-badge ${selectedUserDetail.user.role === 'PATIENT' ? 'badge-patient' : selectedUserDetail.user.role === 'DOCTOR' ? 'badge-doctor' : 'badge-admin'}`} style={{ marginTop: '4px', display: 'inline-block' }}>
                    {selectedUserDetail.user.role}
                  </span>
                </div>
              </div>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => setSelectedUserDetail(null)}>✕ Close</button>
            </div>

            {/* Basic Info */}
            <div style={{ background: '#f8fafc', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border)', marginBottom: '1.25rem' }}>
              <div className="grid-2" style={{ gap: '0.75rem', fontSize: '0.9rem' }}>
                <div><strong>Email:</strong> {selectedUserDetail.user.email}</div>
                <div><strong>Phone:</strong> {selectedUserDetail.user.phone || '—'}</div>
                <div><strong>Date of Birth:</strong> {selectedUserDetail.user.date_of_birth || '—'}</div>
                <div><strong>Age:</strong> {selectedUserDetail.user.age !== null ? `${selectedUserDetail.user.age} yrs` : '—'}</div>
                <div><strong>Status:</strong> {selectedUserDetail.user.status}</div>
                <div><strong>Registered:</strong> {new Date(selectedUserDetail.user.created_at).toLocaleDateString()}</div>
              </div>
            </div>

            {/* Medical Profile Section (If Patient) */}
            {selectedUserDetail.user.role === 'PATIENT' && selectedUserDetail.medical_profile && (
              <div style={{ marginBottom: '1.25rem', border: '1px solid var(--border)', borderRadius: '8px', padding: '1rem' }}>
                <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '1.05rem', fontWeight: 700, color: 'var(--primary)' }}>
                  Patient Medical Profile
                </h4>
                <div className="grid-3" style={{ gap: '0.5rem', fontSize: '0.875rem', marginBottom: '0.75rem' }}>
                  <div><strong>Blood Group:</strong> {selectedUserDetail.medical_profile.blood_group || '—'}</div>
                  <div><strong>Height:</strong> {selectedUserDetail.medical_profile.height_cm ? `${selectedUserDetail.medical_profile.height_cm} cm` : '—'}</div>
                  <div><strong>Weight:</strong> {selectedUserDetail.medical_profile.weight_kg ? `${selectedUserDetail.medical_profile.weight_kg} kg` : '—'}</div>
                </div>
                <div style={{ fontSize: '0.85rem', lineHeight: 1.5 }}>
                  {selectedUserDetail.medical_profile.allergies && <div><strong>Allergies:</strong> {selectedUserDetail.medical_profile.allergies}</div>}
                  {selectedUserDetail.medical_profile.chronic_conditions && <div><strong>Conditions:</strong> {selectedUserDetail.medical_profile.chronic_conditions}</div>}
                  {selectedUserDetail.medical_profile.current_medications && <div><strong>Medications:</strong> {selectedUserDetail.medical_profile.current_medications}</div>}
                  {selectedUserDetail.medical_profile.past_surgeries && <div><strong>Past Surgeries:</strong> {selectedUserDetail.medical_profile.past_surgeries}</div>}
                  {selectedUserDetail.medical_profile.family_history && <div><strong>Family History:</strong> {selectedUserDetail.medical_profile.family_history}</div>}
                  {selectedUserDetail.medical_profile.medical_notes && <div><strong>Notes:</strong> {selectedUserDetail.medical_profile.medical_notes}</div>}
                </div>
              </div>
            )}

            {/* Doctor Clinical Profile Section (If Doctor) */}
            {selectedUserDetail.user.role === 'DOCTOR' && selectedUserDetail.doctor && (
              <div style={{ marginBottom: '1.25rem', border: '1px solid var(--border)', borderRadius: '8px', padding: '1rem' }}>
                <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '1.05rem', fontWeight: 700, color: 'var(--primary)' }}>
                  Practitioner Details
                </h4>
                <div style={{ fontSize: '0.9rem', lineHeight: 1.6 }}>
                  <div><strong>Specialization:</strong> {selectedUserDetail.doctor.specialization}</div>
                  <div><strong>Slot Duration:</strong> {selectedUserDetail.doctor.slot_duration} minutes</div>
                  <div><strong>Active:</strong> {selectedUserDetail.doctor.active ? 'Yes' : 'No'}</div>
                  {selectedUserDetail.doctor.bio && <div><strong>Bio:</strong> {selectedUserDetail.doctor.bio}</div>}
                </div>
              </div>
            )}

            {/* Recent Appointments */}
            {selectedUserDetail.recent_appointments?.length > 0 && (
              <div>
                <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '1rem', fontWeight: 700 }}>
                  Recent Appointments ({selectedUserDetail.appointments_count})
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '200px', overflowY: 'auto' }}>
                  {selectedUserDetail.recent_appointments.map((a) => (
                    <div key={a.id} style={{ border: '1px solid var(--border)', borderRadius: '6px', padding: '0.6rem 0.8rem', fontSize: '0.825rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <strong>#{a.id}</strong> {new Date(a.start_time).toLocaleDateString()} with {a.doctor_name || a.patient_name}
                      </div>
                      <span className="user-badge">{a.status}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Doctor Edit Modal */}
      {editDoctor && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card" style={{ maxWidth: '500px', width: '90%' }}>
            <div className="card-header">
              <h3 className="card-title">Edit {formatDoctorName(editDoctor.name)} Settings</h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setEditDoctor(null)}>✕</button>
            </div>
            <form onSubmit={handleSaveDoctorEdit}>
              <div className="form-group">
                <label className="form-label">Specialization</label>
                <input type="text" className="form-input" value={editSpec} onChange={(e) => setEditSpec(e.target.value)} required />
              </div>
              <div className="form-group">
                <label className="form-label">Bio</label>
                <textarea className="form-textarea" rows={3} value={editBio} onChange={(e) => setEditBio(e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Slot Duration (Minutes)</label>
                <input type="number" min="10" max="120" className="form-input" value={editDuration} onChange={(e) => setEditDuration(e.target.value)} required />
              </div>
              <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setEditDoctor(null)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Save Changes</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Doctor Leave Assignment Modal */}
      {leaveDoctor && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card" style={{ maxWidth: '520px', width: '90%', maxHeight: '85vh', overflowY: 'auto' }}>
            <div className="card-header">
              <h3 className="card-title">Assign Absence for {formatDoctorName(leaveDoctor.name)}</h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setLeaveDoctor(null)}>✕</button>
            </div>

            {leaveConflicts && leaveConflicts.length > 0 && (
              <div className="alert alert-error" style={{ marginBottom: '1.25rem', display: 'block' }}>
                <strong>⚠️ Notice: {leaveConflicts.length} Existing Appointment(s) in this Period!</strong>
                <p style={{ fontSize: '0.825rem', marginTop: '0.25rem' }}>
                  The leave was recorded. Please notify or reschedule the following patient appointments:
                </p>
                <ul style={{ paddingLeft: '1.25rem', marginTop: '0.5rem', fontSize: '0.8rem' }}>
                  {leaveConflicts.map((a) => (
                    <li key={a.id}>
                      Appointment #{a.id} on {new Date(a.start_time).toLocaleString()} ({a.patient_name || `Patient #${a.patient_id}`})
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <form onSubmit={handleAssignLeave}>
              <div className="grid-2" style={{ gap: '0.75rem' }}>
                <div className="form-group">
                  <label className="form-label">Start Date *</label>
                  <input type="date" required className="form-input" value={adminLeaveStart} onChange={(e) => setAdminLeaveStart(e.target.value)} />
                </div>
                <div className="form-group">
                  <label className="form-label">End Date *</label>
                  <input type="date" required className="form-input" value={adminLeaveEnd} onChange={(e) => setAdminLeaveEnd(e.target.value)} />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Reason / Clinical Coverage Note</label>
                <textarea
                  className="form-textarea"
                  rows={2}
                  placeholder="e.g. Annual leave, conference attendance, emergency coverage"
                  value={adminLeaveReason}
                  onChange={(e) => setAdminLeaveReason(e.target.value)}
                />
              </div>

              <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', marginTop: '1rem' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setLeaveDoctor(null)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Schedule Leave</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Leave Request Review Modal */}
      {reviewTarget && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card" style={{ maxWidth: '540px', width: '90%', maxHeight: '85vh', overflowY: 'auto' }}>
            <div className="card-header">
              <h3 className="card-title">Review Leave Request #{reviewTarget.id}</h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setReviewTarget(null)}>✕</button>
            </div>

            <div style={{ background: '#f8fafc', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border)', marginBottom: '1.25rem' }}>
              <div style={{ marginBottom: '0.5rem' }}>
                <strong>Doctor:</strong> {formatDoctorName(reviewTarget.doctor_name)} ({reviewTarget.doctor_specialization})
              </div>
              <div style={{ marginBottom: '0.5rem' }}>
                <strong>Requested Period:</strong> {reviewTarget.start_date} to {reviewTarget.end_date}
              </div>
              <div style={{ marginBottom: '0.5rem' }}>
                <strong>Reason:</strong> {reviewTarget.reason || 'Personal'}
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Requested on {new Date(reviewTarget.requested_at).toLocaleString()}
              </div>
            </div>

            {reviewTarget.affected_appointments_count > 0 && (
              <div className="alert alert-error" style={{ marginBottom: '1.25rem', display: 'block' }}>
                <strong>⚠️ Notice: This Leave Period Affects {reviewTarget.affected_appointments_count} Active Booking(s)!</strong>
                <p style={{ fontSize: '0.825rem', marginTop: '0.25rem' }}>
                  Existing patient appointments will NOT be silently deleted. Patients can reschedule or be notified.
                </p>
                <ul style={{ paddingLeft: '1.25rem', marginTop: '0.5rem', fontSize: '0.8rem' }}>
                  {reviewTarget.affected_appointments.map((a) => (
                    <li key={a.id}>
                      Appointment #{a.id} on {new Date(a.start_time).toLocaleString()} ({a.patient_name || `Patient #${a.patient_id}`})
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Administrator Remarks (Required if Declining)</label>
              <textarea
                className="form-textarea"
                rows={3}
                placeholder="e.g. Approved as requested / Cannot approve due to critical staffing requirements on these dates."
                value={reviewRemarks}
                onChange={(e) => setReviewRemarks(e.target.value)}
              />
            </div>

            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', marginTop: '1rem' }}>
              <button type="button" className="btn btn-secondary" onClick={() => setReviewTarget(null)}>Cancel</button>
              <button
                type="button"
                className="btn btn-danger"
                disabled={reviewingLeave}
                onClick={handleDeclineLeave}
              >
                {reviewingLeave ? 'Processing...' : 'Decline Request'}
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={reviewingLeave}
                onClick={handleApproveLeave}
              >
                {reviewingLeave ? 'Processing...' : 'Approve Leave'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
