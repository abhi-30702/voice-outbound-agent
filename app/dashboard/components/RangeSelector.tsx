'use client'

import { useRouter } from 'next/navigation'

const RANGES = [
  { label: 'Today', value: 'today' },
  { label: '7 days', value: '7d' },
  { label: '30 days', value: '30d' },
]

export default function RangeSelector({ current }: { current: string }) {
  const router = useRouter()
  return (
    <div className="flex gap-2">
      {RANGES.map(r => (
        <button
          key={r.value}
          onClick={() => router.push(`/kpi?range=${r.value}`)}
          className={`px-3 py-1 rounded text-sm border transition-colors ${
            current === r.value
              ? 'bg-blue-600 text-white border-blue-600'
              : 'bg-white hover:bg-gray-50'
          }`}
        >
          {r.label}
        </button>
      ))}
    </div>
  )
}
