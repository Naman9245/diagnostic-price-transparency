// Talks to the FastAPI backend in prototype/backend.
// Point it somewhere else with VITE_API_URL=http://host:port npm run dev
const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(BASE + path, options)
  } catch {
    throw new Error(`Can't reach the API at ${BASE}. Start the backend, then reload this page.`)
  }
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    // FastAPI puts the reason in `detail`: a sentence, or a list of validation errors.
    const detail = Array.isArray(body?.detail) ? body.detail.map((d) => d.msg).join(' ') : body?.detail
    throw new Error(detail || `The API returned an error (${response.status}).`)
  }
  return body
}

const patch = (path, body) =>
  request(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const api = {
  tests: () => request('/tests'),

  hospitals: () => request('/hospitals'),

  doctors: () => request('/doctors'),

  specialties: () => request('/specialties'),

  /** Sets prices for one hospital: { testId: rupees }. `source` says where they came from. */
  updatePrices: (hospitalId, prices, source) =>
    patch(`/hospitals/${hospitalId}/prices`, source ? { prices, source } : { prices }),

  /** Sets one doctor's consultation fee, in rupees. */
  updateFee: (doctorId, fee) => patch(`/doctors/${doctorId}/fee`, { fee }),

  /** Uploads a rate card and gets back the rows read from it, each matched to a test. */
  extractSheet: (hospitalId, file) => {
    const form = new FormData()
    form.append('hospital_id', hospitalId)
    form.append('file', file)
    return request('/price-sheets/extract', { method: 'POST', body: form })
  },
}
