const API_BASE_URL = '/api';

/**
 * Formats API errors into clean, user-friendly sentences.
 */
export function formatApiError(data, status) {
  if (!data && !status) return 'An unexpected error occurred. Please try again.';

  if (data?.detail) {
    if (typeof data.detail === 'string') {
      return data.detail;
    }
    if (Array.isArray(data.detail)) {
      // Pydantic validation errors: convert [{loc: [...], msg: "..."}] into readable text
      const messages = data.detail.map((err) => {
        const field = err.loc && err.loc.length > 1 ? err.loc[err.loc.length - 1] : 'field';
        const msg = err.msg || 'Invalid value';
        if (msg.toLowerCase().includes('valid email')) return 'Please enter a valid email address.';
        if (field === 'password') return 'Password must be at least 8 characters long.';
        if (field === 'phone') return 'Please enter a valid contact phone number.';
        return `${field.replace(/_/g, ' ')}: ${msg}`;
      });
      return messages.join('. ');
    }
  }

  if (data?.message && typeof data.message === 'string') {
    return data.message;
  }

  switch (status) {
    case 400:
      return 'The submitted request is invalid. Please check your input.';
    case 401:
      return 'Authentication failed. Please check your credentials.';
    case 403:
      return 'You do not have permission to perform this action.';
    case 404:
      return 'The requested record or resource was not found.';
    case 409:
      return 'A slot conflict occurred. Another appointment may have just been booked.';
    case 422:
      return 'Validation error. Please verify all required form fields.';
    case 429:
      return 'Too many requests. Please wait a moment and try again.';
    case 500:
    case 502:
    case 503:
      return 'A server error occurred. Please try again shortly.';
    default:
      return 'An unexpected error occurred while communicating with the server.';
  }
}

/**
 * Generate a random UUID string for client-side idempotency keys.
 */
export function generateIdempotencyKey() {
  return 'idemp_' + Math.random().toString(36).substring(2, 15) + '_' + Date.now().toString(36);
}

/**
 * Perform an authenticated HTTP fetch request with error handling and JWT injection.
 */
export async function apiRequest(endpoint, options = {}) {
  const token = localStorage.getItem('access_token');
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;

  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (netErr) {
    const error = new Error('Network error: Unable to reach the healthcare server. Please check your connection.');
    error.status = 0;
    throw error;
  }

  // If unauthorized, clean up token
  if (response.status === 401 && !endpoint.includes('/auth/login')) {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_profile');
  }

  let data;
  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    const friendlyMessage = formatApiError(data, response.status);
    const error = new Error(friendlyMessage);
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
}

