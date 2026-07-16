import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from './api'
import {
  Search, Cpu, BarChart3, ArrowRight, CheckCircle, XCircle,
  AlertCircle, ArrowLeftRight, Layers, Zap, Shield, Database,
  TrendingUp, RefreshCw, ExternalLink, ChevronDown, Network,
  Activity, Gauge, GitCompare
} from 'lucide-react'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, ScatterChart, Scatter, ZAxis,
  CartesianGrid, LineChart, Line, AreaChart, Area
} from 'recharts'

// ═══════════════════════════════════════════
// Types
// ═══════════════════════════════════════════
type Part = {
  mpn: string; manufacturer: string; description: string;
  category: string; package: string; stock: number;
  unit_price: number; lifecycle_status: string;
}
type PartDetail = Part & {
  subcategory: string; mounting_type: string;
  datasheet_url: string; product_url: string;
  specs: Record<string, string>;
}
type Alternative = PartDetail & {
  compatibility_pct: number; total_score: number;
  max_possible_score: number; is_drop_in: boolean;
  spec_scores: Record<string, {
    target: string; candidate: string; score: number;
    max: number; status: string; required: boolean;
  }>;
}
type Category = { slug: string; name: string; description: string; count: number }
type DashboardData = {
  total: number;
  categories: Record<string, number>;
  category_names: Record<string, string>;
  lifecycle_breakdown: Record<string, number>;
}

// ═══════════════════════════════════════════
// Theme
// ═══════════════════════════════════════════
const C = {
  bg: '#0A0E17', surface: '#111827', surfaceAlt: '#1E293B',
  border: '#1E293B', borderHover: '#334155',
  text: '#F1F5F9', muted: '#94A3B8', dim: '#64748B',
  primary: '#3B82F6', primaryGlow: '#3B82F620',
  accent: '#60A5FA', accentBright: '#93C5FD',
  success: '#22C55E', successDim: '#16A34A',
  warning: '#EAB308', warningDim: '#CA8A04',
  danger: '#EF4444', dangerDim: '#DC2626',
  purple: '#A78BFA', pink: '#F472B6', cyan: '#22D3EE',
  orange: '#FB923C',
}
const GRAD = ['#3B82F6','#6366F1','#8B5CF6','#A78BFA','#22C55E',
              '#14B8A6','#EAB308','#F97316','#EF4444','#EC4899']

// ═══════════════════════════════════════════
// Reusable Components
// ═══════════════════════════════════════════
function CompatRing({ pct, size = 56 }: { pct: number; size?: number }) {
  const color = pct >= 80 ? C.success : pct >= 50 ? C.warning : C.danger
  const r = (size - 6) / 2; const circ = 2 * Math.PI * r
  const offset = circ * (1 - pct / 100)
  return (
    <svg width={size} height={size} className="transform -rotate-90">
      <circle cx={size/2} cy={size/2} r={r} fill="none"
              stroke={C.border} strokeWidth={4} />
      <circle cx={size/2} cy={size/2} r={r} fill="none"
              stroke={color} strokeWidth={4}
              strokeDasharray={circ} strokeDashoffset={offset}
              strokeLinecap="round" className="transition-all duration-700" />
      <text x={size/2} y={size/2} textAnchor="middle" dominantBaseline="central"
            fill={color} fontSize={size * 0.22} fontWeight="bold"
            className="transform rotate-90" style={{ transformOrigin: 'center' }}>
        {pct.toFixed(0)}%
      </text>
    </svg>
  )
}

function LifecycleBadge({ status }: { status: string }) {
  const s = (status || '').toLowerCase()
  const [bg, fg] = s === 'active' ? ['#052E16', C.success]
    : s.includes('obsolete') ? ['#450A0A', C.danger]
    : s.includes('not for new') || s.includes('last time') ? ['#422006', C.warning]
    : [C.surfaceAlt, C.muted]
  return (
    <span className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold tracking-wide uppercase"
          style={{ backgroundColor: bg, color: fg }}>
      {status || 'Unknown'}
    </span>
  )
}

function StatusDot({ status }: { status: string }) {
  const color = status === 'MATCH' ? C.success : status === 'FAIL' ? C.danger : C.warning
  return <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
}

function GlowCard({ children, className = '', glow = false }: any) {
  return (
    <div className={`rounded-2xl border p-5 backdrop-blur-sm transition-all duration-300 ${className}`}
         style={{
           backgroundColor: C.surface,
           borderColor: glow ? C.primary + '40' : C.border,
           boxShadow: glow ? `0 0 20px ${C.primaryGlow}` : 'none',
         }}>
      {children}
    </div>
  )
}

