'use client'

import { useState } from 'react'

export default function LeadUpload({
  campaignId,
  onClose,
}: {
  campaignId: string
  onClose: () => void
}) {
  const [result, setResult] = useState<{ inserted: number; skipped: number } | null>(null)
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setError('')
    setUploading(true)
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`/api/leads/upload?campaign_id=${campaignId}`, {
      method: 'POST',
      body: form,
    })
    setUploading(false)
    if (!res.ok) {
      setError('Upload failed — check CSV format and required columns.')
      return
    }
    setResult((await res.json()) as { inserted: number; skipped: number })
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl shadow-2xl w-[400px] overflow-hidden">
        {/* Header */}
        <div className="px-6 py-5 border-b border-slate-100">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center">
                <svg className="w-4 h-4 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
              <h2 className="text-base font-bold text-slate-900">Upload Leads</h2>
            </div>
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
          <div className="bg-slate-50 rounded-xl border border-slate-100 px-4 py-3">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Required columns</p>
            <div className="flex gap-2">
              <code className="text-xs bg-white border border-slate-200 rounded px-1.5 py-0.5 text-slate-700">phone_number</code>
              <code className="text-xs bg-white border border-slate-200 rounded px-1.5 py-0.5 text-slate-700">timezone</code>
            </div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mt-2.5 mb-1.5">Optional</p>
            <div className="flex gap-2">
              <code className="text-xs bg-white border border-slate-200 rounded px-1.5 py-0.5 text-slate-700">first_name</code>
              <code className="text-xs bg-white border border-slate-200 rounded px-1.5 py-0.5 text-slate-700">last_name</code>
              <code className="text-xs bg-white border border-slate-200 rounded px-1.5 py-0.5 text-slate-700">company</code>
            </div>
          </div>

          <label className="flex flex-col items-center gap-3 border-2 border-dashed border-slate-200 rounded-xl px-4 py-6 hover:border-blue-400 hover:bg-blue-50/30 transition-colors cursor-pointer">
            <svg className="w-8 h-8 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span className="text-sm text-slate-500">
              {uploading ? 'Uploading…' : 'Click to select a CSV file'}
            </span>
            <input type="file" accept=".csv" onChange={onFile} className="hidden" disabled={uploading} />
          </label>

          {result && (
            <div className="flex items-center gap-3 bg-green-50 border border-green-100 rounded-xl px-4 py-3">
              <svg className="w-5 h-5 text-green-600 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-sm text-green-700 font-medium">
                {result.inserted} leads added &nbsp;·&nbsp; {result.skipped} skipped
              </p>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-3 bg-red-50 border border-red-100 rounded-xl px-4 py-3">
              <svg className="w-5 h-5 text-red-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-slate-50 border-t border-slate-100 flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 text-sm font-medium text-slate-600 border border-slate-200 rounded-xl hover:bg-white transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
