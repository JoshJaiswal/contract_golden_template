import { Card, CardBody } from '@/components/ui/card';

export function MetricCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <Card>
      <CardBody>
        <p className="text-xs font-mono uppercase tracking-[0.24em] text-zinc-500">
          {label}
        </p>

        <p className="mt-2 font-[family-name:var(--font-syne)] text-3xl font-bold text-zinc-900">
          {value}
        </p>

        {sub ? (
          <p className="mt-1 text-sm text-zinc-500">
            {sub}
          </p>
        ) : null}
      </CardBody>
    </Card>
  );
}