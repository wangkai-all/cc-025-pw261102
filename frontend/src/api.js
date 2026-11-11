const BASE = '/api'

async function req(path, options) {
  const res = await fetch(BASE + path, options)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `${res.status} ${res.statusText}`)
  }
  return res.json()
}

export const api = {
  meta: () => req('/meta'),
  summary: (model, days) => req(`/summary?model=${model}&lookback_days=${days}`),
  conversions: (model, days) => req(`/conversions?model=${model}&lookback_days=${days}`),
  detail: (orderId, model, days) => req(`/conversions/${orderId}?model=${model}&lookback_days=${days}`),
  compare: (days) => req(`/compare?lookback_days=${days}`),
  importData: (entity, rows) =>
    req(`/import/${entity}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(rows),
    }),
  seed: () => req('/seed', { method: 'POST' }),
  reset: () => req('/reset', { method: 'POST' }),
}
