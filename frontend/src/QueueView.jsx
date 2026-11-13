import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { fmtDur, secsSince, useNow } from './util'

export default function QueueView({ queueId, onChanged, onDeleted }) {
  const [data, setData] = useState(null)
  const [name, setName] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const now = useNow(1000)

  const load = useCallback(async () => {
    try { setData(await api(`/queues/${queueId}`)) } catch (e) { setErr(e.message) }
  }, [queueId])

  useEffect(() => {
    load()
    const t = setInterval(load, 4000)
    return () => clearInterval(t)
  }, [load])

  async function act(path, opts) {
    setBusy(true)
    setErr('')
    try {
      setData(await api(path, opts))
      onChanged()
      return true
    } catch (e) {
      setErr(e.message)
      load()
      return false
    } finally {
      setBusy(false)
    }
  }

  async function addToken(e) {
    e.preventDefault()
    if (await act(`/queues/${queueId}/tokens`, { method: 'POST', body: { name } })) setName('')
  }

  async function removeQueue() {
    if (!window.confirm(`Delete “${data.name}” and all of its tokens? This cannot be undone.`)) return
    try { await api(`/queues/${queueId}`, { method: 'DELETE' }); onDeleted() } catch (e) { setErr(e.message) }
  }

  if (!data) return <div className="muted">Loading queue…</div>
  const { waiting, serving } = data

  return (
    <section>
      <div className="qhead">
        <h1>{data.name}</h1>
        <button className="btn ghost danger-text" onClick={removeQueue}>Delete queue</button>
      </div>

      {err && <div className="error" role="alert">{err}</div>}

      <div className="board">
        <div className="board-main">
          <span className="board-label">Now serving</span>
          {serving.length === 0 ? (
            <p className="board-idle">Nobody is being served.</p>
          ) : (
            <ul className="serving-list">
              {serving.map((t) => (
                <li key={t.id}>
                  <span className="board-num">{t.label}</span>
                  <span className="serving-meta"><strong>{t.name}</strong><small>with you for {fmtDur(secsSince(t.called_at, now))}</small></span>
                  <button className="btn signal-outline" disabled={busy} onClick={() => act(`/tokens/${t.id}/complete`, { method: 'POST' })}>Mark done</button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <button className="btn signal call" disabled={busy || waiting.length === 0} onClick={() => act(`/queues/${queueId}/serve-next`, { method: 'POST' })}>
          Call next
          <small>{waiting.length ? `${waiting[0].label} · ${waiting[0].name}` : 'No one waiting'}</small>
        </button>
      </div>

      <form className="addrow" onSubmit={addToken}>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Person’s name" maxLength={60} aria-label="Person's name" required />
        <button className="btn primary" disabled={busy}>Add to queue</button>
      </form>

      <div className="listhead">
        <h2>Waiting</h2>
        <span className="muted small">{waiting.length} in line · {data.served_count} served · {data.cancelled_count} cancelled</span>
      </div>

      {waiting.length === 0 ? (
        <div className="empty"><p>No one is waiting. Add a person above to issue the first token.</p></div>
      ) : (
        <ol className="tickets">
          {waiting.map((t, i) => (
            <li key={t.id} className="ticket">
              <div className="pos" aria-label={`Position ${i + 1}`}>{i + 1}</div>
              <div className="stub"><span className="tnum">{t.label}</span></div>
              <div className="tinfo">
                <strong>{t.name}</strong>
                <small>waiting {fmtDur(secsSince(t.created_at, now))}</small>
              </div>
              <div className="tactions">
                <button className="icon" title="Move up" aria-label={`Move ${t.name} up`} disabled={busy || i === 0} onClick={() => act(`/tokens/${t.id}/move`, { method: 'POST', body: { direction: 'up' } })}>↑</button>
                <button className="icon" title="Move down" aria-label={`Move ${t.name} down`} disabled={busy || i === waiting.length - 1} onClick={() => act(`/tokens/${t.id}/move`, { method: 'POST', body: { direction: 'down' } })}>↓</button>
                <button className="btn ghost danger-text" disabled={busy} onClick={() => { if (window.confirm(`Cancel ${t.label} for ${t.name}?`)) act(`/tokens/${t.id}/cancel`, { method: 'POST' }) }}>Cancel token</button>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
