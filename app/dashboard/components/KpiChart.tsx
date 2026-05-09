'use client'

import useSWR from 'swr'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'

const fetcher = (url: string) => fetch(url).then(r => r.json())

interface KpiData {
  total_leads: number
  calls_made: number
  connection_rate: number
  avg_duration_sec: number
}

function KpiCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
    </div>
  )
}

export default function KpiChart({ range }: { range: string }) {
  const { data, isLoading } = useSWR<KpiData>(
    `/api/kpi?range=${range}`,
    fetcher,
    { refreshInterval: 30_000 },
  )

  if (isLoading) return <p className="text-gray-500">Loading…</p>
  if (!data) return null

  const chartData = [
    { name: 'Calls Made', value: data.calls_made },
    { name: 'Avg Duration (s)', value: data.avg_duration_sec },
  ]

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Total Leads" value={data.total_leads} />
        <KpiCard label="Calls Made" value={data.calls_made} />
        <KpiCard label="Connection Rate" value={`${(data.connection_rate * 100).toFixed(1)}%`} />
        <KpiCard label="Avg Duration" value={`${data.avg_duration_sec}s`} />
      </div>
      <div className="bg-white rounded-lg shadow p-4">
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Area type="monotone" dataKey="value" stroke="#2563eb" fill="#dbeafe" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
