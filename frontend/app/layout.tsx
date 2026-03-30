import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import { Syne, DM_Sans, JetBrains_Mono } from 'next/font/google';
import './globals.css';

import { Providers } from './providers';

// Typography fonts
const syne = Syne({
  subsets: ['latin'],
  variable: '--font-syne',
});

const dmSans = DM_Sans({
  subsets: ['latin'],
  variable: '--font-dm-sans',
});

// Monospace replacement instead of DM_Mono
const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['300', '400', '500', '700'],
  variable: '--font-mono',
});

export const metadata: Metadata = {
  title: 'EY Contract Intelligence',
  description: 'Contract intelligence workspace for NDA and SOW generation',
};

export default function RootLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${syne.variable} ${dmSans.variable} ${jetbrainsMono.variable}`}
    >
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}