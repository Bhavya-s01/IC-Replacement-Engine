import axios from 'axios'

const API = axios.create({ baseURL: 'http://localhost:8000/api' })

export const api = {
  dashboard: () => API.get('/dashboard'),
  categories: () => API.get('/categories'),
  search: (q: string, limit = 30) =>
    API.get('/search', { params: { q, limit } }),
  lookup: (mpn: string) =>
    API.get(`/lookup/${encodeURIComponent(mpn)}`),
  alternatives: (mpn: string, topN = 15, minCompat = 25) =>
    API.get(`/alternatives/${encodeURIComponent(mpn)}`, {
      params: { top_n: topN, min_compat: minCompat },
    }),
  compare: (mpn1: string, mpn2: string) =>
    API.get('/compare', { params: { mpn1, mpn2 } }),
  browse: (category: string, limit = 50, offset = 0) =>
    API.get('/browse', { params: { category, limit, offset } }),
  topManufacturers: (limit = 10) =>
    API.get('/top-manufacturers', { params: { limit } }),
  lifecycleSummary: () =>
    API.get('/lifecycle-summary'),
  stats: () =>
    API.get('/stats'),
  matchingRules: () =>
    API.get('/matching-rules'),
  supplyChainStats: () =>
    API.get('/supply-chain-stats'),
  supplyChain: (mpn: string) =>
    API.get(`/supply-chain/${encodeURIComponent(mpn)}`),
  alternativesFull: (mpn: string, topN = 15, minCompat = 25) =>
    API.get(`/alternatives-full/${encodeURIComponent(mpn)}`, {
      params: { top_n: topN, min_compat: minCompat },
    }),
}

const ADMIN_TOKEN_KEY = 'adminToken'
export const getAdminToken = () => localStorage.getItem(ADMIN_TOKEN_KEY) ?? ''
export const setAdminToken = (t: string) => localStorage.setItem(ADMIN_TOKEN_KEY, t)

const ADMIN = axios.create({ baseURL: 'http://localhost:8000/api/admin' })
ADMIN.interceptors.request.use(cfg => {
  const token = getAdminToken()
  if (token) cfg.headers['X-Admin-Token'] = token
  return cfg
})

export const adminApi = {
  tasks: () => ADMIN.get('/tasks'),
  overview: () => ADMIN.get('/overview'),
  uploadMpns: (form: FormData) => ADMIN.post('/upload/mpns', form),
  uploadSupplyChain: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return ADMIN.post('/upload/supply-chain', form)
  },
  jobs: () => ADMIN.get('/jobs'),
  job: (id: string, offset = 0) => ADMIN.get(`/jobs/${id}`, { params: { offset } }),
  startJob: (task: string, params: Record<string, unknown>) =>
    ADMIN.post('/jobs', { task, params }),
  cancelJob: (id: string) => ADMIN.post(`/jobs/${id}/cancel`),
}
