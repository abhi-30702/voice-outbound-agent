import KpiChart from '@/components/KpiChart'
import RangeSelector from '@/components/RangeSelector'

export default function KpiPage({
  searchParams,
}: {
  searchParams: { range?: string }
}) {
  const range = searchParams?.range ?? 'today'
  return (
    <>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">KPI</h1>
        <RangeSelector current={range} />
      </div>
      <KpiChart range={range} />
    </>
  )
}
