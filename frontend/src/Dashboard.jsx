import { useCallback, useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from './api'
import { fmtDur } from './util'

const hhmm = (ms) => new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
const axis = { fontSize: 12, fill: '#5B6878' }

export default function Dashboard({ queueId, queueName }) {
  const [d, setD] = useState(null)
  const [err, setErr] = useState('')

  const load = useCallback(async () => {
    try { setD(await api(`/queues/${queueId}/analytics`)); setErr('') } catch (e) { setErr(e.message) }
  }, [queueId])

  useEffect(() => {
    load()
    const t = setInterval(load, 8000)
    return () => clearInterval(t)
  }, [load])

  if (err) return <div className="error">{err}</div>
  if (!d) return <div className="muted">Loading dashboard…</div>

  const s = d.summary
  const trend = d.length_trend.map((p) => ({ t: Date.parse(p.t), length: p.length }))
  const waits = d.wait_history.map((w) => ({ label: w.label, minutes: +(w.wait / 60).toFixed(2) }))
  const tiles = [
    ['Average wait', s.avg_wait ? fmtDur(s.avg_wait) : '–', 'before being called'],
    ['Longest wait', s.max_wait ? fmtDur(s.max_wait) : '–', 'before being called'],
    ['Average service time', s.avg_service ? fmtDur(s.avg_service) : '–', 'per served token'],
    ['Waiting right now', s.waiting, s.waiting ? `avg ${fmtDur(s.current_avg_wait)} so far` : 'queue is clear'],
    ['Peak queue length', s.peak_length, 'most people waiting at once'],
    ['Served / cancelled', `${s.served} / ${s.cancelled}`, `${s.total} tokens issued`],
  ]

  return (
    <section>
      <h1>{queueName} · analytics</h1>
      <div className="tiles">
        {tiles.map(([label, value, note]) => (
          <div className="tile" key={label}>
            <span className="tile-label">{label}</span>
            <span className="tile-value">{value}</span>
            <span className="tile-note">{note}</span>
          </div>
        ))}
      </div>

      <div className="chart-card">
        <h2>Queue length over time</h2>
        <p className="muted small">People waiting, recorded each time the line changes.</p>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={trend} margin={{ top: 8, right: 16, left: -16, bottom: 0 }}>
            <CartesianGrid stroke="#E4E9EE" vertical={false} />
            <XAxis dataKey="t" type="number" scale="time" domain={['dataMin', 'dataMax']} tickFormatter={hhmm} tick={axis} tickCount={6} />
            <YAxis allowDecimals={false} tick={axis} />
            <Tooltip labelFormatter={hhmm} formatter={(v) => [v, 'Waiting']} />
            <Line type="stepAfter" dataKey="length" stroke="#1F4FD8" strokeWidth={2.5} dot={trend.length < 25} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <h2>Wait time per token</h2>
        <p className="muted small">Minutes each person waited before being called (latest 30).</p>
        {waits.length === 0 ? (
          <div className="empty"><p>Call your first token to see wait times here.</p></div>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={waits} margin={{ top: 8, right: 16, left: -16, bottom: 0 }}>
              <CartesianGrid stroke="#E4E9EE" vertical={false} />
              <XAxis dataKey="label" tick={axis} />
              <YAxis tick={axis} />
              <Tooltip formatter={(v) => [`${v} min`, 'Waited']} />
              <Bar dataKey="minutes" fill="#0E1A2B" radius={[3, 3, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  )
}
