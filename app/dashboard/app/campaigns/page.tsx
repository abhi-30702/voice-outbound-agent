import CampaignTable from '@/components/CampaignTable'

async function getCampaigns() {
  try {
    const res = await fetch('http://localhost:8000/api/campaigns', { cache: 'no-store' })
    if (!res.ok) return []
    return res.json()
  } catch {
    return []
  }
}

export default async function CampaignsPage() {
  const campaigns = await getCampaigns()
  return (
    <>
      <h1 className="text-2xl font-bold mb-4">Campaigns</h1>
      <CampaignTable initialCampaigns={campaigns} />
    </>
  )
}
