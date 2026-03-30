'use client';
import { useState } from 'react';
import { CheckCircle2 } from 'lucide-react';
import { Card, CardBody } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAppStore } from '@/store/useAppStore';
export function MissingFieldCard({ field, hint, suggested }: { field: string; hint?: string; suggested?: string }) { const [value, setValue] = useState(suggested ?? ''); const setOverride = useAppStore((s) => s.setOverride); const dismissField = useAppStore((s) => s.dismissField); return <Card><CardBody><div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between"><div className="min-w-0 flex-1"><p className="text-base font-semibold text-zinc-900">{field}</p><p className="mt-1 text-sm text-zinc-500">{hint || 'This value was not detected in the source document.'}</p></div><div className="w-full shrink-0 space-y-2 lg:w-[300px]"><Input value={value} onChange={(e) => setValue(e.target.value)} placeholder="Add the missing value" /><div className="flex flex-wrap gap-2"><Button variant="primary" onClick={() => setOverride(field, value)}><CheckCircle2 className="h-4 w-4" />Save value</Button><Button variant="secondary" onClick={() => dismissField(field)}>Dismiss</Button></div></div></div></CardBody></Card>; }