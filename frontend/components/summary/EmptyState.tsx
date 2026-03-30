export function EmptyState({
  title,
  subtitle,
}: {
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-zinc-200 bg-zinc-50 p-8 text-center">
      <p className="text-base font-semibold text-zinc-900">
        {title}
      </p>

      {subtitle ? (
        <p className="mt-1 text-sm text-zinc-500">
          {subtitle}
        </p>
      ) : null}
    </div>
  );
}