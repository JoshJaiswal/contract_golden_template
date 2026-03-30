'use client';
import type { ReactNode } from 'react';
import { Toaster } from 'sonner';
export function Providers({ children }: { children: ReactNode }) { return (<><Toaster position="top-right" richColors={false} closeButton toastOptions={{ style: { border: '1px solid #E5E7EB', background: '#FFFFFF', color: '#1C1C1C', boxShadow: '0 12px 30px rgba(17,17,17,0.08)' } }} />{children}</>); }