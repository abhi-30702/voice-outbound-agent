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
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-green-50 to-emerald-50 border-b border-green-100 px-5 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500"></span>
          </span>
          <span className="font-mono text-sm font-semibold text-slate-800">
            {call.phone_number ?? call.call_id}
          </span>
        </div>
        <span className="inline-flex items-center gap-1.5 text-[11px] font-bold text-green-700 bg-green-100 border border-green-200 px-2.5 py-1 rounded-full uppercase tracking-wide">
          {call.status}
        </span>
      </div>

      {/* Transcript */}
      <div className="px-5 py-4 min-h-[90px]">
        <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest mb-2.5">
          Live Transcript
        </p>
        {call.transcript ? (
          <p className="text-sm text-slate-600 leading-relaxed whitespace-pre-wrap">
            {call.transcript}
          </p>
        ) : (
          <p className="text-sm text-slate-400 italic">Waiting for transcript…</p>
        )}
      </div>
    </div>
  )
}
