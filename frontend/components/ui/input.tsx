import { cn } from '@/lib/utils';
import type { InputHTMLAttributes } from 'react';

export function Input(
  props: InputHTMLAttributes<HTMLInputElement>
) {
  return (
    <input
      {...props}
      className={cn(
        'h-11 w-full rounded-xl border border-zinc-200 bg-white px-3 text-sm text-zinc-900 outline-none transition placeholder:text-zinc-400 focus:border-yellow-400 focus:ring-2 focus:ring-yellow-100',
        props.className
      )}
    />
  );
}
