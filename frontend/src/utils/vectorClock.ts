export function happensBefore(a: number[], b: number[]): boolean {
  if (!a || !b || a.length !== b.length) return false;
  const allLessOrEqual = a.every((val, i) => val <= b[i]);
  const atLeastOneLess = a.some((val, i) => val < b[i]);
  return allLessOrEqual && atLeastOneLess;
}

export function areEqual(a: number[], b: number[]): boolean {
  if (!a || !b || a.length !== b.length) return false;
  return a.every((val, i) => val === b[i]);
}

export function isConcurrent(a: number[], b: number[]): boolean {
  if (areEqual(a, b)) return false;
  return !happensBefore(a, b) && !happensBefore(b, a);
}

export function compareVectorClocks(a: number[], b: number[]): 'BEFORE' | 'AFTER' | 'CONCURRENT' | 'SAME' {
  if (areEqual(a, b)) return 'SAME';
  if (happensBefore(a, b)) return 'BEFORE';
  if (happensBefore(b, a)) return 'AFTER';
  return 'CONCURRENT';
}
