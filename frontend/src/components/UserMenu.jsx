import React, { useState, useRef, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { formatDoctorName } from '../utils/format';
import { ProfileAvatar } from './ProfileAvatar';

export function UserMenu({ onNavigate }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const menuRef = useRef(null);
  const triggerRef = useRef(null);

  const getRoleBadgeClass = (role) => {
    switch (role) {
      case 'PATIENT':
        return 'badge-patient';
      case 'DOCTOR':
        return 'badge-doctor';
      case 'ADMIN':
        return 'badge-admin';
      default:
        return '';
    }
  };

  const getMenuItems = () => {
    if (!user) return [];
    if (user.role === 'PATIENT') {
      return [
        { label: 'Profile', path: '/profile?tab=basic' },
        { label: 'Medical Profile', path: '/profile?tab=medical' },
        { label: 'Appointment History', path: '/profile?tab=appointments' },
        { label: 'Change Password', path: '/profile?tab=password' },
      ];
    }
    if (user.role === 'DOCTOR') {
      return [
        { label: 'Profile', path: '/profile?tab=basic' },
        { label: 'Professional Profile', path: '/profile?tab=professional' },
        { label: 'Appointment History', path: '/profile?tab=appointments' },
        { label: 'Change Password', path: '/profile?tab=password' },
      ];
    }
    if (user.role === 'ADMIN') {
      return [
        { label: 'Profile', path: '/profile?tab=basic' },
        { label: 'User Profiles', path: '/admin/dashboard?tab=users' },
        { label: 'Change Password', path: '/profile?tab=password' },
      ];
    }
    return [
      { label: 'Profile', path: '/profile?tab=basic' },
      { label: 'Change Password', path: '/profile?tab=password' },
    ];
  };

  const menuItems = getMenuItems();

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setIsOpen(false);
        setActiveIdx(-1);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleKeyDown = (e) => {
    if (!isOpen) {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
        e.preventDefault();
        setIsOpen(true);
        setActiveIdx(0);
      }
      return;
    }

    if (e.key === 'Escape') {
      e.preventDefault();
      setIsOpen(false);
      setActiveIdx(-1);
      triggerRef.current?.focus();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx((prev) => (prev < menuItems.length ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx((prev) => (prev > 0 ? prev - 1 : menuItems.length));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (activeIdx >= 0 && activeIdx < menuItems.length) {
        handleItemClick(menuItems[activeIdx].path);
      } else if (activeIdx === menuItems.length) {
        handleLogout();
      }
    }
  };

  const handleItemClick = (path) => {
    setIsOpen(false);
    setActiveIdx(-1);
    if (onNavigate) onNavigate();
    navigate(path);
  };

  const handleLogout = async () => {
    setIsOpen(false);
    setActiveIdx(-1);
    if (onNavigate) onNavigate();
    await logout();
    navigate('/');
  };

  if (!user) return null;

  const displayName = user.role === 'DOCTOR' ? formatDoctorName(user.name) : user.name;

  return (
    <div className="user-menu-container" ref={menuRef} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        ref={triggerRef}
        type="button"
        className="user-menu-trigger"
        onClick={() => setIsOpen(!isOpen)}
        onKeyDown={handleKeyDown}
        aria-haspopup="true"
        aria-expanded={isOpen}
        aria-label="User account and profile menu"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          background: 'none',
          border: '1px solid var(--border)',
          borderRadius: '8px',
          padding: '0.4rem 0.75rem',
          cursor: 'pointer',
          color: 'var(--text-main)',
          fontSize: '0.9rem',
          fontWeight: 600,
        }}
      >
        <ProfileAvatar
          src={user.profile_image_url}
          name={user.name}
          role={user.role}
          size={28}
        />
        <span className={`user-badge ${getRoleBadgeClass(user.role)}`} style={{ fontSize: '0.75rem', padding: '2px 6px' }}>
          {user.role}
        </span>
        <span>{displayName}</span>
        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginLeft: '2px' }}>
          {isOpen ? '▲' : '▼'}
        </span>
      </button>

      {isOpen && (
        <div
          role="menu"
          className="user-dropdown-menu"
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            right: 0,
            background: '#ffffff',
            border: '1px solid var(--border)',
            borderRadius: '8px',
            boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.15)',
            minWidth: '200px',
            zIndex: 1000,
            overflow: 'hidden',
            padding: '0.35rem 0',
          }}
        >
          {menuItems.map((item, idx) => (
            <button
              key={item.label}
              role="menuitem"
              type="button"
              tabIndex={0}
              className="user-dropdown-item"
              style={{
                width: '100%',
                textAlign: 'left',
                padding: '0.65rem 1rem',
                fontSize: '0.9rem',
                fontWeight: 500,
                color: 'var(--text-main)',
                background: idx === activeIdx ? 'var(--primary-light)' : 'transparent',
                border: 'none',
                cursor: 'pointer',
                display: 'block',
              }}
              onMouseEnter={() => setActiveIdx(idx)}
              onClick={() => handleItemClick(item.path)}
            >
              {item.label}
            </button>
          ))}

          <div style={{ borderTop: '1px solid #f1f5f9', margin: '0.25rem 0' }} />

          <button
            role="menuitem"
            type="button"
            tabIndex={0}
            className="user-dropdown-item"
            style={{
              width: '100%',
              textAlign: 'left',
              padding: '0.65rem 1rem',
              fontSize: '0.9rem',
              fontWeight: 600,
              color: '#dc2626',
              background: activeIdx === menuItems.length ? '#fee2e2' : 'transparent',
              border: 'none',
              cursor: 'pointer',
              display: 'block',
            }}
            onMouseEnter={() => setActiveIdx(menuItems.length)}
            onClick={handleLogout}
          >
            Logout
          </button>
        </div>
      )}
    </div>
  );
}
