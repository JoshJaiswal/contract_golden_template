import { cn } from '@/lib/utils';

export function Tabs({
  value,
  onChange,
  items,
}: {
  value: string;
  onChange: (value: string) => void;
  items: { value: string; label: string; count?: number }[];
}) {
  return (
    <div className="flex flex-wrap gap-2 border-b border-zinc-200 pb-3">
      {items.map((item) => (
        <button
          key={item.value}
          onClick={() => onChange(item.value)}
          className={cn(
            'rounded-t-xl border-b-2 px-4 py-2 text-sm font-semibold transition',
            value === item.value
              ? 'border-yellow-400 bg-yellow-50 text-zinc-900'
              : 'border-transparent text-zinc-500 hover:bg-zinc-50 hover:text-zinc-900'
          )}
        >
          <span>{item.label}</span>

          {typeof item.count === 'number' ? (
            <span className="ml-2 rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-600">
              {item.count}
            </span>
          ) : null}
        </button>
      ))}
    </div>
  );
}