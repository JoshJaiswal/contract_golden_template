import { Card, CardBody } from '@/components/ui/card';
import { SummaryRow } from './SummaryRow';
import type { SummarySection as SummarySectionType } from '@/lib/format';

export function SummarySection({
  sections,
}: {
  sections: SummarySectionType[];
}) {
  if (!sections || !sections.length) {
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
            <h3 className="mb-3 flex items-center gap-2 font-semibold text-zinc-900">
              <span>{section.icon}</span>
              <span>{section.title}</span>
            </h3>

            {section.fields.map((field) => (
              <SummaryRow
                key={field.path}
                label={field.label}
                value={field.value}
              />
            ))}
          </CardBody>
        </Card>
      ))}
    </div>
  );
}