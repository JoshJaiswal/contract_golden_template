// lib/format.ts
// ─────────────────────────────────────────────────────────────
// Typed extractors that match the ACTUAL canonical JSON shape
// ─────────────────────────────────────────────────────────────

export type ContractType = 'auto' | 'nda' | 'sow' | 'both';

// ── Display formatters ────────────────────────────────────────

export function formatContractType(ct?: string): string {
  const map: Record<string, string> = {
    auto: 'Auto-detect',
    nda: 'NDA',
    sow: 'SOW',
    both: 'NDA + SOW',
  };
  return map[ct ?? ''] ?? ct ?? '—';
}

export function formatDateTime(iso?: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-IN', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit', hour12: true,
      timeZone: 'Asia/Kolkata',
    });
  } catch {
    return iso;
  }
}

// ── Summary extraction ────────────────────────────────────────

export interface SummaryField {
  label: string;
  value: string | string[];
  path: string;
}

export interface SummarySection {
  title: string;
  icon: string;
  fields: SummaryField[];
}

function val(v: unknown): string | string[] | null {
  if (v === null || v === undefined) return null;
  if (typeof v === 'string') return v.trim() || null;
  if (typeof v === 'number') return String(v);
  if (Array.isArray(v)) {
    const items = v
      .map((i) => (typeof i === 'string' ? i.trim() : JSON.stringify(i)))
      .filter(Boolean);
    return items.length ? items : null;
  }
  return null;
}

