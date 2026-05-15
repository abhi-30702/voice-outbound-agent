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

interface KpiCardProps {
  label: string
  value: string | number
  icon: React.ReactNode
  bg: string
  iconColor: string
}

function KpiCard({ label, value, icon, bg, iconColor }: KpiCardProps) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 flex items-start gap-4">
      <div className={`w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 ${bg}`}>
        <div className={iconColor}>{icon}</div>
      </div>
      <div className="min-w-0">
        <p className="text-xs text-slate-500 font-semibold uppercase tracking-wider leading-none">{label}</p>
        <p className="text-2xl font-bold text-slate-900 mt-1.5 leading-none">{value}</p>
      </div>
    </div>
  )
}

function SkeletonCard() {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 animate-pulse">
      <div className="flex items-start gap-4">
        <div className="w-11 h-11 rounded-xl bg-slate-100 flex-shrink-0"></div>
        <div className="flex-1">
          <div className="h-3 w-20 bg-slate-100 rounded mb-3"></div>
          <div className="h-7 w-16 bg-slate-100 rounded"></div>
        </div>
      </div>
    </div>
  )
}

export default function KpiChart({ range }: { range: string }) {
  const { data, isLoading } = useSWR<KpiData>(
    `/api/kpi?range=${range}`,
    fetcher,
    { refreshInterval: 30_000 },
  )

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <SkeletonCard key={i} />)}
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 h-72 animate-pulse">
          <div className="h-4 w-32 bg-slate-100 rounded mb-6"></div>
          <div className="h-full bg-slate-50 rounded-xl"></div>
        </div>
      </div>
    )
  }

  if (!data) return null

  const chartData = [
    { name: 'Calls Made', value: data.calls_made },
    { name: 'Avg Duration (s)', value: data.avg_duration_sec },
  ]

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <KpiCard
          label="Total Leads"
          value={data.total_leads.toLocaleString()}
          bg="bg-blue-50"
          iconColor="text-blue-600"
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
          }
        />
        <KpiCard
          label="Calls Made"
          value={data.calls_made.toLocaleString()}
          bg="bg-green-50"
          iconColor="text-green-600"
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
            </svg>
          }
        />
        <KpiCard
          label="Connection Rate"
          value={`${(data.connection_rate * 100).toFixed(1)}%`}
          bg="bg-violet-50"
          iconColor="text-violet-600"
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
          }
        />
        <KpiCard
          label="Avg Duration"
          value={`${data.avg_duration_sec}s`}
          bg="bg-orange-50"
          iconColor="text-orange-600"
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
        />
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-sm font-semibold text-slate-700">Call Activity Overview</h3>
          <span className="text-xs text-slate-400">Auto-refreshes every 30s</span>
        </div>
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.12} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 12, fill: '#94a3b8' }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 12, fill: '#94a3b8' }}
              axisLine={false}
              tickLine={false}
              width={36}
            />
            <Tooltip
              contentStyle={{
                borderRadius: '10px',
                border: '1px solid #e2e8f0',
                boxShadow: '0 4px 12px rgba(0,0,0,0.06)',
                fontSize: '12px',
              }}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke="#3b82f6"
              strokeWidth={2.5}
              fill="url(#areaGrad)"
              dot={{ fill: '#3b82f6', strokeWidth: 0, r: 4 }}
              activeDot={{ r: 5, fill: '#2563eb' }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
