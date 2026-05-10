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
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-96 shadow-xl">
        <h2 className="text-lg font-bold mb-4">New Campaign</h2>
        <label className="block text-sm font-medium mb-1">Campaign Name</label>
        <input
          value={name}
          onChange={e => setName(e.target.value)}
          className="w-full border rounded px-3 py-2 mb-4 text-sm"
          placeholder="e.g. May Real Estate Batch"
        />
        <label className="block text-sm font-medium mb-1">Template</label>
        <select
          value={template}
          onChange={e => setTemplate(e.target.value)}
          className="w-full border rounded px-3 py-2 mb-4 text-sm"
        >
          {TEMPLATES.map(t => (
            <option key={t.key} value={t.key}>{t.label}</option>
          ))}
        </select>
        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm border rounded hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={!name || loading}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Creating…' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  )
}
