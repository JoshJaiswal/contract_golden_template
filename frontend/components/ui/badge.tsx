import type { HTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export function Badge({
  className,
  tone = 'neutral',
  ...props
}: HTMLAttributes<HTMLSpanElement> & {
  tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'yellow';
}) {
  const toneClasses = {
    neutral: 'border-zinc-200 bg-zinc-100 text-zinc-600',
    success: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    warning: 'border-amber-200 bg-amber-50 text-amber-700',
    danger: 'border-red-200 bg-red-50 text-red-700',
    yellow: 'border-yellow-200 bg-yellow-100 text-zinc-900',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium',
        toneClasses[tone],
        className
      )}
      {...props}
    />
  );
}