import { ConflictList } from './ConflictList';

export function ConflictResolver({ conflicts }: { conflicts: { field: string; label: string; current: string; proposed: string; note?: string }[] }) {
  return <ConflictList conflicts={conflicts} />;
}