export function extractSummarySections(
  canonical: Record<string, any> | null
): SummarySection[] {
  if (!canonical) return [];
  const sections: SummarySection[] = [];

  // ── Parties ──────────────────────────────────────────────
  const p = canonical.parties ?? {};
  const client = p.client ?? {};
  const vendor = p.vendor ?? {};
  const partiesFields: SummaryField[] = [];

  if (val(client.name))
    partiesFields.push({ label: 'Client', value: val(client.name)!, path: 'parties.client.name' });
  if (val(vendor.name))
    partiesFields.push({ label: 'Vendor', value: val(vendor.name)!, path: 'parties.vendor.name' });
  if (val(p.ndaType))
    partiesFields.push({ label: 'NDA Type', value: val(p.ndaType)!, path: 'parties.ndaType' });
  if (Array.isArray(client.signatories) && client.signatories.length)
    partiesFields.push({ label: 'Client Signatories', value: client.signatories, path: 'parties.client.signatories' });
  if (Array.isArray(vendor.signatories) && vendor.signatories.length)
    partiesFields.push({ label: 'Vendor Signatories', value: vendor.signatories, path: 'parties.vendor.signatories' });

  if (partiesFields.length)
    sections.push({ title: 'Parties', icon: '👥', fields: partiesFields });

  // ── Dates ────────────────────────────────────────────────
  const d = canonical.dates ?? {};
  const datesFields: SummaryField[] = [];

  if (val(d.effectiveDate))
    datesFields.push({ label: 'Effective Date', value: val(d.effectiveDate)!, path: 'dates.effectiveDate' });
  if (val(d.expirationDate))
    datesFields.push({ label: 'Expiration Date', value: val(d.expirationDate)!, path: 'dates.expirationDate' });
  if (val(d.executionDate))
    datesFields.push({ label: 'Execution Date', value: val(d.executionDate)!, path: 'dates.executionDate' });
  if (val(d.noticePeriod))
    datesFields.push({ label: 'Notice Period', value: val(d.noticePeriod)!, path: 'dates.noticePeriod' });

  if (datesFields.length)
    sections.push({ title: 'Dates', icon: '📅', fields: datesFields });

  // ── Scope ────────────────────────────────────────────────
  const s = canonical.scope ?? {};
  const scopeFields: SummaryField[] = [];

  if (val(s.description))
    scopeFields.push({ label: 'Description', value: val(s.description)!, path: 'scope.description' });
  if (val(s.deliverables))
    scopeFields.push({ label: 'Deliverables', value: val(s.deliverables)!, path: 'scope.deliverables' });
  if (val(s.outOfScope))
    scopeFields.push({ label: 'Out of Scope', value: val(s.outOfScope)!, path: 'scope.outOfScope' });
  if (val(s.milestones))
    scopeFields.push({ label: 'Milestones', value: val(s.milestones)!, path: 'scope.milestones' });
  if (val(s.assumptions))
    scopeFields.push({ label: 'Assumptions', value: val(s.assumptions)!, path: 'scope.assumptions' });

  if (scopeFields.length)
    sections.push({ title: 'Scope of Work', icon: '📐', fields: scopeFields });

  // ── Commercials ──────────────────────────────────────────
  const c = canonical.commercials ?? {};
  const commFields: SummaryField[] = [];

  if (val(c.totalValue)) {
    const formatted = c.currency
      ? `${c.currency} ${Number(c.totalValue).toLocaleString('en-IN')}`
      : String(c.totalValue);
    commFields.push({ label: 'Total Value', value: formatted, path: 'commercials.totalValue' });
  }
  if (val(c.paymentTerms))
    commFields.push({ label: 'Payment Terms', value: val(c.paymentTerms)!, path: 'commercials.paymentTerms' });
  if (val(c.pricingModel))
    commFields.push({ label: 'Pricing Model', value: val(c.pricingModel)!, path: 'commercials.pricingModel' });
  if (val(c.taxes))
    commFields.push({ label: 'Taxes', value: val(c.taxes)!, path: 'commercials.taxes' });
  if (val(c.expenses))
    commFields.push({ label: 'Expenses', value: val(c.expenses)!, path: 'commercials.expenses' });

  if (commFields.length)
    sections.push({ title: 'Commercials', icon: '💰', fields: commFields });

  // ── Confidentiality ──────────────────────────────────────
  const conf = canonical.confidentiality ?? {};
  const confFields: SummaryField[] = [];

  if (val(conf.term))
    confFields.push({ label: 'Term (years)', value: val(conf.term)!, path: 'confidentiality.term' });
  if (val(conf.exceptions))
    confFields.push({ label: 'Exceptions', value: val(conf.exceptions)!, path: 'confidentiality.exceptions' });
  if (val(conf.obligations))
    confFields.push({ label: 'Obligations', value: val(conf.obligations)!, path: 'confidentiality.obligations' });

  if (confFields.length)
    sections.push({ title: 'Confidentiality', icon: '🔒', fields: confFields });

  // ── Legal ────────────────────────────────────────────────
  const l = canonical.legal ?? {};
  const legalFields: SummaryField[] = [];

  if (val(l.governingLaw))
    legalFields.push({ label: 'Governing Law', value: val(l.governingLaw)!, path: 'legal.governingLaw' });
  if (val(l.jurisdiction))
    legalFields.push({ label: 'Jurisdiction', value: val(l.jurisdiction)!, path: 'legal.jurisdiction' });
  if (val(l.liabilityCap))
    legalFields.push({ label: 'Liability Cap', value: val(l.liabilityCap)!, path: 'legal.liabilityCap' });
  if (val(l.ipOwnership))
    legalFields.push({ label: 'IP Ownership', value: val(l.ipOwnership)!, path: 'legal.ipOwnership' });
  if (val(l.disputeResolution))
    legalFields.push({ label: 'Dispute Resolution', value: val(l.disputeResolution)!, path: 'legal.disputeResolution' });

  if (legalFields.length)
    sections.push({ title: 'Legal', icon: '⚖️', fields: legalFields });

  // ── Security ─────────────────────────────────────────────
  const sec = canonical.security ?? {};
  const secFields: SummaryField[] = [];

  if (val(sec.requirements))
    secFields.push({ label: 'Requirements', value: val(sec.requirements)!, path: 'security.requirements' });
  if (val(sec.dataResidency))
    secFields.push({ label: 'Data Residency', value: val(sec.dataResidency)!, path: 'security.dataResidency' });
  if (val(sec.complianceStandards))
    secFields.push({ label: 'Compliance Standards', value: val(sec.complianceStandards)!, path: 'security.complianceStandards' });
  if (val(sec.personalDataProcessing))
    secFields.push({ label: 'Personal Data Processing', value: val(sec.personalDataProcessing)!, path: 'security.personalDataProcessing' });
  if (val(sec.privacyRequirements))
    secFields.push({ label: 'Privacy Requirements', value: val(sec.privacyRequirements)!, path: 'security.privacyRequirements' });

  if (secFields.length)
    sections.push({ title: 'Security & Privacy', icon: '🛡️', fields: secFields });

  // ── Project Governance ───────────────────────────────────
  const pg = canonical.projectGovernance ?? {};
  const pgFields: SummaryField[] = [];

  if (val(pg.projectTimeline))
    pgFields.push({ label: 'Project Timeline', value: val(pg.projectTimeline)!, path: 'projectGovernance.projectTimeline' });
  if (val(pg.keyPersonnel))
    pgFields.push({ label: 'Key Personnel', value: val(pg.keyPersonnel)!, path: 'projectGovernance.keyPersonnel' });
  if (val(pg.acceptanceCriteria))
    pgFields.push({ label: 'Acceptance Criteria', value: val(pg.acceptanceCriteria)!, path: 'projectGovernance.acceptanceCriteria' });
  if (val(pg.changeControl))
    pgFields.push({ label: 'Change Control', value: val(pg.changeControl)!, path: 'projectGovernance.changeControl' });
  if (val(pg.governanceModel))
    pgFields.push({ label: 'Governance Model', value: val(pg.governanceModel)!, path: 'projectGovernance.governanceModel' });

  if (pgFields.length)
    sections.push({ title: 'Project Governance', icon: '📊', fields: pgFields });

  return sections;
}

