import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Format integers with thousand separators. Accepts number-like inputs.
export function formatNumber(value: number | string | null | undefined): string {
  const n = typeof value === "string" ? Number(value) : (value ?? 0 as number);
  const num = Number.isFinite(n as number) ? (n as number) : 0;
  return new Intl.NumberFormat().format(num);
}
