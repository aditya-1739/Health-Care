import React, { useState, useEffect } from 'react';

/**
 * ProfileAvatar — Reusable, accessible, role-aware profile avatar component.
 * Displays uploaded user picture or a clean SVG avatar fallback with role-themed soft palette.
 * Never displays random stock human photos.
 */
export function ProfileAvatar({
  src,
  name = 'User',
  role = 'PATIENT',
  size = 'md',
  className = '',
  style = {},
}) {
  const [hasError, setHasError] = useState(false);

  // Reset error state when src changes
  useEffect(() => {
    setHasError(false);
  }, [src]);

  // Map size strings to pixel dimensions
  const sizeMap = {
    xs: 24,
    sm: 32,
    md: 40,
    lg: 64,
    xl: 96,
    xxl: 120,
  };

  const dim = typeof size === 'number' ? size : sizeMap[size] || 40;

  // Determine role theme styling for default avatar
  const normalizedRole = (role || '').toUpperCase();
  let bg = '#eff6ff';
  let color = '#2563eb';
  let border = '1px solid #bfdbfe';

  if (normalizedRole === 'DOCTOR') {
    bg = '#ecfdf5';
    color = '#059669';
    border = '1px solid #a7f3d0';
  } else if (normalizedRole === 'ADMIN') {
    bg = '#f5f3ff';
    color = '#7c3aed';
    border = '1px solid #ddd6fe';
  }

  // Handle URL normalization (relative /uploads/ vs full URL)
  let resolvedSrc = src;
  if (src && src.startsWith('/uploads/')) {
    const rawBase = import.meta.env.VITE_API_BASE_URL || '';
    resolvedSrc = rawBase ? `${rawBase.replace(/\/$/, '')}${src}` : src;
  }

  // SVG Fallback based on Role
  const renderFallbackIcon = () => {
    const iconSize = Math.round(dim * 0.55);

    if (normalizedRole === 'DOCTOR') {
      return (
        <svg
          width={iconSize}
          height={iconSize}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M4.8 2.3A.3.3 0 1 0 5 2H4a2 2 0 0 0-2 2v5a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6V4a2 2 0 0 0-2-2h-1a.2.2 0 1 0 .3.3" />
          <path d="M8 15v1a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6v-4" />
          <circle cx="20" cy="10" r="2" />
        </svg>
      );
    }

    if (normalizedRole === 'ADMIN') {
      return (
        <svg
          width={iconSize}
          height={iconSize}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        </svg>
      );
    }

    // Default: Patient / General User Silhouette
    return (
      <svg
        width={iconSize}
        height={iconSize}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="12" cy="7" r="4" />
      </svg>
    );
  };

  return (
    <div
      className={`profile-avatar-container ${className}`}
      style={{
        width: `${dim}px`,
        height: `${dim}px`,
        minWidth: `${dim}px`,
        minHeight: `${dim}px`,
        borderRadius: '50%',
        overflow: 'hidden',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: bg,
        color: color,
        border: border,
        flexShrink: 0,
        ...style,
      }}
      aria-label={`Avatar for ${name}`}
    >
      {resolvedSrc && !hasError ? (
        <img
          src={resolvedSrc}
          alt={name}
          onError={() => setHasError(true)}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            display: 'block',
          }}
        />
      ) : (
        renderFallbackIcon()
      )}
    </div>
  );
}
export default ProfileAvatar;
