import { Card, CardBody } from '@/components/ui/card';
import { cnKeyToLabel } from '@/lib/format';
import { SummaryRow } from './SummaryRow';

export function SummarySection({
  sections,
}: {
  sections: { title: string; items: { key: string; value: any }[] }[];
}) {
  if (!sections.length) {
    return (
      <div className="rounded-2xl border border-dashed border-zinc-200 p-6 text-sm text-zinc-500">
        No summary data detected yet.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {sections.map((section) => (
        <Card key={section.title}>
          <CardBody>
            <h3 className="mb-2 font-semibold text-zinc-900">
              {section.title}
            </h3>

            {section.items.map((item) => (
              <SummaryRow
                key={item.key}
                label={cnKeyToLabel(item.key)}
                value={item.value}
              />
            ))}
          </CardBody>
        </Card>
      ))}
    </div>
  );
}