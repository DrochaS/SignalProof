const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  })

  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    const message = data?.error || data?.message || 'Request failed'
    throw new Error(message)
  }

  return data
}

export async function fetchDeliveries() {
  const payload = await request('/api/deliveries')
  return Array.isArray(payload?.deliveries) ? payload.deliveries : []
}

export async function createDelivery(delivery) {
  const payload = await request('/api/deliveries', {
    method: 'POST',
    body: JSON.stringify(delivery),
  })

  return payload?.delivery || null
}
