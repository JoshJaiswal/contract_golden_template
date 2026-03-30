export function SummaryRow({
  label,
  value,
}: {
  label: string;
  value: unknown;
}) {
  return (
    <div className="flex gap-4 border-b border-zinc-200 py-3 last:border-b-0">
      <div className="w-44 shrink-0 text-xs font-mono uppercase tracking-[0.18em] text-zinc-500">
        {label}
      </div>

      <div className="min-w-0 flex-1 text-sm leading-6 text-zinc-900">
        {String(value || '—')}
      </div>
    </div>
  );
}