import { format, formatDistanceToNow } from 'date-fns';

function normalizeDateString(dateString: string): string {
  const trimmed = dateString.trim();
  const hasTimezone = /[zZ]|[+-]\d{2}:\d{2}$/.test(trimmed);
  return hasTimezone ? trimmed : `${trimmed}Z`;
}

export function formatDate(dateString: string): string {
  try {
    return format(new Date(normalizeDateString(dateString)), 'MMM d, yyyy');
  } catch {
    return dateString;
  }
}

export function formatRelativeTime(dateString: string): string {
  try {
    return formatDistanceToNow(new Date(normalizeDateString(dateString)), { addSuffix: true });
  } catch {
    return dateString;
  }
}
