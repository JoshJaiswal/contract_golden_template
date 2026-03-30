import { Card, CardBody } from '@/components/ui/card';
import { safeJson } from '@/lib/format';

export function JsonViewer({ value }: { value: unknown }) {
  return (
    <Card>
      <CardBody>
        <pre className="max-h-[650px] overflow-auto rounded-xl bg-zinc-950 p-4 text-xs leading-6 text-zinc-100">
          {safeJson(value)}
        </pre>
      </CardBody>
    </Card>
  );
}