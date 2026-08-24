import React, { useState, useEffect, useRef } from 'react';
import { Link, useSearchParams, useParams, useNavigate } from 'react-router-dom';
import { medicineApi } from '../api/client';
import { useAuth } from '../context/AuthContext';

export function MedicineInformation() {
  const { user, isAuthenticated } = useAuth();
  const [searchParams] = useSearchParams();
  const { rxcui: paramRxcui } = useParams();
  const navigate = useNavigate();

  const getBackLink = () => {
    if (!isAuthenticated || !user) return { to: '/', label: '← Back to Home' };
    if (user.role === 'PATIENT') return { to: '/patient/dashboard', label: '← Back to Patient Portal' };
    if (user.role === 'DOCTOR') return { to: '/doctor/dashboard', label: '← Back to Doctor Console' };
    if (user.role === 'ADMIN') return { to: '/admin/dashboard', label: '← Back to Admin Console' };
    return { to: '/', label: '← Back to Home' };
  };

  const backLink = getBackLink();

  const [query, setQuery] = useState(searchParams.get('query') || searchParams.get('q') || '');
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeSuggestionIdx, setActiveSuggestionIdx] = useState(-1);
  const [searching, setSearching] = useState(false);
  const [didYouMean, setDidYouMean] = useState(null);
  const [selectedMedicine, setSelectedMedicine] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [error, setError] = useState(null);
  const [searchAttempted, setSearchAttempted] = useState(false);
  const [showDetailedSafety, setShowDetailedSafety] = useState(false);

  const searchInputRef = useRef(null);
  const searchContainerRef = useRef(null);
  const debounceTimerRef = useRef(null);
  const activeRequestIdRef = useRef(0);

  const quickPills = [
    { label: 'Paracetamol', q: 'Paracetamol' },
    { label: 'Amoxicillin', q: 'Amoxicillin' },
    { label: 'Ibuprofen', q: 'Ibuprofen' },
    { label: 'Cetirizine', q: 'Cetirizine' },
    { label: 'Metformin', q: 'Metformin' },
  ];

  // Outside click listener to dismiss autocomplete dropdown
  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  // Auto-load if rxcui is in URL params or initial query
  useEffect(() => {
    if (paramRxcui) {
      loadMedicineDetails(paramRxcui);
    } else if (query && query.trim().length >= 2 && !selectedMedicine) {
      handleDirectSearch(query.trim());
    }
  }, [paramRxcui]);

  // Debounced lightweight autocomplete search
  useEffect(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    if (!query || query.trim().length < 2) {
      setSuggestions([]);
      setShowSuggestions(false);
      setDidYouMean(null);
      setSearching(false);
      return;
    }

    debounceTimerRef.current = setTimeout(async () => {
      const currentReqId = ++activeRequestIdRef.current;
      setSearching(true);
      try {
        const data = await medicineApi.search(query.trim());
        if (currentReqId === activeRequestIdRef.current) {
          setSuggestions(data.results || []);
          setDidYouMean(data.did_you_mean || null);
          setShowSuggestions(true);
          setActiveSuggestionIdx(-1);
        }
      } catch {
        if (currentReqId === activeRequestIdRef.current) {
          setSuggestions([]);
          setDidYouMean(null);
        }
      } finally {
        if (currentReqId === activeRequestIdRef.current) {
          setSearching(false);
        }
      }
    }, 280);

    return () => {
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    };
  }, [query]);

  const loadMedicineDetails = async (rxcui, drugName = '') => {
    setLoadingDetails(true);
    setError(null);
    setShowSuggestions(false);
    setShowDetailedSafety(false);
    try {
      const details = await medicineApi.getDetails(rxcui);
      setSelectedMedicine(details);
      setSearchAttempted(true);
      if (drugName) setQuery(drugName);
    } catch (err) {
      setError(err.message || 'Failed to retrieve medicine information.');
      setSelectedMedicine(null);
    } finally {
      setLoadingDetails(false);
    }
  };

  const handleDirectSearch = async (searchTerm) => {
    setSearching(true);
    setError(null);
    setSearchAttempted(true);
    setShowSuggestions(false);
    setShowDetailedSafety(false);
    try {
      const data = await medicineApi.search(searchTerm);
      setDidYouMean(data.did_you_mean || null);
      if (data.results && data.results.length > 0) {
        await loadMedicineDetails(data.results[0].rxcui, data.results[0].name);
      } else {
        setSelectedMedicine(null);
      }
    } catch {
      setError('Search failed. Please try another medicine name.');
      setSelectedMedicine(null);
    } finally {
      setSearching(false);
    }
  };

  const handleSelectSuggestion = (item) => {
    setQuery(item.name);
    setShowSuggestions(false);
    loadMedicineDetails(item.rxcui, item.name);
  };

  const handleKeyDown = (e) => {
    if (!showSuggestions) {
      if (e.key === 'Enter') {
        e.preventDefault();
        if (query.trim().length >= 2) handleDirectSearch(query.trim());
      }
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (suggestions.length > 0) {
        setActiveSuggestionIdx((prev) => (prev < suggestions.length - 1 ? prev + 1 : 0));
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (suggestions.length > 0) {
        setActiveSuggestionIdx((prev) => (prev > 0 ? prev - 1 : suggestions.length - 1));
      }
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (activeSuggestionIdx >= 0 && activeSuggestionIdx < suggestions.length) {
        handleSelectSuggestion(suggestions[activeSuggestionIdx]);
      } else if (query.trim().length >= 2) {
        handleDirectSearch(query.trim());
      }
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
      setActiveSuggestionIdx(-1);
    }
  };

  const handleQuickChipClick = (term) => {
    setQuery(term);
    handleDirectSearch(term);
  };

  const handleClearSearch = () => {
    setSelectedMedicine(null);
    setQuery('');
    setSearchAttempted(false);
    setError(null);
    setDidYouMean(null);
  };

  return (
    <div className="main-content" style={{ maxWidth: '1080px', margin: '0 auto', padding: '2rem 1.5rem' }}>
      {/* Top Contextual Navigation Link */}
      <div style={{ marginBottom: '1.25rem' }}>
        <Link
          to={backLink.to}
          style={{
            color: 'var(--primary)',
            fontWeight: 600,
            fontSize: '0.9rem',
            textDecoration: 'none',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.35rem',
          }}
        >
          {backLink.label}
        </Link>
      </div>

      {/* Hero / Main Search Area */}
      <div style={{ background: '#ffffff', border: '1px solid var(--border)', borderRadius: '16px', padding: '2.25rem 2rem', marginBottom: '2rem', boxShadow: 'var(--shadow-sm)' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '2.5rem', alignItems: 'center' }}>
          <div>
            <div className="hero-eyebrow" style={{ marginBottom: '0.75rem' }}>
              Medicine Information
            </div>

            <h1 style={{ fontSize: '2.1rem', fontWeight: 800, marginBottom: '0.5rem', color: 'var(--text-main)', lineHeight: 1.25 }}>
              Find clear information about a medicine.
            </h1>

            <p style={{ color: 'var(--text-muted)', fontSize: '1rem', marginBottom: '1.5rem', lineHeight: 1.5 }}>
              Learn what a medicine is generally used for, common forms, and important safety information.
            </p>

            {/* Search Input Section */}
            <div ref={searchContainerRef} style={{ position: 'relative' }}>
              <label className="form-label" style={{ fontSize: '0.85rem', fontWeight: 700, marginBottom: '0.4rem', display: 'block' }} htmlFor="medicine-search-input">
                Search medicine
              </label>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <div style={{ position: 'relative', flex: 1 }}>
                  <input
                    id="medicine-search-input"
                    ref={searchInputRef}
                    type="text"
                    className="form-input"
                    style={{ fontSize: '1rem', padding: '0.8rem 1.15rem', borderRadius: '8px', border: '1px solid var(--border)', width: '100%' }}
                    placeholder="Search for a medicine (e.g. Paracetamol, Amoxicillin)..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onFocus={() => {
                      if (query.trim().length >= 2) setShowSuggestions(true);
                    }}
                    role="combobox"
                    aria-expanded={showSuggestions}
                    aria-controls="medicine-autocomplete-list"
                    aria-activedescendant={activeSuggestionIdx >= 0 ? `med-option-${activeSuggestionIdx}` : undefined}
                    aria-autocomplete="list"
                    autoComplete="off"
                  />
                  {searching && (
                    <div style={{ position: 'absolute', right: '14px', top: '50%', transform: 'translateY(-50%)', fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 500 }}>
                      Searching...
                    </div>
                  )}
                </div>
                <button
                  className="btn btn-primary"
                  style={{ padding: '0.8rem 1.5rem', fontSize: '0.95rem', fontWeight: 600 }}
                  onClick={() => {
                    if (query.trim().length >= 2) handleDirectSearch(query.trim());
                  }}
                  disabled={searching || query.trim().length < 2}
                >
                  Search
                </button>
              </div>

              {/* Autocomplete Dropdown */}
              {showSuggestions && query.trim().length >= 2 && (
                <div
                  id="medicine-autocomplete-list"
                  role="listbox"
                  style={{
                    position: 'absolute',
                    top: '100%',
                    left: 0,
                    right: 0,
                    background: '#ffffff',
                    border: '1px solid var(--border)',
                    borderRadius: '8px',
                    boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.15)',
                    zIndex: 100,
                    marginTop: '4px',
                    maxHeight: '300px',
                    overflowY: 'auto',
                  }}
                >
                  {suggestions.length > 0 ? (
                    suggestions.map((item, idx) => (
                      <div
                        key={item.rxcui}
                        id={`med-option-${idx}`}
                        role="option"
                        aria-selected={idx === activeSuggestionIdx}
                        style={{
                          padding: '0.75rem 1rem',
                          cursor: 'pointer',
                          background: idx === activeSuggestionIdx ? 'var(--primary-light)' : 'transparent',
                          borderBottom: '1px solid #f1f5f9',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                        onMouseEnter={() => setActiveSuggestionIdx(idx)}
                        onMouseDown={(e) => {
                          e.preventDefault();
                          handleSelectSuggestion(item);
                        }}
                      >
                        <div>
                          <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>{item.name}</div>
                          {item.synonym && (
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Also known as: {item.synonym}</div>
                          )}
                        </div>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          Select →
                        </span>
                      </div>
                    ))
                  ) : !searching ? (
                    <div style={{ padding: '1rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                      <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>No matching medicine found.</div>
                      <div style={{ fontSize: '0.825rem', marginTop: '2px' }}>Try a generic name or check the spelling.</div>
                      {didYouMean && (
                        <div style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}>
                          Did you mean{' '}
                          <button
                            type="button"
                            style={{ color: 'var(--primary)', fontWeight: 700, textDecoration: 'underline', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                            onMouseDown={(e) => {
                              e.preventDefault();
                              handleQuickChipClick(didYouMean);
                            }}
                          >
                            {didYouMean}
                          </button>
                          ?
                        </div>
                      )}
                    </div>
                  ) : null}
                </div>
              )}
            </div>

            {/* Popular Search Chips */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', marginTop: '1rem' }}>
              <span style={{ fontSize: '0.825rem', color: 'var(--text-muted)', fontWeight: 600 }}>Popular:</span>
              {quickPills.map((pill) => (
                <button
                  key={pill.label}
                  type="button"
                  className="btn btn-secondary btn-sm"
                  style={{ fontSize: '0.8rem', padding: '0.25rem 0.65rem' }}
                  onClick={() => handleQuickChipClick(pill.q)}
                >
                  {pill.label}
                </button>
              ))}
            </div>
          </div>

          {/* Right Visual Card */}
          <div style={{ borderRadius: '12px', overflow: 'hidden', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}>
            <img
              src="/images/consultation.jpg"
              alt="Healthcare professional providing patient guidance"
              style={{ width: '100%', height: '100%', maxHeight: '280px', objectFit: 'cover', display: 'block' }}
              loading="eager"
            />
            <div style={{ background: '#f8fafc', padding: '0.75rem 1rem', fontSize: '0.8rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ color: 'var(--primary)', fontWeight: 800 }}>✓</span>
              <span>Authoritative medication knowledge powered by RxNorm & DailyMed</span>
            </div>
          </div>
        </div>
      </div>

      {error && <div className="alert alert-error" role="alert" style={{ marginBottom: '1.5rem' }}>{error}</div>}

      {/* Loading State */}
      {loadingDetails && (
        <div className="card" style={{ textAlign: 'center', padding: '3rem 1rem', border: '1px solid var(--border)', borderRadius: '12px' }}>
          <div style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--primary)' }}>
            Retrieving medicine information...
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Loading verified details from official sources
          </p>
        </div>
      )}

      {/* No Results State */}
      {!loadingDetails && searchAttempted && !selectedMedicine && !error && (
        <div className="card" style={{ textAlign: 'center', padding: '3rem 1.5rem', border: '1px solid var(--border)', borderRadius: '12px', marginBottom: '2rem' }}>
          <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.5rem' }}>No matching medicine found</h3>
          <p style={{ color: 'var(--text-muted)', maxWidth: '460px', margin: '0.5rem auto 1.5rem', lineHeight: 1.5 }}>
            We could not find a match for "{query}". Try searching by the generic active ingredient name (for example, <em>Paracetamol</em>) or check the spelling.
          </p>
          {didYouMean && (
            <div style={{ marginBottom: '1.5rem', fontSize: '0.95rem' }}>
              Did you mean{' '}
              <button
                type="button"
                className="btn btn-primary btn-sm"
                style={{ marginLeft: '6px' }}
                onClick={() => handleQuickChipClick(didYouMean)}
              >
                {didYouMean}
              </button>
            </div>
          )}
          <div style={{ display: 'flex', justifyContent: 'center', gap: '0.5rem' }}>
            <button className="btn btn-secondary" onClick={() => handleQuickChipClick('Paracetamol')}>
              Search Paracetamol
            </button>
            <button className="btn btn-secondary" onClick={() => handleQuickChipClick('Amoxicillin')}>
              Search Amoxicillin
            </button>
          </div>
        </div>
      )}

      {/* Pre-Search State (When no medicine is searched yet) */}
      {!loadingDetails && !selectedMedicine && !searchAttempted && (
        <div>
          {/* "What you'll find" Information Strip */}
          <div style={{ marginBottom: '2rem' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--primary)', marginBottom: '0.75rem' }}>
              What you'll find
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.25rem' }}>
              <div style={{ background: '#ffffff', border: '1px solid var(--border)', borderRadius: '10px', padding: '1.25rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
                  <span style={{ color: 'var(--primary)', fontWeight: 800 }}>✓</span>
                  <h3 style={{ fontSize: '1rem', fontWeight: 700, margin: 0, color: 'var(--text-main)' }}>What it's used for</h3>
                </div>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', margin: 0, lineHeight: 1.5 }}>
                  Simple information about common uses and indications.
                </p>
              </div>

              <div style={{ background: '#ffffff', border: '1px solid var(--border)', borderRadius: '10px', padding: '1.25rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
                  <span style={{ color: 'var(--primary)', fontWeight: 800 }}>✓</span>
                  <h3 style={{ fontSize: '1rem', fontWeight: 700, margin: 0, color: 'var(--text-main)' }}>Common forms</h3>
                </div>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', margin: 0, lineHeight: 1.5 }}>
                  Available formats including tablet, capsule, liquid, and more.
                </p>
              </div>

              <div style={{ background: '#ffffff', border: '1px solid var(--border)', borderRadius: '10px', padding: '1.25rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
                  <span style={{ color: 'var(--primary)', fontWeight: 800 }}>!</span>
                  <h3 style={{ fontSize: '1rem', fontWeight: 700, margin: 0, color: 'var(--text-main)' }}>Safety information</h3>
                </div>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', margin: 0, lineHeight: 1.5 }}>
                  Important things to know and safety guidance before use.
                </p>
              </div>
            </div>
          </div>

          {/* Guidance Empty State */}
          <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '1.75rem', textAlign: 'center', marginBottom: '2rem' }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.35rem' }}>
              Search a medicine to get started
            </h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', margin: '0 auto', maxWidth: '420px', lineHeight: 1.5 }}>
              You can search by <strong>medicine name</strong>, <strong>generic active substance</strong>, or <strong>common brand name</strong>.
            </p>
          </div>
        </div>
      )}

      {/* Patient-First Medicine Detail View (When a medicine is selected) */}
      {!loadingDetails && selectedMedicine && (
        <div className="card" style={{ padding: '2rem', border: '1px solid var(--border)', borderRadius: '12px', marginBottom: '2rem' }}>
          {/* Header Block with Clear Action */}
          <div style={{ borderBottom: '1px solid var(--border)', paddingBottom: '1.25rem', marginBottom: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.75rem' }}>
              <div>
                <h2 style={{ fontSize: '1.75rem', fontWeight: 800, margin: 0, color: 'var(--text-main)' }}>
                  {selectedMedicine.name}
                </h2>
                {selectedMedicine.generic_name && selectedMedicine.generic_name.toLowerCase() !== selectedMedicine.name.toLowerCase() && (
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', marginTop: '0.25rem', marginBottom: 0 }}>
                    Generic name: <strong style={{ color: 'var(--text-main)' }}>{selectedMedicine.generic_name}</strong>
                  </p>
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span className="user-badge" style={{ background: '#ecfdf5', color: '#047857', border: '1px solid #a7f3d0', fontWeight: 600, padding: '4px 10px', fontSize: '0.8rem' }}>
                  ✓ Information verified from official source
                </span>
                <button
                  type="button"
                  onClick={handleClearSearch}
                  className="btn btn-secondary btn-sm"
                  style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }}
                >
                  New Search ✕
                </button>
              </div>
            </div>
          </div>

          {/* 1. Primary Section: "What is it used for?" */}
          <div style={{ marginBottom: '1.75rem' }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '0.6rem', color: 'var(--text-main)' }}>
              What is it used for?
            </h3>

            {selectedMedicine.uses?.length > 0 ? (
              <div>
                <p style={{ fontSize: '0.95rem', color: 'var(--text-main)', margin: '0 0 0.5rem 0', lineHeight: 1.5 }}>
                  {selectedMedicine.name} is commonly used for:
                </p>
                <ul style={{ paddingLeft: '1.25rem', margin: 0, color: 'var(--text-main)', fontSize: '0.95rem', lineHeight: 1.6 }}>
                  {selectedMedicine.uses.map((use, idx) => (
                    <li key={idx} style={{ marginBottom: '0.35rem' }}>
                      {use.replace(/^Used for\s+/i, '').replace(/^Used to\s+/i, '')}
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', margin: 0 }}>
                Used according to standard clinical indications.
              </p>
            )}

            {/* AI Simplified Explanation Box */}
            {selectedMedicine.ai_summary && (
              <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '1rem', marginTop: '1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem', flexWrap: 'wrap', gap: '0.25rem' }}>
                  <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#334155' }}>
                    Simple explanation
                  </span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    AI-generated from official medicine information
                  </span>
                </div>
                <p style={{ fontSize: '0.9rem', color: '#1e293b', margin: 0, lineHeight: 1.5 }}>
                  {selectedMedicine.ai_summary}
                </p>
              </div>
            )}
          </div>

          {/* 2. Medicine Snapshot (Clean Compact 2-Column Grid) */}
          <div style={{ background: '#f8fafc', borderRadius: '8px', padding: '1.25rem', marginBottom: '1.75rem', border: '1px solid #e2e8f0' }}>
            <div className="grid-2" style={{ gap: '1rem' }}>
              <div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>Active ingredient</div>
                <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-main)', marginTop: '2px' }}>
                  {selectedMedicine.active_ingredients?.join(', ') || selectedMedicine.generic_name || selectedMedicine.name}
                </div>
              </div>

              {selectedMedicine.dosage_forms?.length > 0 && (
                <div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600, marginBottom: '4px' }}>Available forms</div>
                  <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                    {selectedMedicine.dosage_forms.map((form, idx) => (
                      <span key={idx} style={{ background: '#ffffff', color: '#334155', padding: '0.2rem 0.55rem', borderRadius: '4px', fontSize: '0.8rem', border: '1px solid #cbd5e1' }}>
                        {form}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {selectedMedicine.brand_names?.length > 0 && (
              <div style={{ marginTop: '1rem', paddingTop: '0.75rem', borderTop: '1px solid #e2e8f0' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>Also known as</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>* Brand names may vary by country</div>
                </div>
                <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                  {selectedMedicine.brand_names.map((brand, idx) => (
                    <span key={idx} style={{ background: '#ffffff', color: '#475569', padding: '0.2rem 0.55rem', borderRadius: '4px', fontSize: '0.8rem', border: '1px solid #cbd5e1' }}>
                      {brand}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* 3. Important Safety Information */}
          <div style={{ marginBottom: '1.75rem' }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 700, marginBottom: '0.5rem', color: '#991b1b' }}>
              Important safety information
            </h3>
            {selectedMedicine.warnings?.length > 0 ? (
              <div>
                <ul style={{ paddingLeft: '1.25rem', margin: 0, color: '#7f1d1d', fontSize: '0.9rem', lineHeight: 1.5 }}>
                  {selectedMedicine.warnings.slice(0, showDetailedSafety ? undefined : 2).map((w, idx) => (
                    <li key={idx} style={{ marginBottom: '0.35rem' }}>
                      {w}
                    </li>
                  ))}
                </ul>
                {selectedMedicine.warnings.length > 2 && (
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    style={{ marginTop: '0.5rem', fontSize: '0.8rem' }}
                    onClick={() => setShowDetailedSafety(!showDetailedSafety)}
                  >
                    {showDetailedSafety ? 'Hide detailed safety information' : 'View detailed safety information'}
                  </button>
                )}
              </div>
            ) : (
              <ul style={{ paddingLeft: '1.25rem', margin: 0, color: '#7f1d1d', fontSize: '0.9rem', lineHeight: 1.5 }}>
                <li>Follow the directions on the label or your doctor's prescription.</li>
                <li>Keep out of reach of children. Seek immediate medical assistance in case of accidental overdose.</li>
              </ul>
            )}
          </div>

          {/* 4. When Should I Ask a Doctor or Pharmacist? */}
          <div style={{ background: '#f8fafc', padding: '1.25rem', borderRadius: '8px', border: '1px solid #e2e8f0', marginBottom: '1.75rem' }}>
            <div style={{ fontWeight: 700, fontSize: '0.95rem', marginBottom: '0.5rem', color: 'var(--text-main)' }}>
              When should I ask a doctor or pharmacist?
            </div>
            <ul style={{ paddingLeft: '1.25rem', margin: 0, fontSize: '0.875rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
              <li>You are unsure whether this medicine is right for your symptoms.</li>
              <li>You take other prescription medications or have an existing health condition.</li>
              <li>You are pregnant, planning to become pregnant, or breastfeeding.</li>
              <li>You have questions about proper dosage or how to store the medicine safely.</li>
            </ul>
          </div>

          {/* 5. Information Source */}
          <div style={{ fontSize: '0.825rem', color: 'var(--text-muted)', marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
            <div>
              Information source: <strong>{selectedMedicine.source?.name || 'DailyMed / U.S. National Library of Medicine'}</strong>
              {selectedMedicine.source?.url && (
                <a href={selectedMedicine.source.url} target="_blank" rel="noreferrer" style={{ marginLeft: '6px', color: 'var(--primary)', textDecoration: 'underline' }}>
                  [Official Source Link ↗]
                </a>
              )}
            </div>
          </div>

          {/* 6. Technical Details (Collapsed by default) */}
          <div style={{ borderTop: '1px solid var(--border)', paddingTop: '1rem', marginBottom: '1.5rem' }}>
            <details style={{ cursor: 'pointer', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              <summary style={{ fontWeight: 600, color: 'var(--text-main)', userSelect: 'none' }}>
                Technical details ⌄
              </summary>
              <div style={{ marginTop: '0.75rem', paddingLeft: '0.5rem', lineHeight: 1.6, fontSize: '0.8rem' }}>
                <div><strong>RxCUI:</strong> {selectedMedicine.rxcui}</div>
                <div><strong>Terminology Provider:</strong> NIH RxNorm & DailyMed Structured Product Labeling (SPL)</div>
                <div><strong>Standardization:</strong> Unified Medical Language System (UMLS)</div>
              </div>
            </details>
          </div>

          {/* 7. Important Disclaimer */}
          <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '0.9rem 1.15rem', marginBottom: '1.75rem', color: '#64748b' }}>
            <div style={{ fontWeight: 700, fontSize: '0.825rem', marginBottom: '0.2rem', color: '#475569' }}>
              Important
            </div>
            <p style={{ fontSize: '0.8rem', margin: 0, lineHeight: 1.5 }}>
              This information is for general educational purposes only. It is not a substitute for advice, diagnosis, or treatment from a qualified healthcare professional.
            </p>
          </div>

          {/* 8. Find a Doctor CTA */}
          <div style={{ background: '#ffffff', border: '1px solid var(--border)', borderRadius: '8px', textAlign: 'center', padding: '1.75rem 1.25rem' }}>
            <h4 style={{ fontSize: '1.15rem', fontWeight: 800, marginBottom: '0.35rem', color: 'var(--text-main)' }}>
              Have questions about your medicine?
            </h4>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', maxWidth: '480px', margin: '0 auto 1.25rem', lineHeight: 1.5 }}>
              Talk to a healthcare professional to discuss your medical history, potential interactions, and receive tailored care.
            </p>
            <Link
              to={isAuthenticated && user?.role === 'PATIENT' ? '/patient/dashboard' : '/roles'}
              className="btn btn-primary"
              style={{ padding: '0.65rem 1.5rem', fontWeight: 600 }}
            >
              Find a Doctor
            </Link>
          </div>
        </div>
      )}

      {/* Trust / Educational Note at Bottom of Page */}
      <div style={{ borderTop: '1px solid var(--border)', paddingTop: '1.25rem', marginTop: '1.5rem', textAlign: 'center', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
        <p style={{ margin: '0 0 0.25rem 0' }}>
          Information sourced from NIH RxNorm and official DailyMed Structured Product Labeling (SPL).
        </p>
        <p style={{ margin: 0, color: '#94a3b8' }}>
          For general educational information only. This is not a substitute for professional medical advice.
        </p>
      </div>
    </div>
  );
}
