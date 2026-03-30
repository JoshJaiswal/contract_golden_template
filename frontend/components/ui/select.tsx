import { cn } from '@/lib/utils';
import type { SelectHTMLAttributes } from 'react';

export function Select(
  props: SelectHTMLAttributes<HTMLSelectElement>
) {
  return (
    <select
      {...props}
      className={cn(
        'h-11 w-full rounded-xl border border-zinc-200 bg-white px-3 text-sm text-zinc-900 outline-none transition focus:border-yellow-400 focus:ring-2 focus:ring-yellow-100',
        props.className
      )}
    />
  );
}