// ── Conflicts extraction ──────────────────────────────────────

export interface ConflictItem {
  field: string;
  chosen: string;
  chosenSource: string;
  alternatives: Array<{ value: string | string[]; source: string }>;
}

export function extractConflicts(
  canonical: Record<string, any> | null
): ConflictItem[] {
  if (!canonical?.conflicts) return [];
  return canonical.conflicts.map((c: any) => ({
    field: c.field ?? '',
    chosen: typeof c.chosen === 'string' ? c.chosen : JSON.stringify(c.chosen),
    chosenSource: c.chosenSource ?? '',
    alternatives: (c.alternatives ?? []).map((a: any) => ({
      value: a.value,
      source: a.source ?? '',
    })),
  }));
}

// ── Missing fields extraction ─────────────────────────────────

export interface MissingFieldGroup {
  section: string;
  icon: string;
  items: Array<{ full: string; label: string; hint: string }>;
}

const SECTION_META: Record<string, { icon: string; label: string }> = {
  parties: { icon: '👥', label: 'Parties' },
  dates: { icon: '📅', label: 'Dates' },
  scope: { icon: '📐', label: 'Scope of Work' },
  confidentiality: { icon: '🔒', label: 'Confidentiality' },
  commercials: { icon: '💰', label: 'Commercials' },
  legal: { icon: '⚖️', label: 'Legal' },
  security: { icon: '🛡️', label: 'Security' },
  projectgovernance: { icon: '📊', label: 'Project Governance' },
  risks: { icon: '⚠️', label: 'Risks' },
  other: { icon: '📋', label: 'Other' },
};

export function extractMissingFields(
  canonical: Record<string, any> | null
): MissingFieldGroup[] {
  if (!canonical) return [];

  const raw: string[] =
    canonical.missingFields ?? canonical.missing_fields ?? [];

  if (!raw.length) return [];

  const grouped: Record<string, MissingFieldGroup> = {};

  for (const entry of raw) {
    const field = typeof entry === 'string' ? entry : (entry as any).field ?? '';
    if (!field) continue;

    const parts = field.split('.');
    const sectionKey = parts[0].toLowerCase();
    const meta = SECTION_META[sectionKey] ?? SECTION_META.other;

    if (!grouped[sectionKey]) {
      grouped[sectionKey] = {
        section: meta.label,
        icon: meta.icon,
        items: [],
      };
    }

    // Human-readable label from the last dot segment
    const rawLabel = parts[parts.length - 1];
    const label = rawLabel
      .replace(/([A-Z])/g, ' $1')
      .replace(/^./, (s) => s.toUpperCase())
      .trim();

    grouped[sectionKey].items.push({
      full: field,
      label,
      hint: `Required field: ${field}`,
    });
  }

  return Object.values(grouped);
}

// ───────────────────────────────
// ✅ Add missing exports
// ───────────────────────────────

// Return file extension safely
export function getFileExtension(name?: string | null): string {
  if (!name) return '';
  const parts = name.split('.');
  return parts.length > 1 ? parts.pop()!.toLowerCase() : '';
}

// Safely parse JSON for JsonViewer
export function safeJson(value: any): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

// Convert canonical key → human readable label
export function cnKeyToLabel(key: string): string {
  if (!key) return '';
  return key
    .split('.')
    .pop()!
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (s) => s.toUpperCase())
    .trim();
}

// Stats from job record (update as needed)
export function extractJobStats(job: any) {
  if (!job) return {};

  return {
    status: job.status ?? 'unknown',
    fileName: job.file_name ?? '—',
    pages: job.page_count ?? 0,
    created: job.created_at ?? null,
    updated: job.updated_at ?? null,
  };
}