import { useState } from 'react'
import { api, auth } from './api'

export default function Login({ onAuthed }) {
  const [mode, setMode] = useState('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setErr('')
    try {
      const r = await api(mode === 'login' ? '/auth/login' : '/auth/register', { method: 'POST', body: { username, password } })
      auth.set(r.token)
      onAuthed(r.user)
    } catch (x) {
      setErr(x.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login">
      <aside className="login-board" aria-hidden="true">
        <div className="brand brand-lg">Lineup</div>
        <div className="board-demo">
          <span className="board-label">Now serving</span>
          <span className="board-num">T-042</span>
          <span className="board-next">Next: T-043, T-044, T-045</span>
        </div>
      </aside>
      <main className="login-form">
        <form onSubmit={submit}>
          <h1>{mode === 'login' ? 'Sign in to your queues' : 'Create a manager account'}</h1>
          <p className="muted">Create queues, issue tokens and call the next person in line.</p>
          <label>Username
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required minLength={3} autoFocus />
          </label>
          <label>Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required minLength={6} />
          </label>
          {err && <div className="error" role="alert">{err}</div>}
          <button className="btn primary wide" disabled={busy}>{busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}</button>
          <button type="button" className="link" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setErr('') }}>
            {mode === 'login' ? 'New manager? Create an account' : 'Already have an account? Sign in'}
          </button>
        </form>
      </main>
    </div>
  )
}
