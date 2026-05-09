export interface CallState {
  call_id: string
  lead_id: string | null
  phone_number: string | null
  status: string
  start_time: string | null
  transcript: string
}

export default function CallCard({ call }: { call: CallState }) {
  return (
    <div className="bg-white rounded-lg shadow p-4 border-l-4 border-green-500">
      <div className="flex justify-between mb-2">
        <span className="font-mono text-sm text-gray-700">
          {call.phone_number ?? call.call_id}
        </span>
        <span className="text-xs uppercase font-semibold text-green-600">{call.status}</span>
      </div>
      <p className="text-sm text-gray-600 whitespace-pre-wrap">
        {call.transcript || 'Waiting for transcript…'}
      </p>
    </div>
  )
}
