export function SummaryRow({
  label,
  value,
}: {
  label: string;
  value: string | string[];
}) {
  return (
    <div className="flex gap-3 border-b border-zinc-100 py-2.5 last:border-0">
      <div className="w-44 flex-shrink-0 text-xs font-mono uppercase tracking-wide text-zinc-400 pt-0.5">
        {label}
      </div>

      <div className="flex-1 text-sm text-zinc-800">
        {Array.isArray(value) ? (
          <ul className="space-y-1">
            {value.map((v, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-yellow-500 mt-0.5">▸</span>
                <span>{v}</span>
              </li>
            ))}
          </ul>
        ) : (
          value
        )}
      </div>
    </div>
  );
}