function StatCard({ label, value, icon: Icon, color, trend }: any) {
  return (
    <GlowCard>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium tracking-wide uppercase" style={{ color: C.dim }}>{label}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          {trend && <p className="text-xs mt-1" style={{ color: C.success }}>
            <TrendingUp className="w-3 h-3 inline mr-1" />{trend}
          </p>}
        </div>
        <div className="w-12 h-12 rounded-xl flex items-center justify-center"
             style={{ backgroundColor: color + '15' }}>
          <Icon className="w-6 h-6" style={{ color }} />
        </div>
      </div>
    </GlowCard>
  )
}

// ═══════════════════════════════════════════
// MAIN APP
// ═══════════════════════════════════════════
export default function App() {
  const [page, setPage] = useState<'dashboard'|'search'|'alternatives'|'compare'|'browse'|'graph'>('dashboard')
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState<Part[]>([])
  const [selectedPart, setSelectedPart] = useState<PartDetail | null>(null)
  const [alternatives, setAlternatives] = useState<Alternative[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [topMfrs, setTopMfrs] = useState<{manufacturer: string; count: number}[]>([])
  const [loading, setLoading] = useState(false)
  const [cmpMpn1, setCmpMpn1] = useState('')
  const [cmpMpn2, setCmpMpn2] = useState('')
  const [cmpResult, setCmpResult] = useState<any>(null)
  const [browseCat, setBrowseCat] = useState('')
  const [browseParts, setBrowseParts] = useState<any[]>([])
  const [browseTotal, setBrowseTotal] = useState(0)
  const [minCompat, setMinCompat] = useState(30)
  const [expandedAlt, setExpandedAlt] = useState<number | null>(null)
  const [graphData, setGraphData] = useState<any>(null)

  useEffect(() => { loadDashboard() }, [])

  const loadDashboard = async () => {
    try {
      const [d, c, m] = await Promise.all([
        api.dashboard(), api.categories(), api.topManufacturers(),
      ])
      setDashboard(d.data); setCategories(c.data); setTopMfrs(m.data)
    } catch (e) { console.error(e) }
  }

  const search = async () => {
    if (!query.trim()) return
    setLoading(true)
    try {
      const r = await api.search(query, 30)
      setSearchResults(r.data); setPage('search')
    } catch (e) { console.error(e) }
    setLoading(false)
  }

  const selectPart = async (mpn: string) => {
    setLoading(true)
    try {
      const [p, a] = await Promise.all([
        api.lookup(mpn),
        api.alternatives(mpn, 15, minCompat),
      ])
      setSelectedPart(p.data); setAlternatives(a.data)
      setPage('alternatives'); setExpandedAlt(null)

      // Build graph data for network visualization
      const nodes = [{ id: mpn, group: 'target', val: 20 }]
      const links: any[] = []
      a.data.forEach((alt: Alternative) => {
        nodes.push({
          id: alt.mpn, group: alt.is_drop_in ? 'dropin' : 'alt',
          val: alt.compatibility_pct / 10,
        })
        links.push({
          source: mpn, target: alt.mpn,
          value: alt.compatibility_pct,
        })
      })
      setGraphData({ nodes, links })
    } catch (e) { console.error(e) }
    setLoading(false)
  }

  const runCompare = async () => {
    if (!cmpMpn1 || !cmpMpn2) return
    setLoading(true)
    try {
      const r = await api.compare(cmpMpn1, cmpMpn2)
      setCmpResult(r.data)
    } catch (e) { console.error(e) }
    setLoading(false)
  }

  const loadBrowse = async (cat: string) => {
    setBrowseCat(cat)
    try {
      const r = await api.browse(cat, 50)
      setBrowseParts(r.data.parts); setBrowseTotal(r.data.total); setPage('browse')
    } catch (e) { console.error(e) }
  }

  const ttStyle = { backgroundColor: C.surface, border: `1px solid ${C.border}`,
                     color: C.text, borderRadius: 12, fontSize: 12 }

  // ═══════════════════════════════════════════
  // RENDER
  // ═══════════════════════════════════════════
  return (
    <div className="min-h-screen" style={{ backgroundColor: C.bg, color: C.text }}>

      {/* ── HEADER ── */}
      <header className="border-b px-6 py-3 sticky top-0 z-50 backdrop-blur-xl"
              style={{ backgroundColor: C.bg + 'E0', borderColor: C.border }}>
        <div className="max-w-[1440px] mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center relative"
                 style={{ background: `linear-gradient(135deg, ${C.primary}, ${C.purple})` }}>
              <Cpu className="w-5 h-5 text-white" />
              <div className="absolute -top-0.5 -right-0.5 w-3 h-3 rounded-full animate-pulse"
                   style={{ backgroundColor: C.success }} />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight">IC Alternative Finder</h1>
              <p className="text-[10px] tracking-widest uppercase" style={{ color: C.dim }}>
                {dashboard ? `${dashboard.total.toLocaleString()} components · ${Object.keys(dashboard.categories).length} categories` : 'Loading...'}
              </p>
            </div>
          </div>
          <nav className="flex gap-1">
            {([
              ['dashboard', 'Dashboard', BarChart3],
              ['search', 'Search', Search],
              ['alternatives', 'Finder', Zap],
              ['compare', 'Compare', GitCompare],
              ['browse', 'Browse', Layers],
              ['graph', 'Graph', Network],
            ] as const).map(([id, label, Icon]) => (
              <button key={id} onClick={() => setPage(id as any)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all"
                style={{
                  backgroundColor: page === id ? C.primary : 'transparent',
                  color: page === id ? 'white' : C.muted,
                  boxShadow: page === id ? `0 0 15px ${C.primaryGlow}` : 'none',
                }}>
                <Icon className="w-3.5 h-3.5" /> {label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      {/* ── SEARCH BAR ── */}
      <div className="border-b px-6 py-3" style={{ borderColor: C.border }}>
        <div className="max-w-[1440px] mx-auto flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 w-4 h-4" style={{ color: C.dim }} />
            <input type="text" value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && search()}
              placeholder="Search by part number, keyword, or manufacturer..."
              className="w-full pl-9 pr-4 py-2 rounded-xl text-sm focus:outline-none focus:ring-2 transition-all"
              style={{ backgroundColor: C.surfaceAlt, border: `1px solid ${C.border}`,
                       color: C.text, '--tw-ring-color': C.primary } as any} />
          </div>
          <button onClick={search} disabled={loading}
            className="px-6 py-2 rounded-xl text-sm font-semibold text-white disabled:opacity-50 transition-all hover:shadow-lg"
            style={{ background: `linear-gradient(135deg, ${C.primary}, ${C.purple})`,
                     boxShadow: `0 4px 15px ${C.primaryGlow}` }}>
            {loading ? '...' : 'Search'}
          </button>
        </div>
      </div>

      <main className="max-w-[1440px] mx-auto px-6 py-6">

        {/* ════════════════════ DASHBOARD ════════════════════ */}
        {page === 'dashboard' && dashboard && (
          <div className="space-y-6">
            <div className="grid grid-cols-4 gap-4">
              <StatCard label="Total Components" value={dashboard.total.toLocaleString()} icon={Database} color={C.primary} />
              <StatCard label="Categories" value={Object.keys(dashboard.categories).length} icon={Layers} color={C.purple} />
              <StatCard label="Active Parts" value={(dashboard.lifecycle_breakdown['Active']||0).toLocaleString()} icon={CheckCircle} color={C.success} />
              <StatCard label="Manufacturers" value={topMfrs.length + '+'} icon={Activity} color={C.cyan} />
            </div>

            <div className="grid grid-cols-3 gap-6">
              {/* Category Bar Chart */}
              <GlowCard className="col-span-2">
                <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
                  <BarChart3 className="w-4 h-4" style={{ color: C.primary }} /> Parts by Category
                </h3>
                <ResponsiveContainer width="100%" height={350}>
                  <BarChart data={categories.filter(c => c.count > 0).sort((a, b) => b.count - a.count).slice(0, 14)}
                            layout="vertical" margin={{ left: 150 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                    <XAxis type="number" tick={{ fill: C.dim, fontSize: 10 }} />
                    <YAxis type="category" dataKey="name" tick={{ fill: C.muted, fontSize: 11 }} width={145} />
                    <Tooltip contentStyle={ttStyle} />
                    <Bar dataKey="count" radius={[0, 6, 6, 0]}>
                      {categories.filter(c => c.count > 0).sort((a, b) => b.count - a.count).slice(0, 14)
                        .map((_, i) => <Cell key={i} fill={GRAD[i % GRAD.length]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </GlowCard>

              {/* Lifecycle Donut */}
              <GlowCard>
                <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
                  <Gauge className="w-4 h-4" style={{ color: C.success }} /> Lifecycle Status
                </h3>
                <ResponsiveContainer width="100%" height={350}>
                  <PieChart>
                    <Pie data={Object.entries(dashboard.lifecycle_breakdown).map(([name, value]) => ({ name, value }))}
                         cx="50%" cy="45%" outerRadius={100} innerRadius={60}
                         dataKey="value" paddingAngle={3} strokeWidth={0}>
                      {Object.keys(dashboard.lifecycle_breakdown).map((_, i) => (
                        <Cell key={i} fill={GRAD[i % GRAD.length]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={ttStyle} />
                    <Legend wrapperStyle={{ fontSize: 10, color: C.muted }} />
                  </PieChart>
                </ResponsiveContainer>
              </GlowCard>
            </div>

            {/* Top Manufacturers */}
            <GlowCard>
              <h3 className="text-sm font-semibold mb-4">Top Manufacturers</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={topMfrs.slice(0, 10)} margin={{ bottom: 60 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                  <XAxis dataKey="manufacturer" tick={{ fill: C.muted, fontSize: 9 }} angle={-45} textAnchor="end" />
                  <YAxis tick={{ fill: C.dim, fontSize: 10 }} />
                  <Tooltip contentStyle={ttStyle} />
                  <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                    {topMfrs.slice(0, 10).map((_, i) => <Cell key={i} fill={GRAD[i % GRAD.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </GlowCard>

            {/* Category Grid */}
            <div className="grid grid-cols-4 gap-3">
              {categories.filter(c => c.count > 0).sort((a, b) => b.count - a.count).map((cat, i) => (
                <button key={cat.slug} onClick={() => loadBrowse(cat.slug)}
                  className="rounded-xl p-4 text-left border transition-all hover:scale-[1.02] hover:border-blue-500/50"
                  style={{ borderColor: C.border, backgroundColor: C.surfaceAlt }}>
                  <div className="w-2 h-2 rounded-full mb-2" style={{ backgroundColor: GRAD[i % GRAD.length] }} />
                  <div className="text-xs font-medium">{cat.name}</div>
                  <div className="text-lg font-bold mt-1" style={{ color: GRAD[i % GRAD.length] }}>
                    {cat.count.toLocaleString()}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ════════════════════ SEARCH ════════════════════ */}
        {page === 'search' && (
          <GlowCard>
            <div className="px-1 py-2 mb-3">
              <h2 className="font-semibold text-sm">{searchResults.length} results for "{query}"</h2>
            </div>
            {searchResults.length === 0 ? (
              <div className="p-8 text-center" style={{ color: C.muted }}>No results found.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr style={{ color: C.dim }} className="text-xs border-b" >
                    <th className="text-left px-3 py-2">MPN</th>
                    <th className="text-left px-3 py-2">Manufacturer</th>
                    <th className="text-left px-3 py-2">Category</th>
                    <th className="text-left px-3 py-2">Status</th>
                    <th className="text-right px-3 py-2">Stock</th>
                    <th className="text-right px-3 py-2">Price</th>
                    <th className="px-3 py-2"></th>
                  </tr></thead>
                  <tbody>
                    {searchResults.map(p => (
                      <tr key={p.mpn} className="border-b cursor-pointer transition-colors hover:bg-white/5"
                          style={{ borderColor: C.border }}
                          onClick={() => selectPart(p.mpn)}>
                        <td className="px-3 py-3 font-mono font-medium" style={{ color: C.accent }}>{p.mpn}</td>
                        <td className="px-3 py-3">{p.manufacturer}</td>
                        <td className="px-3 py-3" style={{ color: C.muted }}>{p.category}</td>
                        <td className="px-3 py-3"><LifecycleBadge status={p.lifecycle_status} /></td>
                        <td className="px-3 py-3 text-right font-mono" style={{ color: C.success }}>{p.stock.toLocaleString()}</td>
                        <td className="px-3 py-3 text-right font-mono">${p.unit_price.toFixed(4)}</td>
                        <td className="px-3 py-3"><ArrowRight className="w-4 h-4" style={{ color: C.dim }} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </GlowCard>
        )}

        {/* ════════════════════ ALTERNATIVES ════════════════════ */}
        {page === 'alternatives' && selectedPart && (
          <div className="space-y-5">
            {/* Target Part */}
            <GlowCard glow>
              <div className="flex justify-between items-start">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Cpu className="w-5 h-5" style={{ color: C.primary }} />
                    <h2 className="text-xl font-bold font-mono" style={{ color: C.accent }}>{selectedPart.mpn}</h2>
                  </div>
                  <p className="text-sm" style={{ color: C.muted }}>{selectedPart.description}</p>
                  <p className="text-xs mt-1" style={{ color: C.dim }}>
                    {selectedPart.manufacturer} · {selectedPart.category} · {selectedPart.package}
                  </p>
                </div>
                <LifecycleBadge status={selectedPart.lifecycle_status} />
              </div>
              {Object.keys(selectedPart.specs).length > 0 && (
                <div className="mt-4 grid grid-cols-4 gap-2">
                  {Object.entries(selectedPart.specs).sort().slice(0, 12).map(([k, v]) => (
                    <div key={k} className="rounded-lg px-3 py-2" style={{ backgroundColor: C.bg }}>
                      <div className="text-[10px] uppercase tracking-wider" style={{ color: C.dim }}>{k}</div>
                      <div className="text-xs font-medium mt-0.5">{v}</div>
                    </div>
                  ))}
                </div>
              )}
            </GlowCard>

            {/* Scatter + Controls */}
            {alternatives.length > 2 && (
              <GlowCard>
                <h4 className="text-xs font-semibold mb-3" style={{ color: C.dim }}>
                  Compatibility Landscape — {alternatives.length} alternatives
                </h4>
                <ResponsiveContainer width="100%" height={200}>
                  <ScatterChart margin={{ left: 10, right: 10, top: 10, bottom: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                    <XAxis type="number" dataKey="idx" name="Rank" tick={{ fill: C.dim, fontSize: 10 }} />
                    <YAxis type="number" dataKey="pct" name="Compat" domain={[0, 100]} tick={{ fill: C.dim, fontSize: 10 }} />
                    <ZAxis range={[40, 200]} />
                    <Tooltip contentStyle={ttStyle}
                             formatter={(v: any, name: string) => [name === 'pct' ? `${v}%` : v, name === 'pct' ? 'Compatibility' : 'Rank']} />
                    <Scatter data={alternatives.map((a, i) => ({ idx: i + 1, pct: Math.round(a.compatibility_pct), name: a.mpn }))}>
                      {alternatives.map((a, i) => (
                        <Cell key={i} fill={a.compatibility_pct >= 80 ? C.success : a.compatibility_pct >= 50 ? C.warning : C.danger} />
                      ))}
                    </Scatter>
                  </ScatterChart>
                </ResponsiveContainer>
              </GlowCard>
            )}

            {/* Alternatives List */}
            {alternatives.map((alt, idx) => (
              <GlowCard key={alt.mpn}
                        className={expandedAlt === idx ? 'ring-1 ring-blue-500/30' : ''}>
                <div className="flex items-start gap-4 cursor-pointer" onClick={() => setExpandedAlt(expandedAlt === idx ? null : idx)}>
                  <CompatRing pct={alt.compatibility_pct} />
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-sm font-bold" style={{ color: C.dim }}>#{idx + 1}</span>
                      <span className="font-mono font-bold text-sm" style={{ color: C.accent }}>{alt.mpn}</span>
                      {alt.is_drop_in && (
                        <span className="px-2 py-0.5 text-[10px] font-bold rounded-full tracking-wider uppercase"
                              style={{ backgroundColor: '#052E16', color: C.success }}>Drop-In</span>
                      )}
                    </div>
                    <p className="text-xs" style={{ color: C.muted }}>{alt.description}</p>
                    <p className="text-[11px] mt-0.5" style={{ color: C.dim }}>{alt.manufacturer}</p>
                  </div>
                  <div className="text-right text-xs space-y-1">
                    <LifecycleBadge status={alt.lifecycle_status} />
                    <div className="mt-1" style={{ color: C.dim }}>{alt.package}</div>
                  </div>
                  <ChevronDown className={`w-4 h-4 transition-transform ${expandedAlt === idx ? 'rotate-180' : ''}`}
                               style={{ color: C.dim }} />
                </div>

                {expandedAlt === idx && Object.keys(alt.spec_scores).length > 0 && (
                  <div className="mt-4 flex gap-6">
                    {/* Spec Table */}
                    <div className="flex-1">
                      <table className="w-full text-xs">
                        <thead><tr style={{ color: C.dim }}>
                          <th className="text-left py-1 font-normal">Spec</th>
                          <th className="text-left py-1 font-normal">Target</th>
                          <th className="text-left py-1 font-normal">Candidate</th>
                          <th className="text-center py-1 font-normal">Match</th>
                          <th className="text-right py-1 font-normal">Score</th>
                        </tr></thead>
                        <tbody>
                          {Object.entries(alt.spec_scores).sort().map(([name, d]) => (
                            <tr key={name} className="border-t" style={{ borderColor: C.border }}>
                              <td className="py-1.5">
                                {d.required && <span style={{ color: C.danger }}>* </span>}{name}
                              </td>
                              <td className="py-1.5 font-mono" style={{ color: C.dim }}>{d.target}</td>
                              <td className="py-1.5 font-mono" style={{ color: C.dim }}>{d.candidate}</td>
                              <td className="py-1.5 text-center"><StatusDot status={d.status} /></td>
                              <td className="py-1.5 text-right font-mono" style={{ color: C.dim }}>
                                {d.score.toFixed(0)}/{d.max.toFixed(0)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {/* Radar Chart */}
                    {Object.keys(alt.spec_scores).length > 2 && (
                      <div className="w-72 flex-shrink-0">
                        <ResponsiveContainer width="100%" height={240}>
                          <RadarChart data={Object.entries(alt.spec_scores).map(([name, d]) => ({
                            spec: name.length > 14 ? name.slice(0, 14) + '…' : name,
                            score: d.max > 0 ? (d.score / d.max) * 100 : 0,
                          }))}>
                            <PolarGrid stroke={C.border} />
                            <PolarAngleAxis dataKey="spec" tick={{ fill: C.dim, fontSize: 9 }} />
                            <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                            <Radar dataKey="score" stroke={C.primary} fill={C.primary} fillOpacity={0.25} strokeWidth={2} />
                          </RadarChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                  </div>
                )}
              </GlowCard>
            ))}
          </div>
        )}

        {/* ════════════════════ COMPARE ════════════════════ */}
        {page === 'compare' && (
          <div className="space-y-5">
            <GlowCard>
              <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
                <GitCompare className="w-4 h-4" style={{ color: C.primary }} /> Side-by-Side Comparison
              </h3>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <input value={cmpMpn1} onChange={e => setCmpMpn1(e.target.value)}
                  placeholder="Part 1 (e.g. MIC5501-3.0YM5-TR)"
                  className="px-3 py-2 rounded-xl text-sm focus:outline-none focus:ring-2"
                  style={{ backgroundColor: C.surfaceAlt, border: `1px solid ${C.border}`, color: C.text } as any} />
                <input value={cmpMpn2} onChange={e => setCmpMpn2(e.target.value)}
                  placeholder="Part 2 (e.g. AP2112K-3.3TRG1)"
                  className="px-3 py-2 rounded-xl text-sm focus:outline-none focus:ring-2"
                  style={{ backgroundColor: C.surfaceAlt, border: `1px solid ${C.border}`, color: C.text } as any} />
              </div>
              <button onClick={runCompare} disabled={loading || !cmpMpn1 || !cmpMpn2}
                className="px-6 py-2 rounded-xl text-sm font-semibold text-white disabled:opacity-50"
                style={{ background: `linear-gradient(135deg, ${C.primary}, ${C.purple})` }}>
                Compare
              </button>
            </GlowCard>

            {cmpResult && (
              <GlowCard>
                <table className="w-full text-sm">
                  <thead><tr className="border-b" style={{ borderColor: C.border, color: C.dim }}>
                    <th className="text-left px-3 py-2 text-xs font-normal">Parameter</th>
                    <th className="text-left px-3 py-2 text-xs font-mono" style={{ color: C.accent }}>{cmpResult.part_a.mpn}</th>
                    <th className="text-left px-3 py-2 text-xs font-mono" style={{ color: C.purple }}>{cmpResult.part_b.mpn}</th>
                    <th className="text-center px-3 py-2 text-xs font-normal">Match</th>
                  </tr></thead>
                  <tbody>
                    {['manufacturer','category','package','mounting_type','lifecycle_status'].map(field => {
                      const va = cmpResult.part_a[field] || '-'
                      const vb = cmpResult.part_b[field] || '-'
                      const match = va.toLowerCase() === vb.toLowerCase()
                      return (
                        <tr key={field} className="border-b" style={{ borderColor: C.border }}>
                          <td className="px-3 py-2 capitalize" style={{ color: C.dim }}>{field.replace('_', ' ')}</td>
                          <td className="px-3 py-2">{va}</td>
                          <td className="px-3 py-2">{vb}</td>
                          <td className="px-3 py-2 text-center">
                            {match ? <CheckCircle className="w-4 h-4 inline" style={{ color: C.success }} />
                                   : <XCircle className="w-4 h-4 inline" style={{ color: C.danger }} />}
                          </td>
                        </tr>
                      )
                    })}
                    <tr><td colSpan={4} className="px-3 py-1 text-[10px] font-semibold uppercase tracking-widest border-t"
                            style={{ borderColor: C.border, color: C.dim }}>Specifications</td></tr>
                    {cmpResult.all_spec_names.map((spec: string) => {
                      const va = cmpResult.part_a.specs[spec] || '-'
                      const vb = cmpResult.part_b.specs[spec] || '-'
                      const match = va.toLowerCase() === vb.toLowerCase()
                      return (
                        <tr key={spec} className="border-b" style={{ borderColor: C.border }}>
                          <td className="px-3 py-2 text-xs" style={{ color: C.dim }}>{spec}</td>
                          <td className="px-3 py-2 text-xs font-mono">{va}</td>
                          <td className="px-3 py-2 text-xs font-mono">{vb}</td>
                          <td className="px-3 py-2 text-center">
                            {match ? <CheckCircle className="w-4 h-4 inline" style={{ color: C.success }} />
                                   : <AlertCircle className="w-4 h-4 inline" style={{ color: C.warning }} />}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </GlowCard>
            )}
          </div>
        )}

        {/* ════════════════════ BROWSE ════════════════════ */}
        {page === 'browse' && (
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              <select value={browseCat} onChange={e => loadBrowse(e.target.value)}
                className="px-3 py-2 rounded-xl text-sm"
                style={{ backgroundColor: C.surfaceAlt, border: `1px solid ${C.border}`, color: C.text }}>
                <option value="">Select Category</option>
                {categories.filter(c => c.count > 0).map(c => (
                  <option key={c.slug} value={c.slug}>{c.name} ({c.count})</option>
                ))}
              </select>
              <span className="text-xs" style={{ color: C.dim }}>
                {browseTotal > 0 ? `${browseTotal.toLocaleString()} parts` : ''}
              </span>
            </div>
            {browseParts.length > 0 && (
              <GlowCard>
                <table className="w-full text-sm">
                  <thead><tr className="border-b text-xs" style={{ borderColor: C.border, color: C.dim }}>
                    <th className="text-left px-3 py-2">MPN</th>
                    <th className="text-left px-3 py-2">Manufacturer</th>
                    <th className="text-left px-3 py-2">Description</th>
                    <th className="text-left px-3 py-2">Status</th>
                    <th className="text-right px-3 py-2">Stock</th>
                  </tr></thead>
                  <tbody>
                    {browseParts.map((p: any) => (
                      <tr key={p.manufacturer_part_number}
                          className="border-b cursor-pointer transition-colors hover:bg-white/5"
                          style={{ borderColor: C.border }}
                          onClick={() => selectPart(p.manufacturer_part_number)}>
                        <td className="px-3 py-2 font-mono text-xs" style={{ color: C.accent }}>{p.manufacturer_part_number}</td>
                        <td className="px-3 py-2 text-xs">{p.manufacturer}</td>
                        <td className="px-3 py-2 text-xs truncate max-w-xs" style={{ color: C.muted }}>{p.description}</td>
                        <td className="px-3 py-2"><LifecycleBadge status={p.lifecycle_status} /></td>
                        <td className="px-3 py-2 text-right text-xs font-mono" style={{ color: C.success }}>{(p.stock||0).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </GlowCard>
            )}
          </div>
        )}

        {/* ════════════════════ NETWORK GRAPH ════════════════════ */}
        {page === 'graph' && (
          <div className="space-y-4">
            <GlowCard glow>
              <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
                <Network className="w-4 h-4" style={{ color: C.cyan }} />
                Compatibility Network Graph
              </h3>
              <p className="text-xs mb-4" style={{ color: C.dim }}>
                Search for a part above to visualize its compatibility network.
                {graphData ? ` Showing ${graphData.nodes.length} nodes.` : ' No data yet.'}
              </p>
              {graphData ? (
                <div className="rounded-xl overflow-hidden border" style={{ borderColor: C.border, height: 500 }}>
                  <ForceGraph graphData={graphData} />
                </div>
              ) : (
                <div className="h-64 flex items-center justify-center rounded-xl"
                     style={{ backgroundColor: C.bg }}>
                  <p style={{ color: C.dim }}>Search for a part and find alternatives to see the network graph.</p>
                </div>
              )}
            </GlowCard>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t px-6 py-4 mt-8" style={{ borderColor: C.border }}>
        <div className="max-w-[1440px] mx-auto flex justify-between items-center">
          <span className="text-[10px] tracking-widest uppercase" style={{ color: C.dim }}>
            IC Alternative Finder · {dashboard?.total.toLocaleString() || '...'} components
          </span>
          <span className="text-[10px]" style={{ color: C.dim }}>
            {Object.keys(dashboard?.categories || {}).length} categories
          </span>
        </div>
      </footer>
    </div>
  )
}

// ═══════════════════════════════════════════
// FORCE GRAPH COMPONENT
// ═══════════════════════════════════════════
function ForceGraph({ graphData }: { graphData: any }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [dimensions, setDimensions] = useState({ width: 800, height: 500 })

  useEffect(() => {
    if (containerRef.current) {
      setDimensions({
        width: containerRef.current.clientWidth,
        height: 500,
      })
    }
  }, [])

  // Simple canvas-based force graph
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const nodesRef = useRef<any[]>([])
  const linksRef = useRef<any[]>([])
  const animRef = useRef<number>(0)

  useEffect(() => {
    if (!graphData || !canvasRef.current) return

    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const W = dimensions.width
    const H = dimensions.height
    canvas.width = W * 2; canvas.height = H * 2
    canvas.style.width = W + 'px'; canvas.style.height = H + 'px'
    ctx.scale(2, 2)

    // Initialize node positions
    const nodes = graphData.nodes.map((n: any, i: number) => ({
      ...n,
      x: W / 2 + Math.cos(i * 0.5) * (100 + Math.random() * 100),
      y: H / 2 + Math.sin(i * 0.5) * (100 + Math.random() * 100),
      vx: 0, vy: 0,
    }))
    const links = graphData.links.map((l: any) => ({
      ...l,
      sourceIdx: nodes.findIndex((n: any) => n.id === l.source),
      targetIdx: nodes.findIndex((n: any) => n.id === l.target),
    }))

    nodesRef.current = nodes
    linksRef.current = links

    const C_BG = '#0A0E17'
    const C_PRIMARY = '#3B82F6'
    const C_SUCCESS = '#22C55E'
    const C_WARNING = '#EAB308'
    const C_DANGER = '#EF4444'
    const C_CYAN = '#22D3EE'
    const C_LINE = '#1E293B'

    function simulate() {
      // Simple force simulation
      for (const link of links) {
        if (link.sourceIdx < 0 || link.targetIdx < 0) continue
        const s = nodes[link.sourceIdx]
        const t = nodes[link.targetIdx]
        const dx = t.x - s.x; const dy = t.y - s.y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const targetDist = 150 - (link.value || 50) * 0.5
        const force = (dist - targetDist) * 0.003
        const fx = dx / dist * force; const fy = dy / dist * force
        s.vx += fx; s.vy += fy; t.vx -= fx; t.vy -= fy
      }

      // Repulsion
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[j].x - nodes[i].x
          const dy = nodes[j].y - nodes[i].y
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          if (dist < 200) {
            const force = (200 - dist) * 0.01
            const fx = dx / dist * force; const fy = dy / dist * force
            nodes[i].vx -= fx; nodes[i].vy -= fy
            nodes[j].vx += fx; nodes[j].vy += fy
          }
        }
        // Center gravity
        nodes[i].vx += (W / 2 - nodes[i].x) * 0.0005
        nodes[i].vy += (H / 2 - nodes[i].y) * 0.0005
        // Damping
        nodes[i].vx *= 0.9; nodes[i].vy *= 0.9
        nodes[i].x += nodes[i].vx; nodes[i].y += nodes[i].vy
        // Bounds
        nodes[i].x = Math.max(30, Math.min(W - 30, nodes[i].x))
        nodes[i].y = Math.max(30, Math.min(H - 30, nodes[i].y))
      }
    }

    function draw() {
      simulate()
      ctx.fillStyle = C_BG
      ctx.fillRect(0, 0, W, H)

      // Draw links
      for (const link of links) {
        if (link.sourceIdx < 0 || link.targetIdx < 0) continue
        const s = nodes[link.sourceIdx]; const t = nodes[link.targetIdx]
        const compat = link.value || 50
        const color = compat >= 80 ? C_SUCCESS : compat >= 50 ? C_WARNING : C_DANGER
        ctx.strokeStyle = color + '40'
        ctx.lineWidth = Math.max(1, compat / 30)
        ctx.beginPath(); ctx.moveTo(s.x, s.y); ctx.lineTo(t.x, t.y); ctx.stroke()

        // Draw compatibility label on link
        const mx = (s.x + t.x) / 2; const my = (s.y + t.y) / 2
        ctx.fillStyle = color + '90'
        ctx.font = '9px sans-serif'; ctx.textAlign = 'center'
        ctx.fillText(`${compat.toFixed(0)}%`, mx, my - 4)
      }

      // Draw nodes
      for (const node of nodes) {
        const isTarget = node.group === 'target'
        const isDropin = node.group === 'dropin'
        const r = isTarget ? 18 : isDropin ? 12 : 9
        const color = isTarget ? C_CYAN : isDropin ? C_SUCCESS : C_PRIMARY

        // Glow
        if (isTarget || isDropin) {
          ctx.beginPath(); ctx.arc(node.x, node.y, r + 6, 0, Math.PI * 2)
          ctx.fillStyle = color + '15'; ctx.fill()
        }

        // Circle
        ctx.beginPath(); ctx.arc(node.x, node.y, r, 0, Math.PI * 2)
        ctx.fillStyle = color + '30'; ctx.fill()
        ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.stroke()

        // Label
        ctx.fillStyle = '#F1F5F9'
        ctx.font = `${isTarget ? 'bold 11' : '9'}px monospace`
        ctx.textAlign = 'center'
        const label = node.id.length > 18 ? node.id.slice(0, 18) + '…' : node.id
        ctx.fillText(label, node.x, node.y + r + 14)
      }

      animRef.current = requestAnimationFrame(draw)
    }

    draw()
    return () => cancelAnimationFrame(animRef.current)
  }, [graphData, dimensions])

  return (
    <div ref={containerRef} style={{ width: '100%', height: 500 }}>
      <canvas ref={canvasRef} style={{ display: 'block' }} />
    </div>
  )
}