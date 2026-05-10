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

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setError('')
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`/api/leads/upload?campaign_id=${campaignId}`, {
      method: 'POST',
      body: form,
    })
    if (!res.ok) {
      setError('Upload failed — check CSV format.')
      return
    }
    setResult((await res.json()) as { inserted: number; skipped: number })
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-80 shadow-xl">
        <h2 className="text-lg font-bold mb-2">Upload Leads</h2>
        <p className="text-xs text-gray-500 mb-4">
          Required columns: <code>phone_number</code>, <code>timezone</code>
          <br />Optional: <code>first_name</code>, <code>last_name</code>, <code>company</code>
        </p>
        <input type="file" accept=".csv" onChange={onFile} className="mb-3 text-sm" />
        {result && (
          <p className="text-green-700 text-sm">
            Inserted: {result.inserted} &nbsp;|&nbsp; Skipped: {result.skipped}
          </p>
        )}
        {error && <p className="text-red-500 text-sm">{error}</p>}
        <div className="flex justify-end mt-4">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm border rounded hover:bg-gray-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
