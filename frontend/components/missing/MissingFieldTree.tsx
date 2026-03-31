import { MissingFieldCard } from './MissingFieldCard';

type MissingItem = {
  field?: string;
  full?: string;
  hint?: string;
  suggested?: string;
  label?: string;
};

type MissingGroup = {
  name?: string;
  section?: string;
  icon?: string;
  items: MissingItem[];
};

export function MissingFieldTree({ groups }: { groups: MissingGroup[] }) {
  if (!groups?.length) {
    return (
      <div className="rounded-2xl border border-dashed border-zinc-200 p-6 text-sm text-zinc-500">
        No missing fields detected.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {groups.map((group, gi) => {
        const title = group.name ?? group.section ?? "Other";
        const icon = group.icon ?? "";
        // ✅ Use a stable, non-empty key
        const groupKey = group.name ?? group.section ?? `group-${gi}`;

        return (
          <div key={groupKey} className="space-y-3">
            <h3 className="font-semibold text-zinc-900">
              {icon ? <span className="mr-1">{icon}</span> : null}
              {title}
            </h3>

            <div className="space-y-3">
              {(group.items ?? []).map((item, ii) => {
                // ✅ Prefer unique identifiers, fallback to composite
                const itemKey =
                  item.field ??
                  item.full ??
                  `${groupKey}-${item.label ?? item.hint ?? ""}-${ii}`;

                // Normalize props for MissingFieldCard
                const normalized = {
                  field: item.field ?? item.full ?? "",
                  hint: item.hint,
                  suggested: item.suggested,
                };

                return <MissingFieldCard key={itemKey} {...normalized} />;
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}