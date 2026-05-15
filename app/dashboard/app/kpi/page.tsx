import KpiChart from '@/components/KpiChart'
import RangeSelector from '@/components/RangeSelector'

export default function KpiPage({
  searchParams,
}: {
  searchParams: { range?: string }
}) {
  const range = searchParams?.range ?? 'today'
  return (
    <div className="px-8 py-8">
      <div className="flex items-center justify-between mb-7">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Analytics</h1>
          <p className="text-sm text-slate-500 mt-1">Campaign performance and call metrics</p>
        </div>
        <RangeSelector current={range} />
      </div>
      <KpiChart range={range} />
    </div>
  )
}
