import CampaignTable from '@/components/CampaignTable'

async function getCampaigns() {
  const apiBase = process.env.API_INTERNAL_URL || 'http://localhost:8000'
  try {
    const res = await fetch(`${apiBase}/api/campaigns`, { cache: 'no-store' })
    if (!res.ok) return []
    return res.json()
  } catch {
    return []
  }
}

export default async function CampaignsPage() {
  const campaigns = await getCampaigns()
  return (
    <div className="px-8 py-8">
      <div className="mb-7">
        <h1 className="text-2xl font-bold text-slate-900">Campaigns</h1>
        <p className="text-sm text-slate-500 mt-1">Manage outbound calling campaigns and view lead pipeline</p>
      </div>
      <CampaignTable initialCampaigns={campaigns} />
    </div>
  )
}
