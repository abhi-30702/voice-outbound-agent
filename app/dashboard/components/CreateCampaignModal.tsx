'use client'

import { useState } from 'react'

const TEMPLATES = [
  { label: 'Real Estate Lead Qualifier', key: 'real_estate' },
  { label: 'Recruitment Screener', key: 'recruitment' },
  { label: 'Financial Services Qualifier', key: 'financial_services' },
]

interface Campaign {
  id: string
  name: string
  status: string
  lead_count: number
}

export default function CreateCampaignModal({
  onCreated,
  onClose,
}: {
  onCreated: (c: Campaign) => void
  onClose: () => void
}) {
  const [name, setName] = useState('')
  const [template, setTemplate] = useState(TEMPLATES[0].key)
  const [loading, setLoading] = useState(false)

  async function submit() {
    setLoading(true)
    const res = await fetch('/api/campaigns', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        prompt_template: { template_key: template },
        llm_config: {},
      }),
    })
    const data = (await res.json()) as Campaign
    onCreated(data)
    setLoading(false)
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl shadow-2xl w-[420px] overflow-hidden">
        {/* Header */}
        <div className="px-6 py-5 border-b border-slate-100">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-slate-900">Create New Campaign</h2>
            <button
              onClick={onClose}
              className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1.5">
              Campaign Name
            </label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-shadow"
              placeholder="e.g. May Real Estate Batch"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1.5">
              Call Template
            </label>
            <select
              value={template}
              onChange={e => setTemplate(e.target.value)}
              className="w-full border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm text-slate-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-shadow"
            >
              {TEMPLATES.map(t => (
                <option key={t.key} value={t.key}>{t.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-slate-50 border-t border-slate-100 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-600 border border-slate-200 rounded-xl hover:bg-white transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={!name.trim() || loading}
            className="px-5 py-2 text-sm font-medium bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            {loading && (
              <svg className="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            )}
            {loading ? 'Creating…' : 'Create Campaign'}
          </button>
        </div>
      </div>
    </div>
  )
}
