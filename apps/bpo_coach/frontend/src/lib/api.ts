export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message) }
}

export async function api(method: string, data: Record<string, unknown> = {}) {
  let body: BodyInit
  const headers: Record<string, string> = {'X-Frappe-CSRF-Token': (window as any).bpoCoachBoot?.csrf_token || ''}
  if (data instanceof FormData) body = data
  else { headers['Content-Type'] = 'application/json'; body = JSON.stringify(data) }
  const response = await fetch('/api/method/bpo_coach.api.' + method, {method: 'POST', headers, body, credentials: 'same-origin'})
  if (response.status === 401 || response.status === 403) {
    if (response.status === 401) window.location.assign('/login?redirect-to=' + encodeURIComponent(location.pathname + location.search))
  }
  const result = await response.json()
  if (!response.ok || result.exc) {
    let message = 'The request could not be completed. Your saved progress is preserved.'
    try { const messages = JSON.parse(result._server_messages); message = JSON.parse(messages[0]).message } catch {}
    const clean = new DOMParser().parseFromString(message, 'text/html').body.textContent || message
    throw new ApiError(clean, response.status)
  }
  return result.message
}

export const requestId = () => crypto.randomUUID()
export const parse = (value: any, fallback: any = []) => typeof value === 'string' ? JSON.parse(value) : value || fallback

export async function screenshotUrl(name: string) { return (await api('asset', {name})).url }

export function rememberRequest(key: string, payload: Record<string, unknown>) {
  const serialized = JSON.stringify(payload)
  const existing = sessionStorage.getItem(key)
  if (existing) {
    const saved = JSON.parse(existing)
    if (saved.serialized === serialized) return saved.id
  }
  const id = requestId()
  sessionStorage.setItem(key, JSON.stringify({serialized, id}))
  return id
}
