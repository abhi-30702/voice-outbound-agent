import LiveCallFeed from '@/components/LiveCallFeed'

export default function LiveMonitorPage() {
  return (
    <div className="px-8 py-8">
      <div className="mb-7">
        <h1 className="text-2xl font-bold text-slate-900">Live Monitor</h1>
        <p className="text-sm text-slate-500 mt-1">Real-time view of all active outbound calls</p>
      </div>
      <LiveCallFeed />
    </div>
  )
}
