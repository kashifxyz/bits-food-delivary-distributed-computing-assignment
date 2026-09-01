export function formatTimestamp(isoString: string): string {
  try {
    const d = new Date(isoString);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 3 });
  } catch {
    return isoString;
  }
}

export function formatVectorClock(clock: number[]): string {
  if (!clock || !Array.isArray(clock)) return '[0, 0, 0, 0]';
  return `[${clock.join(', ')}]`;
}

export function getProcessBadgeColor(processId: number): { bg: string; text: string; border: string } {
  switch (processId) {
    case 1:
      return { bg: 'rgba(59, 130, 246, 0.15)', text: '#60a5fa', border: '#3b82f6' };
    case 2:
      return { bg: 'rgba(245, 158, 11, 0.15)', text: '#fbbf24', border: '#f59e0b' };
    case 3:
      return { bg: 'rgba(16, 185, 129, 0.15)', text: '#34d399', border: '#10b981' };
    case 4:
      return { bg: 'rgba(168, 85, 247, 0.15)', text: '#c084fc', border: '#a855f7' };
    default:
      return { bg: 'rgba(156, 163, 175, 0.15)', text: '#9ca3af', border: '#6b7280' };
  }
}

export function getEventTypeBadge(type: string): { bg: string; text: string } {
  switch (type) {
    case 'INTERNAL':
      return { bg: '#374151', text: '#e5e7eb' };
    case 'SEND':
      return { bg: '#1e3a8a', text: '#93c5fd' };
    case 'RECEIVE':
      return { bg: '#064e3b', text: '#6ee7b7' };
    case 'MARKER':
      return { bg: '#831843', text: '#f472b6' };
    case 'SNAPSHOT_START':
    case 'SNAPSHOT_COMPLETE':
      return { bg: '#4c1d95', text: '#c4b5fd' };
    default:
      return { bg: '#1f2937', text: '#d1d5db' };
  }
}
