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

    const ws = new WebSocket('ws://localhost:8000/ws/calls')
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
  if (activeCalls.length === 0) {
    return <p className="text-gray-500">No active calls right now.</p>
  }
  return (
    <div className="flex flex-col gap-4">
      {activeCalls.map(c => <CallCard key={c.call_id} call={c} />)}
    </div>
  )
}