export const authApi = {
  login: (credentials) =>
    apiRequest('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    }),
  register: (patientData) =>
    apiRequest('/auth/register', {
      method: 'POST',
      body: JSON.stringify(patientData),
    }),
  getMe: () => apiRequest('/auth/me'),
  logout: () =>
    apiRequest('/auth/logout', {
      method: 'POST',
    }),
};

export const healthApi = {
  check: () => apiRequest('/health'),
};

export const patientApi = {
  getMe: () => apiRequest('/patients/me'),
  updateMe: (data) =>
    apiRequest('/patients/me', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  getById: (id) => apiRequest(`/patients/${id}`),
};

export const doctorApi = {
  list: (specialization) => {
    const query = specialization ? `?specialization=${encodeURIComponent(specialization)}` : '';
    return apiRequest(`/doctors${query}`);
  },
  getById: (id) => apiRequest(`/doctors/${id}`),
  getAvailability: (doctorId, dateStr) =>
    apiRequest(`/doctors/${doctorId}/availability?date=${dateStr}`),
  getMyLeaves: () => apiRequest('/doctors/me/leaves'),
  addMyLeave: (data) =>
    apiRequest('/doctors/me/leaves', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  deleteMyLeave: (leaveId) =>
    apiRequest(`/doctors/me/leaves/${leaveId}`, {
      method: 'DELETE',
    }),
  addMyWorkingHours: (data) =>
    apiRequest('/doctors/me/working-hours', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

export const appointmentApi = {
  hold: (data, idempotencyKey) => {
    const headers = {};
    if (idempotencyKey) {
      headers['X-Idempotency-Key'] = idempotencyKey;
    }
    return apiRequest('/appointments/hold', {
      method: 'POST',
      headers,
      body: JSON.stringify({ ...data, idempotency_key: idempotencyKey }),
    });
  },
  confirm: (appointmentId, idempotencyKey) => {
    const headers = {};
    if (idempotencyKey) {
      headers['X-Idempotency-Key'] = idempotencyKey;
    }
    return apiRequest(`/appointments/${appointmentId}/confirm`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ idempotency_key: idempotencyKey }),
    });
  },
  list: (params = {}) => {
    const queryParts = [];
    if (params.status) queryParts.push(`status=${encodeURIComponent(params.status)}`);
    if (params.timeframe) queryParts.push(`timeframe=${encodeURIComponent(params.timeframe)}`);
    const query = queryParts.length ? `?${queryParts.join('&')}` : '';
    return apiRequest(`/appointments${query}`);
  },
  getById: (id) => apiRequest(`/appointments/${id}`),
  cancel: (id, reason) =>
    apiRequest(`/appointments/${id}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  decline: (id, remarks) =>
    apiRequest(`/appointments/${id}/decline`, {
      method: 'POST',
      body: JSON.stringify({ remarks }),
    }),
  reschedule: (id, newStartTime, idempotencyKey) => {
    const headers = {};
    if (idempotencyKey) {
      headers['X-Idempotency-Key'] = idempotencyKey;
    }
    return apiRequest(`/appointments/${id}/reschedule`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ new_start_time: newStartTime, idempotency_key: idempotencyKey }),
    });
  },
  complete: (id) =>
    apiRequest(`/appointments/${id}/complete`, {
      method: 'POST',
    }),
  noShow: (id) =>
    apiRequest(`/appointments/${id}/no-show`, {
      method: 'POST',
    }),
  getAlternatives: (id) => apiRequest(`/appointments/${id}/alternative-slots`),
};

export const clinicalApi = {
  submitSymptoms: (appointmentId, data) =>
    apiRequest(`/appointments/${appointmentId}/symptoms`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getSymptoms: (appointmentId) => apiRequest(`/appointments/${appointmentId}/symptoms`),
  getAISummaries: (appointmentId) => apiRequest(`/appointments/${appointmentId}/ai-summary`),
  saveClinicalNotes: (appointmentId, data) =>
    apiRequest(`/appointments/${appointmentId}/clinical-notes`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getClinicalNotes: (appointmentId) => apiRequest(`/appointments/${appointmentId}/clinical-notes`),
  createPrescription: (appointmentId, data) =>
    apiRequest(`/appointments/${appointmentId}/prescription`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getPrescription: (appointmentId) => apiRequest(`/appointments/${appointmentId}/prescription`),
  updateMedicationStatus: (prescriptionId, medicationId, status) =>
    apiRequest(`/prescriptions/${prescriptionId}/medications/${medicationId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),
  getMyMedicationReminders: () => apiRequest('/patients/me/medication-reminders'),
};

export const calendarApi = {
  getAuthUrl: () => apiRequest('/calendar/auth-url'),
  callback: (code) =>
    apiRequest('/calendar/callback', {
      method: 'POST',
      body: JSON.stringify({ code }),
    }),
  getStatus: () => apiRequest('/calendar/status'),
  disconnect: () =>
    apiRequest('/calendar/disconnect', {
      method: 'DELETE',
    }),
};

export const adminApi = {
  getDashboard: () => apiRequest('/admin/dashboard'),
  getPatients: (search) => {
    const query = search ? `?search=${encodeURIComponent(search)}` : '';
    return apiRequest(`/admin/patients${query}`);
  },
  createUser: (userData) =>
    apiRequest('/admin/users', {
      method: 'POST',
      body: JSON.stringify(userData),
    }),
  updateDoctor: (id, data) =>
    apiRequest(`/admin/doctors/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  toggleDoctorStatus: (id, active) =>
    apiRequest(`/admin/doctors/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ active }),
    }),
  addDoctorWorkingHours: (id, data) =>
    apiRequest(`/admin/doctors/${id}/working-hours`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  addDoctorLeave: (id, data) =>
    apiRequest(`/admin/doctors/${id}/leaves`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  deleteDoctorLeave: (doctorId, leaveId) =>
    apiRequest(`/admin/doctors/${doctorId}/leaves/${leaveId}`, {
      method: 'DELETE',
    }),
  getAuditLogs: (limit = 50) => apiRequest(`/admin/audit-logs?limit=${limit}`),
  getLeaveRequests: (status) => {
    const query = status ? `?status=${encodeURIComponent(status)}` : '';
    return apiRequest(`/admin/leave-requests${query}`);
  },
  approveLeaveRequest: (id, remarks) =>
    apiRequest(`/admin/leave-requests/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ remarks }),
    }),
  declineLeaveRequest: (id, remarks) =>
    apiRequest(`/admin/leave-requests/${id}/decline`, {
      method: 'POST',
      body: JSON.stringify({ remarks }),
    }),
  getReliabilityMetrics: () => apiRequest('/admin/reliability/metrics'),
  getUsers: (search, role) => {
    const params = new URLSearchParams();
    if (search) params.append('search', search);
    if (role && role !== 'ALL') params.append('role', role);
    const qs = params.toString();
    return apiRequest(`/admin/users${qs ? '?' + qs : ''}`);
  },
  getUserProfile: (userId) => apiRequest(`/admin/users/${userId}/profile`),
  retryAI: (summaryId) =>
    apiRequest(`/admin/reliability/retry-ai/${summaryId}`, {
      method: 'POST',
    }),
  retryNotification: (notificationId) =>
    apiRequest(`/admin/reliability/retry-notification/${notificationId}`, {
      method: 'POST',
    }),
  retryCalendar: (eventId) =>
    apiRequest(`/admin/reliability/retry-calendar/${eventId}`, {
      method: 'POST',
    }),
};

export const profileApi = {
  getMe: () => apiRequest('/profile/me'),
  updateMe: (data) =>
    apiRequest('/profile/me', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  getMedical: () => apiRequest('/profile/me/medical'),
  updateMedical: (data) =>
    apiRequest('/profile/me/medical', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  getAppointments: () => apiRequest('/profile/me/appointments'),
  changePassword: (data) =>
    apiRequest('/profile/me/change-password', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

export const medicineApi = {
  search: (query) => apiRequest(`/medicines/search?q=${encodeURIComponent(query)}`),
  getDetails: (rxcui) => apiRequest(`/medicines/${encodeURIComponent(rxcui)}`),
};

