/**
 * Formats a doctor's name cleanly, ensuring "Dr." prefix is present exactly once.
 * Examples:
 *   "Alice Smith" -> "Dr. Alice Smith"
 *   "Dr. Alice Smith" -> "Dr. Alice Smith"
 *   "Dr Robert Jones" -> "Dr. Robert Jones"
 *   "DR. ALICE SMITH" -> "Dr. ALICE SMITH"
 */
export function formatDoctorName(name) {
  if (!name) return 'Dr. Specialist';
  const trimmed = name.trim();
  // Remove existing leading Dr / Dr. / DR / DR. (case-insensitive)
  const cleaned = trimmed.replace(/^dr\.?\s+/i, '');
  return `Dr. ${cleaned}`;
}
