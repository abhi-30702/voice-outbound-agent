'use client'

import { useEffect, useState } from 'react'
import CallCard, { type CallState } from './CallCard'

type CallMap = Record<string, CallState>

export default function LiveCallFeed() {
  const [calls, setCalls] = useState<CallMap>({})

  useEffect(() => {
    fetch('/api/calls/active')
      .then(r => r.json())
      .then((data: Omit<CallState, 'transcript'>[]) => {
        const map: CallMap = {}
        data.forEach(c => { map[c.call_id] = { ...c, transcript: '' } })
        setCalls(map)
      })
      .catch(() => {})

    const wsUrl = process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000'
    const ws = new WebSocket(`${wsUrl}/ws/calls`)
    ws.onmessage = (e: MessageEvent) => {
      const msg = JSON.parse(e.data as string) as {
        event: string
        call_id: string
        payload: Record<string, string>
      }
      if (msg.event === 'call_started') {
        setCalls(prev => ({
          ...prev,
          [msg.call_id]: {
            call_id: msg.call_id,
            lead_id: null,
            phone_number: msg.payload?.from_number ?? null,
            status: 'calling',
            start_time: null,
            transcript: '',
          },
        }))
      } else if (msg.event === 'transcript_updated') {
        setCalls(prev => ({
          ...prev,
          [msg.call_id]: {
            ...(prev[msg.call_id] ?? {
              call_id: msg.call_id,
              lead_id: null,
              phone_number: null,
              status: 'calling',
              start_time: null,
              transcript: '',
            }),
            transcript: msg.payload?.transcript ?? '',
          },
        }))
      } else if (msg.event === 'call_ended') {
        setCalls(prev => {
          const next = { ...prev }
          delete next[msg.call_id]
          return next
        })
      }
    }
    return () => ws.close()
  }, [])

  const activeCalls = Object.values(calls)

  return (
    <div>
      {/* Status bar */}
      <div className="flex items-center gap-2 mb-6">
        {activeCalls.length > 0 ? (
          <>
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500"></span>
            </span>
            <span className="text-sm font-semibold text-slate-800">
              {activeCalls.length} active call{activeCalls.length !== 1 ? 's' : ''}
            </span>
          </>
        ) : (
          <>
            <span className="w-2.5 h-2.5 rounded-full bg-slate-300"></span>
            <span className="text-sm font-medium text-slate-500">Listening for calls…</span>
          </>
        )}
      </div>

      {activeCalls.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center bg-white rounded-2xl border border-slate-200">
          <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center mb-5">
            <svg className="w-8 h-8 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
            </svg>
          </div>
          <p className="font-semibold text-slate-700 text-base">No active calls</p>
          <p className="text-sm text-slate-400 mt-1.5 max-w-sm">
            Start the dialing worker to begin outbound calls. Calls will appear here in real time.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {activeCalls.map(c => <CallCard key={c.call_id} call={c} />)}
        </div>
      )}
    </div>
  )
}
