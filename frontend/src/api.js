const KEY = 'lineup_token'
export const auth = {
  get: () => localStorage.getItem(KEY),
  set: (t) => localStorage.setItem(KEY, t),
  clear: () => localStorage.removeItem(KEY),
}

export async function api(path, { method = 'GET', body } = {}) {
  const token = auth.get()
  const res = await fetch('/api' + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (res.status === 401 && token) {
    auth.clear()
    window.dispatchEvent(new Event('lineup:logout'))
  }
  const data = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) {
    const d = data?.detail
    throw new Error(typeof d === 'string' ? d : Array.isArray(d) ? d.map((e) => e.msg.replace('Value error, ', '')).join(', ') : 'Something went wrong')
  }
  return data
}
