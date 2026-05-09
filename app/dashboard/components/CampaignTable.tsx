'use client'

import { useState } from 'react'
import CreateCampaignModal from './CreateCampaignModal'
import LeadUpload from './LeadUpload'

interface Campaign {
  id: string
  name: string
  status: string
  lead_count: number
}

export default function CampaignTable({ initialCampaigns }: { initialCampaigns: Campaign[] }) {
  const [campaigns, setCampaigns] = useState<Campaign[]>(initialCampaigns)
  const [showCreate, setShowCreate] = useState(false)
  const [uploadFor, setUploadFor] = useState<string | null>(null)

  async function patchStatus(id: string, status: string) {
    await fetch(`/api/campaigns/${id}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    })
    setCampaigns(prev => prev.map(c => (c.id === id ? { ...c, status } : c)))
  }

  function onCreated(campaign: Campaign) {
    setCampaigns(prev => [...prev, campaign])
    setShowCreate(false)
  }

  return (
    <>
      <button
        onClick={() => setShowCreate(true)}
        className="mb-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
      >
        + New Campaign
      </button>

      {showCreate && (
        <CreateCampaignModal onCreated={onCreated} onClose={() => setShowCreate(false)} />
      )}

      <table className="w-full bg-white shadow rounded-lg overflow-hidden text-sm">
        <thead className="bg-gray-100 text-left">
          <tr>
            <th className="p-3">Name</th>
            <th className="p-3">Status</th>
            <th className="p-3">Leads</th>
            <th className="p-3">Actions</th>
          </tr>
        </thead>
        <tbody>
          {campaigns.map(c => (
            <tr key={c.id} className="border-t">
              <td className="p-3">{c.name}</td>
              <td className="p-3 capitalize">{c.status}</td>
              <td className="p-3">{c.lead_count}</td>
              <td className="p-3 flex gap-2 flex-wrap">
                <button
                  onClick={() => patchStatus(c.id, 'active')}
                  className="px-2 py-1 bg-green-100 text-green-700 rounded"
                >
                  Resume
                </button>
                <button
                  onClick={() => patchStatus(c.id, 'paused')}
                  className="px-2 py-1 bg-yellow-100 text-yellow-700 rounded"
                >
                  Pause
                </button>
                <button
                  onClick={() => patchStatus(c.id, 'completed')}
                  className="px-2 py-1 bg-red-100 text-red-700 rounded"
                >
                  Stop
                </button>
                <button
                  onClick={() => setUploadFor(c.id)}
                  className="px-2 py-1 bg-blue-100 text-blue-700 rounded"
                >
                  Upload Leads
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {uploadFor && (
        <LeadUpload campaignId={uploadFor} onClose={() => setUploadFor(null)} />
      )}
    </>
  )
}
