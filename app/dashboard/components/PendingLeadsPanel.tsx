'use client'

import { useEffect, useState } from 'react'

interface Lead {
  id: string
  phone_number: string
  first_name: string | null
  last_name: string | null
  status: string
  campaign_id: string | null
}

export default function PendingLeadsPanel({ campaignId }: { campaignId: string }) {
  const [leads, setLeads] = useState<Lead[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetch(`/api/leads?campaign_id=${campaignId}&status=pending`)
      .then(r => r.json())
      .then((data: unknown) => {
        setLeads(Array.isArray(data) ? (data as Lead[]) : [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [campaignId])

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-3 text-slate-400 text-sm">
        <svg className="animate-spin w-4 h-4 text-blue-400" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        Loading pending leads…
      </div>
    )
  }

  if (leads.length === 0) {
    return (
      <div className="flex items-center gap-2.5 py-3 text-sm text-slate-500">
        <svg className="w-4 h-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        All leads have been contacted — no pending leads remaining.
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-orange-100 text-orange-700 text-xs font-semibold">
          <span className="w-1.5 h-1.5 rounded-full bg-orange-500"></span>
          {leads.length} pending — not yet contacted
        </span>
      </div>
      <div className="rounded-lg border border-slate-200 overflow-hidden bg-white">
        <table className="w-full text-xs">
          <thead className="bg-slate-50 border-b border-slate-100">
            <tr>
              <th className="text-left px-4 py-2.5 font-semibold text-slate-400 uppercase tracking-wider">#</th>
              <th className="text-left px-4 py-2.5 font-semibold text-slate-400 uppercase tracking-wider">Name</th>
              <th className="text-left px-4 py-2.5 font-semibold text-slate-400 uppercase tracking-wider">Phone</th>
              <th className="text-left px-4 py-2.5 font-semibold text-slate-400 uppercase tracking-wider">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {leads.map((lead, i) => {
              const fullName = [lead.first_name, lead.last_name].filter(Boolean).join(' ')
              return (
                <tr key={lead.id} className="hover:bg-blue-50/40 transition-colors">
                  <td className="px-4 py-2.5 text-slate-400 font-mono">{i + 1}</td>
                  <td className="px-4 py-2.5 font-medium text-slate-700">
                    {fullName || <span className="text-slate-400 italic">Unknown</span>}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-slate-600">{lead.phone_number}</td>
                  <td className="px-4 py-2.5">
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-orange-50 text-orange-600 text-[10px] font-bold uppercase tracking-wide">
                      Pending
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
