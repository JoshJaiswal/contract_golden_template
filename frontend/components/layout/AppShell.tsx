import type { ReactNode } from 'react';
import { Header } from './Header';
import { Footer } from './Footer';
export function AppShell({ children }: { children: ReactNode }) { return <div className="min-h-screen bg-white text-zinc-900"><Header /><main className="mx-auto w-full max-w-7xl px-4 py-6 md:px-6 md:py-8">{children}</main><Footer /></div>; }