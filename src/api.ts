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