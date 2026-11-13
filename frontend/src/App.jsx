import { useCallback, useEffect, useState } from 'react'
import { api, auth } from './api'
import Login from './Login'
import QueueView from './QueueView'
import Dashboard from './Dashboard'

export default function App() {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(!auth.get())
  const [queues, setQueues] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [tab, setTab] = useState('queue')
  const [newName, setNewName] = useState('')
  const [err, setErr] = useState('')

  const logout = useCallback(() => { auth.clear(); setUser(null); setQueues([]); setActiveId(null) }, [])

  useEffect(() => {
    window.addEventListener('lineup:logout', logout)
    return () => window.removeEventListener('lineup:logout', logout)
  }, [logout])

  useEffect(() => {
    if (!auth.get()) return
    api('/auth/me').then(setUser).catch(() => {}).finally(() => setReady(true))
  }, [])

  const loadQueues = useCallback(async () => {
    try {
      const list = await api('/queues')
      setQueues(list)
      setActiveId((cur) => (list.some((q) => q.id === cur) ? cur : list[0]?.id ?? null))
    } catch { /* handled by api() on 401 */ }
  }, [])

  useEffect(() => {
    if (!user) return
    loadQueues()
    const t = setInterval(loadQueues, 6000)
    return () => clearInterval(t)
  }, [user, loadQueues])

  async function createQueue(e) {
    e.preventDefault()
    setErr('')
    try {
      const q = await api('/queues', { method: 'POST', body: { name: newName } })
      setNewName('')
      await loadQueues()
      setActiveId(q.id)
      setTab('queue')
    } catch (x) { setErr(x.message) }
  }

  if (!ready) return <div className="splash">Loading…</div>
  if (!user) return <Login onAuthed={setUser} />

  const active = queues.find((q) => q.id === activeId)

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">Lineup</div>
        <div className="who">
          <span>{user.username}</span>
          <button className="btn ghost" onClick={logout}>Sign out</button>
        </div>
      </header>

      <aside className="side">
        <h2 className="side-title">Your queues</h2>
        <nav>
          {queues.map((q) => (
            <button key={q.id} className={'qitem' + (q.id === activeId ? ' on' : '')} onClick={() => { setActiveId(q.id); setTab('queue') }}>
              <span className="qname">{q.name}</span>
              <span className="qcount" title="Waiting">{q.waiting}</span>
            </button>
          ))}
          {!queues.length && <p className="muted small">No queues yet. Name your first one below.</p>}
        </nav>
        <form className="newq" onSubmit={createQueue}>
          <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Queue name, e.g. Billing desk" maxLength={60} aria-label="New queue name" required />
          <button className="btn primary">Create queue</button>
          {err && <div className="error">{err}</div>}
        </form>
      </aside>

      <main className="main">
        {active ? (
          <>
            <div className="tabs" role="tablist">
              <button role="tab" aria-selected={tab === 'queue'} className={tab === 'queue' ? 'on' : ''} onClick={() => setTab('queue')}>Queue</button>
              <button role="tab" aria-selected={tab === 'dash'} className={tab === 'dash' ? 'on' : ''} onClick={() => setTab('dash')}>Dashboard</button>
            </div>
            {tab === 'queue'
              ? <QueueView key={active.id} queueId={active.id} onChanged={loadQueues} onDeleted={() => { loadQueues() }} />
              : <Dashboard key={active.id} queueId={active.id} queueName={active.name} />}
          </>
        ) : (
          <div className="empty big">
            <h2>Create a queue to get started</h2>
            <p className="muted">Each queue has a name, like “Billing desk” or “Walk-ins”. Add one from the panel on the left.</p>
          </div>
        )}
      </main>
    </div>
  )
}
