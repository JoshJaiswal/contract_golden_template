import type { ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export function Button(
  {
    className,
    variant = 'primary',
    size = 'md',
    ...props
  }: ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: 'primary' | 'secondary' | 'ghost';
    size?: 'sm' | 'md';
  }
) {
  const base =
    'inline-flex items-center justify-center gap-2 rounded-xl font-medium transition ' +
    'disabled:cursor-not-allowed disabled:opacity-50';

  const variants = {
    primary: 'bg-yellow-300 text-zinc-900 hover:bg-yellow-400',
    secondary: 'border border-zinc-200 bg-white text-zinc-900 hover:bg-zinc-50',
    ghost: 'bg-transparent text-zinc-700 hover:bg-zinc-100',
  };

  const sizes = {
    sm: 'h-9 px-3 text-sm',
    md: 'h-11 px-4 text-sm',
  };

  return (
    <button
      className={cn(base, variants[variant], sizes[size], className)}
      {...props}
    />
  );
}