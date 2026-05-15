'use client'

import React, { useState } from 'react'
import CreateCampaignModal from './CreateCampaignModal'
import LeadUpload from './LeadUpload'
import PendingLeadsPanel from './PendingLeadsPanel'

interface Campaign {
  id: string
  name: string
  status: string
  lead_count: number
}

const STATUS_CONFIG: Record<string, { dot: string; badge: string; label: string }> = {
  active:    { dot: 'bg-green-500',  badge: 'bg-green-50 text-green-700 border-green-200',   label: 'Active' },
  paused:    { dot: 'bg-yellow-500', badge: 'bg-yellow-50 text-yellow-700 border-yellow-200', label: 'Paused' },
  completed: { dot: 'bg-slate-400',  badge: 'bg-slate-50 text-slate-600 border-slate-200',    label: 'Completed' },
  draft:     { dot: 'bg-blue-400',   badge: 'bg-blue-50 text-blue-600 border-blue-200',       label: 'Draft' },
}

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] ?? { dot: 'bg-gray-400', badge: 'bg-gray-50 text-gray-600 border-gray-200', label: status }
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border ${cfg.badge}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`}></span>
      {cfg.label}
    </span>
  )
}

export default function CampaignTable({ initialCampaigns }: { initialCampaigns: Campaign[] }) {
  const [campaigns, setCampaigns] = useState<Campaign[]>(initialCampaigns)
  const [showCreate, setShowCreate] = useState(false)
  const [uploadFor, setUploadFor] = useState<string | null>(null)
  const [expandedLeads, setExpandedLeads] = useState<string | null>(null)
  const [patching, setPatching] = useState<string | null>(null)

  async function patchStatus(id: string, status: string) {
    setPatching(id)
    await fetch(`/api/campaigns/${id}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    })
    setCampaigns(prev => prev.map(c => (c.id === id ? { ...c, status } : c)))
    setPatching(null)
  }

  function onCreated(campaign: Campaign) {
    setCampaigns(prev => [...prev, campaign])
    setShowCreate(false)
  }

  return (
    <>
      {showCreate && <CreateCampaignModal onCreated={onCreated} onClose={() => setShowCreate(false)} />}
      {uploadFor && <LeadUpload campaignId={uploadFor} onClose={() => setUploadFor(null)} />}

      {/* Toolbar */}
      <div className="flex items-center justify-between mb-5">
        <p className="text-sm text-slate-500">
          {campaigns.length} campaign{campaigns.length !== 1 ? 's' : ''}
        </p>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 text-sm font-semibold transition-colors shadow-sm shadow-blue-900/20"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 4v16m8-8H4" />
          </svg>
          New Campaign
        </button>
      </div>

      {campaigns.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center bg-white rounded-2xl border border-slate-200">
          <div className="w-14 h-14 rounded-2xl bg-slate-100 flex items-center justify-center mb-5">
            <svg className="w-7 h-7 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
          </div>
          <p className="font-bold text-slate-700 text-base">No campaigns yet</p>
          <p className="text-sm text-slate-400 mt-1.5 max-w-xs">
            Create your first campaign to start making outbound calls.
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/80">
                <th className="text-left px-6 py-4 font-semibold text-slate-400 text-[11px] uppercase tracking-wider">Campaign</th>
                <th className="text-left px-6 py-4 font-semibold text-slate-400 text-[11px] uppercase tracking-wider">Status</th>
                <th className="text-left px-6 py-4 font-semibold text-slate-400 text-[11px] uppercase tracking-wider">Total Leads</th>
                <th className="text-left px-6 py-4 font-semibold text-slate-400 text-[11px] uppercase tracking-wider">Pending</th>
                <th className="text-right px-6 py-4 font-semibold text-slate-400 text-[11px] uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody>
              {campaigns.map(c => (
                <React.Fragment key={c.id}>
                  <tr className="border-t border-slate-100 hover:bg-slate-50/60 transition-colors group">
                    {/* Campaign name */}
                    <td className="px-6 py-4">
                      <span className="font-semibold text-slate-900">{c.name}</span>
                    </td>

                    {/* Status badge */}
                    <td className="px-6 py-4">
                      <StatusBadge status={c.status} />
                    </td>

                    {/* Lead count */}
                    <td className="px-6 py-4">
                      <span className="text-slate-700 font-medium">{c.lead_count.toLocaleString()}</span>
                    </td>

                    {/* Pending leads toggle */}
                    <td className="px-6 py-4">
                      <button
                        onClick={() => setExpandedLeads(prev => prev === c.id ? null : c.id)}
                        className={`inline-flex items-center gap-1.5 text-xs font-semibold transition-colors ${
                          expandedLeads === c.id
                            ? 'text-blue-700'
                            : 'text-blue-500 hover:text-blue-700'
                        }`}
                      >
                        View pending
                        <svg
                          className={`w-3.5 h-3.5 transition-transform duration-200 ${expandedLeads === c.id ? 'rotate-180' : ''}`}
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
                        </svg>
                      </button>
                    </td>

                    {/* Action buttons */}
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-end gap-2">
                        {c.status !== 'active' && (
                          <button
                            onClick={() => patchStatus(c.id, 'active')}
                            disabled={patching === c.id}
                            className="px-3 py-1.5 text-[11px] font-semibold bg-green-50 text-green-700 border border-green-200 rounded-lg hover:bg-green-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            Resume
                          </button>
                        )}
                        {c.status === 'active' && (
                          <button
                            onClick={() => patchStatus(c.id, 'paused')}
                            disabled={patching === c.id}
                            className="px-3 py-1.5 text-[11px] font-semibold bg-yellow-50 text-yellow-700 border border-yellow-200 rounded-lg hover:bg-yellow-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            Pause
                          </button>
                        )}
                        {c.status !== 'completed' && (
                          <button
                            onClick={() => patchStatus(c.id, 'completed')}
                            disabled={patching === c.id}
                            className="px-3 py-1.5 text-[11px] font-semibold bg-red-50 text-red-600 border border-red-200 rounded-lg hover:bg-red-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            Stop
                          </button>
                        )}
                        <button
                          onClick={() => setUploadFor(c.id)}
                          className="px-3 py-1.5 text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200 rounded-lg hover:bg-blue-100 transition-colors"
                        >
                          Upload Leads
                        </button>
                      </div>
                    </td>
                  </tr>

                  {/* Expandable pending leads panel */}
                  {expandedLeads === c.id && (
                    <tr className="border-t border-blue-100 bg-blue-50/30">
                      <td colSpan={5} className="px-6 py-5">
                        <PendingLeadsPanel campaignId={c.id} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
