import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Orqix | AI-Native Distributed ML Experiment Platform',
  description: 'Production-grade distributed experiment, lineage, registry, and workflow scheduler platform.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-darkbg text-gray-100 min-h-screen`}>
        {children}
      </body>
    </html>
  )
}
