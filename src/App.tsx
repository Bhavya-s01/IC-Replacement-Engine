import { useState, useEffect } from 'react'
import { api } from './api'
import {
  Search, Cpu, BarChart3, ArrowRight, CheckCircle, XCircle,
  AlertCircle, ArrowLeftRight, Layers, Zap, Database,
  TrendingUp, RefreshCw, ExternalLink, ChevronDown, Home,
  FileText, Wrench, ChevronRight, Info, Box, Activity,
  Shield, GitCompare, Award, Target
} from 'lucide-react'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, ScatterChart, Scatter, ZAxis,
  CartesianGrid, Treemap
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
// Design Tokens
// ═══════════════════════════════════════════
const DELL_BLUE = '#0076CE'
const DELL_DARK = '#00447C'

const T = {
  bg: '#FFFFFF',
  bgAlt: '#F8FAFC',
  surface: '#FFFFFF',
  surfaceMuted: '#F1F5F9',
  border: '#E2E8F0',
  borderHover: '#CBD5E1',
  text: '#0F172A',
  textSecondary: '#475569',
  textMuted: '#94A3B8',
  primary: DELL_BLUE,
  primaryDark: DELL_DARK,
  primaryLight: '#E0F2FE',
  success: '#16A34A',
  successBg: '#F0FDF4',
  warning: '#CA8A04',
  warningBg: '#FEFCE8',
  danger: '#DC2626',
  dangerBg: '#FEF2F2',
  accent: '#0284C7',
}

const CHART_COLORS = [
  '#0076CE', '#00447C', '#0284C7', '#0EA5E9', '#38BDF8',
  '#7DD3FC', '#06B6D4', '#14B8A6', '#10B981', '#22C55E'
]

// ═══════════════════════════════════════════
// Shared Components
// ═══════════════════════════════════════════
function CompatBadge({ pct }: { pct: number }) {
  const color = pct >= 80 ? T.success : pct >= 50 ? T.warning : T.danger
  const bg = pct >= 80 ? T.successBg : pct >= 50 ? T.warningBg : T.dangerBg
  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold"
          style={{ backgroundColor: bg, color }}>
      {pct.toFixed(0)}%
    </span>
  )
}

function LifecycleBadge({ status }: { status: string }) {
  const s = (status || '').toLowerCase()
  const [bg, fg] = s === 'active' ? [T.successBg, T.success]
    : s.includes('obsolete') ? [T.dangerBg, T.danger]
    : s.includes('not for new') || s.includes('last time') ? [T.warningBg, T.warning]
    : [T.surfaceMuted, T.textMuted]
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium"
          style={{ backgroundColor: bg, color: fg }}>
      {status || 'Unknown'}
    </span>
  )
}

function StatusDot({ status }: { status: string }) {
  const color = status === 'MATCH' ? T.success : status === 'FAIL' ? T.danger : T.warning
  return <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
}

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-white rounded-xl border border-slate-200 ${className}`}
         style={{ boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.04), 0 1px 2px -1px rgb(0 0 0 / 0.04)' }}>
      {children}
    </div>
  )
}

function KpiCard({ label, value, icon: Icon, trend }: {
  label: string; value: string | number; icon: any; trend?: string
}) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[13px] font-medium text-slate-500">{label}</p>
          <p className="text-2xl font-semibold text-slate-900 mt-1">{value}</p>
          {trend && (
            <p className="text-xs text-emerald-600 mt-1.5 flex items-center gap-1">
              <TrendingUp className="w-3 h-3" />{trend}
            </p>
          )}
        </div>
        <div className="w-10 h-10 rounded-lg flex items-center justify-center"
             style={{ backgroundColor: T.primaryLight }}>
          <Icon className="w-5 h-5" style={{ color: T.primary }} />
        </div>
      </div>
    </Card>
  )
}

function SectionHeader({ icon: Icon, title, subtitle }: {
  icon: any; title: string; subtitle?: string
}) {
  return (
    <div className="flex items-center gap-3 mb-6">
      <div className="w-9 h-9 rounded-lg flex items-center justify-center"
           style={{ backgroundColor: T.primaryLight }}>
        <Icon className="w-4.5 h-4.5" style={{ color: T.primary }} />
      </div>
      <div>
        <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
        {subtitle && <p className="text-sm text-slate-500">{subtitle}</p>}
      </div>
    </div>
  )
}

const tooltipStyle = {
  backgroundColor: '#fff',
  border: '1px solid #E2E8F0',
  borderRadius: 8,
  fontSize: 12,
  boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.05)',
}

// ═══════════════════════════════════════════
// MAIN APP
// ═══════════════════════════════════════════
export default function App() {
  type Page = 'home' | 'dashboard' | 'browse' | 'search' | 'alternatives' | 'compare'
  const [page, setPage] = useState<Page>('home')
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState<Part[]>([])
  const [selectedPart, setSelectedPart] = useState<PartDetail | null>(null)
  const [alternatives, setAlternatives] = useState<Alternative[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [topMfrs, setTopMfrs] = useState<{ manufacturer: string; count: number }[]>([])
  const [loading, setLoading] = useState(false)
  const [cmpMpn1, setCmpMpn1] = useState('')
  const [cmpMpn2, setCmpMpn2] = useState('')
  const [cmpResult, setCmpResult] = useState<any>(null)
  const [browseCat, setBrowseCat] = useState('')
  const [browseParts, setBrowseParts] = useState<any[]>([])
  const [browseTotal, setBrowseTotal] = useState(0)
  const [minCompat, setMinCompat] = useState(30)
  const [expandedAlt, setExpandedAlt] = useState<number | null>(null)

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

  // Active section
  const section = ['home'].includes(page) ? 'home'
    : ['dashboard', 'browse'].includes(page) ? 'data'
    : 'finder'

  // ═══════════════════════════════════════════
  // RENDER
  // ═══════════════════════════════════════════
  return (
    <div className="min-h-screen" style={{ backgroundColor: T.bgAlt, color: T.text }}>

      {/* ── TOP NAVIGATION ── */}
      <header className="sticky top-0 z-50 bg-white border-b"
              style={{ borderColor: T.border }}>
        <div className="max-w-[1400px] mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-6">
            {/* Logo */}
            <button onClick={() => setPage('home')} className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center"
                   style={{ backgroundColor: T.primary }}>
                <Cpu className="w-4.5 h-4.5 text-white" />
              </div>
              <div>
                <span className="text-sm font-semibold text-slate-900">IC Alternative Finder</span>
              </div>
            </button>

            {/* Section Nav */}
            <nav className="flex items-center gap-1 ml-4 border-l pl-4" style={{ borderColor: T.border }}>
              {([
                ['home', 'Home', Home],
                ['data', 'View Datasheet', FileText],
                ['finder', 'Find Replacement', Wrench],
              ] as const).map(([id, label, Icon]) => (
                <button key={id}
                  onClick={() => {
                    if (id === 'home') setPage('home')
                    else if (id === 'data') setPage('dashboard')
                    else setPage('search')
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors"
                  style={{
                    backgroundColor: section === id ? T.primaryLight : 'transparent',
                    color: section === id ? T.primary : T.textSecondary,
                    fontWeight: section === id ? 600 : 400,
                  }}>
                  <Icon className="w-3.5 h-3.5" /> {label}
                </button>
              ))}
            </nav>
          </div>

          {/* Search */}
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-2 w-4 h-4 text-slate-400" />
              <input type="text" value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && search()}
                placeholder="Search part number..."
                className="w-72 pl-9 pr-3 py-1.5 rounded-lg text-sm bg-slate-50 border border-slate-200 text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 transition-all" />
            </div>
            <button onClick={search} disabled={loading}
              className="px-4 py-1.5 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-colors"
              style={{ backgroundColor: T.primary }}>
              Search
            </button>
          </div>
        </div>

        {/* Sub-nav for Data section */}
        {section === 'data' && (
          <div className="border-t" style={{ borderColor: T.border }}>
            <div className="max-w-[1400px] mx-auto px-6 flex gap-1 h-10 items-center">
              {([
                ['dashboard', 'Dashboard', BarChart3],
                ['browse', 'Browse Categories', Layers],
              ] as const).map(([id, label, Icon]) => (
                <button key={id} onClick={() => setPage(id as Page)}
                  className="flex items-center gap-1.5 px-3 py-1 rounded-md text-xs transition-colors"
                  style={{
                    backgroundColor: page === id ? T.surfaceMuted : 'transparent',
                    color: page === id ? T.text : T.textSecondary,
                    fontWeight: page === id ? 500 : 400,
                  }}>
                  <Icon className="w-3.5 h-3.5" /> {label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Sub-nav for Finder section */}
        {section === 'finder' && (
          <div className="border-t" style={{ borderColor: T.border }}>
            <div className="max-w-[1400px] mx-auto px-6 flex gap-1 h-10 items-center">
              {([
                ['search', 'Search Parts', Search],
                ['alternatives', 'Find Alternatives', Zap],
                ['compare', 'Compare Parts', GitCompare],
              ] as const).map(([id, label, Icon]) => (
                <button key={id} onClick={() => setPage(id as Page)}
                  className="flex items-center gap-1.5 px-3 py-1 rounded-md text-xs transition-colors"
                  style={{
                    backgroundColor: page === id ? T.surfaceMuted : 'transparent',
                    color: page === id ? T.text : T.textSecondary,
                    fontWeight: page === id ? 500 : 400,
                  }}>
                  <Icon className="w-3.5 h-3.5" /> {label}
                </button>
              ))}
            </div>
          </div>
        )}
      </header>

      <main className="max-w-[1400px] mx-auto px-6 py-6">

        {/* ══════════════ HOME ══════════════ */}
        {page === 'home' && (
          <div className="max-w-3xl mx-auto py-16 text-center">
            <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-6"
                 style={{ backgroundColor: T.primaryLight }}>
              <Cpu className="w-8 h-8" style={{ color: T.primary }} />
            </div>
            <h1 className="text-3xl font-bold text-slate-900 mb-3">
              IC Alternative Finder
            </h1>
            <p className="text-lg text-slate-500 mb-10 max-w-xl mx-auto leading-relaxed">
              A technical IC replaceability engine for flat-panel monitor components.
              Search {dashboard?.total.toLocaleString() || '33,000+'} components across {' '}
              {categories.length || 22} categories with full electrical spec comparison.
            </p>

            <div className="grid grid-cols-2 gap-4 max-w-lg mx-auto mb-12">
              <button onClick={() => setPage('dashboard')}
                className="flex items-center gap-3 p-4 rounded-xl border border-slate-200 bg-white text-left hover:border-blue-300 hover:shadow-sm transition-all">
                <div className="w-10 h-10 rounded-lg flex items-center justify-center"
                     style={{ backgroundColor: T.primaryLight }}>
                  <FileText className="w-5 h-5" style={{ color: T.primary }} />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-900">View Datasheet</p>
                  <p className="text-xs text-slate-500">Browse database & specs</p>
                </div>
              </button>
              <button onClick={() => setPage('search')}
                className="flex items-center gap-3 p-4 rounded-xl border border-slate-200 bg-white text-left hover:border-blue-300 hover:shadow-sm transition-all">
                <div className="w-10 h-10 rounded-lg flex items-center justify-center"
                     style={{ backgroundColor: T.primaryLight }}>
                  <Wrench className="w-5 h-5" style={{ color: T.primary }} />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-900">Find Replacement</p>
                  <p className="text-xs text-slate-500">IC alternative engine</p>
                </div>
              </button>
            </div>

            <div className="grid grid-cols-3 gap-6 text-left max-w-2xl mx-auto">
              {[
                { icon: Target, title: 'Spec-Based Matching',
                  desc: '8–13 electrical parameters compared per category using weighted scoring' },
                { icon: Shield, title: 'Lifecycle Aware',
                  desc: 'Filters by Active, Obsolete, NRND, and Last Time Buy status automatically' },
                { icon: Award, title: 'Drop-In Detection',
                  desc: 'Identifies pin-compatible, same-package replacements that need zero PCB changes' },
              ].map(({ icon: Icon, title, desc }) => (
                <div key={title} className="p-4">
                  <Icon className="w-5 h-5 mb-3" style={{ color: T.primary }} />
                  <h3 className="text-sm font-semibold text-slate-900 mb-1">{title}</h3>
                  <p className="text-xs text-slate-500 leading-relaxed">{desc}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ══════════════ DASHBOARD ══════════════ */}
        {page === 'dashboard' && dashboard && (
          <div className="space-y-6">
            <SectionHeader icon={BarChart3} title="Database Overview"
                           subtitle={`${dashboard.total.toLocaleString()} components across ${Object.keys(dashboard.categories).length} categories`} />

            {/* KPIs */}
            <div className="grid grid-cols-4 gap-4">
              <KpiCard label="Total Components" value={dashboard.total.toLocaleString()} icon={Database} />
              <KpiCard label="Categories" value={Object.keys(dashboard.categories).length} icon={Layers} />
              <KpiCard label="Active Parts" value={(dashboard.lifecycle_breakdown['Active'] || 0).toLocaleString()} icon={CheckCircle} />
              <KpiCard label="Manufacturers" value={topMfrs.length + '+'} icon={Activity} />
            </div>

            {/* Charts */}
            <div className="grid grid-cols-5 gap-6">
              {/* Category Bar Chart — 3 columns */}
              <Card className="col-span-3 p-5">
                <h3 className="text-sm font-semibold text-slate-900 mb-4">Parts by Category</h3>
                <ResponsiveContainer width="100%" height={380}>
                  <BarChart data={categories.filter(c => c.count > 0).sort((a, b) => b.count - a.count).slice(0, 14)}
                            layout="vertical" margin={{ left: 160 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                    <XAxis type="number" tick={{ fill: T.textMuted, fontSize: 11 }} />
                    <YAxis type="category" dataKey="name" tick={{ fill: T.textSecondary, fontSize: 11 }} width={155} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Bar dataKey="count" fill={T.primary} radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Card>

              {/* Lifecycle Donut — 2 columns */}
              <Card className="col-span-2 p-5">
                <h3 className="text-sm font-semibold text-slate-900 mb-4">Lifecycle Status</h3>
                <ResponsiveContainer width="100%" height={380}>
                  <PieChart>
                    <Pie data={Object.entries(dashboard.lifecycle_breakdown).map(([name, value]) => ({ name, value }))}
                         cx="50%" cy="45%" outerRadius={100} innerRadius={55}
                         dataKey="value" paddingAngle={2} strokeWidth={0}>
                      {Object.keys(dashboard.lifecycle_breakdown).map((_, i) => (
                        <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={tooltipStyle} />
                    <Legend wrapperStyle={{ fontSize: 11, color: T.textMuted }} />
                  </PieChart>
                </ResponsiveContainer>
              </Card>
            </div>

            {/* Manufacturer Chart */}
            <Card className="p-5">
              <h3 className="text-sm font-semibold text-slate-900 mb-4">Top Manufacturers</h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={topMfrs.slice(0, 10)} margin={{ bottom: 60 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                  <XAxis dataKey="manufacturer" tick={{ fill: T.textMuted, fontSize: 10 }} angle={-45} textAnchor="end" />
                  <YAxis tick={{ fill: T.textMuted, fontSize: 10 }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Bar dataKey="count" fill={T.accent} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card>

            {/* Category Grid */}
            <div>
              <h3 className="text-sm font-semibold text-slate-900 mb-3">Browse by Category</h3>
              <div className="grid grid-cols-4 gap-3">
                {categories.filter(c => c.count > 0).sort((a, b) => b.count - a.count).map(cat => (
                  <button key={cat.slug} onClick={() => loadBrowse(cat.slug)}
                    className="text-left p-4 rounded-xl border border-slate-200 bg-white hover:border-blue-300 hover:shadow-sm transition-all">
                    <p className="text-xs font-medium text-slate-500">{cat.name}</p>
                    <p className="text-lg font-semibold text-slate-900 mt-1">{cat.count.toLocaleString()}</p>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ══════════════ BROWSE ══════════════ */}
        {page === 'browse' && (
          <div className="space-y-4">
            <SectionHeader icon={Layers} title="Browse Components" />
            <div className="flex items-center gap-4 mb-4">
              <select value={browseCat} onChange={e => loadBrowse(e.target.value)}
                className="px-3 py-2 rounded-lg text-sm bg-white border border-slate-200 text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20">
                <option value="">Select category</option>
                {categories.filter(c => c.count > 0).map(c => (
                  <option key={c.slug} value={c.slug}>{c.name} ({c.count})</option>
                ))}
              </select>
              <span className="text-xs text-slate-500">
                {browseTotal > 0 ? `${browseTotal.toLocaleString()} parts` : ''}
              </span>
            </div>
            {browseParts.length > 0 && (
              <Card>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-xs text-slate-500" style={{ borderColor: T.border }}>
                        <th className="text-left px-4 py-3 font-medium">MPN</th>
                        <th className="text-left px-4 py-3 font-medium">Manufacturer</th>
                        <th className="text-left px-4 py-3 font-medium">Description</th>
                        <th className="text-left px-4 py-3 font-medium">Status</th>
                        <th className="text-left px-4 py-3 font-medium">Package</th>
                        <th className="px-4 py-3"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {browseParts.map((p: any) => (
                        <tr key={p.manufacturer_part_number}
                            className="border-b hover:bg-slate-50 cursor-pointer transition-colors"
                            style={{ borderColor: T.border }}
                            onClick={() => selectPart(p.manufacturer_part_number)}>
                          <td className="px-4 py-3 font-mono text-xs font-medium" style={{ color: T.primary }}>{p.manufacturer_part_number}</td>
                          <td className="px-4 py-3 text-xs">{p.manufacturer}</td>
                          <td className="px-4 py-3 text-xs text-slate-500 truncate max-w-xs">{p.description}</td>
                          <td className="px-4 py-3"><LifecycleBadge status={p.lifecycle_status} /></td>
                          <td className="px-4 py-3 text-xs text-slate-500">{p.package}</td>
                          <td className="px-4 py-3"><ArrowRight className="w-3.5 h-3.5 text-slate-400" /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}
          </div>
        )}

        {/* ══════════════ SEARCH RESULTS ══════════════ */}
        {page === 'search' && (
          <div>
            <SectionHeader icon={Search} title="Search Components"
                           subtitle="Enter a part number or keyword to find components" />
            {searchResults.length > 0 && (
              <Card>
                <div className="px-5 py-3 border-b" style={{ borderColor: T.border }}>
                  <p className="text-sm font-medium text-slate-900">{searchResults.length} results for "{query}"</p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-xs text-slate-500" style={{ borderColor: T.border }}>
                        <th className="text-left px-4 py-2.5 font-medium">MPN</th>
                        <th className="text-left px-4 py-2.5 font-medium">Manufacturer</th>
                        <th className="text-left px-4 py-2.5 font-medium">Category</th>
                        <th className="text-left px-4 py-2.5 font-medium">Status</th>
                        <th className="text-left px-4 py-2.5 font-medium">Package</th>
                        <th className="px-4 py-2.5"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {searchResults.map(p => (
                        <tr key={p.mpn}
                            className="border-b hover:bg-slate-50 cursor-pointer transition-colors"
                            style={{ borderColor: T.border }}
                            onClick={() => selectPart(p.mpn)}>
                          <td className="px-4 py-3 font-mono text-xs font-medium" style={{ color: T.primary }}>{p.mpn}</td>
                          <td className="px-4 py-3 text-xs">{p.manufacturer}</td>
                          <td className="px-4 py-3 text-xs text-slate-500">{p.category}</td>
                          <td className="px-4 py-3"><LifecycleBadge status={p.lifecycle_status} /></td>
                          <td className="px-4 py-3 text-xs text-slate-500">{p.package}</td>
                          <td className="px-4 py-3"><ArrowRight className="w-3.5 h-3.5 text-slate-400" /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}
            {searchResults.length === 0 && query && (
              <Card className="p-12 text-center">
                <Search className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                <p className="text-sm text-slate-500">No results found for "{query}"</p>
              </Card>
            )}
            {!query && (
              <Card className="p-12 text-center">
                <Search className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                <p className="text-sm text-slate-500">Enter a part number or keyword above to search</p>
              </Card>
            )}
          </div>
        )}

        {/* ══════════════ ALTERNATIVES ══════════════ */}
        {page === 'alternatives' && selectedPart && (
          <div className="space-y-5">
            <SectionHeader icon={Zap} title="Alternative Finder"
                           subtitle={`Alternatives for ${selectedPart.mpn}`} />

            {/* Target Part */}
            <Card className="p-5">
              <div className="flex justify-between items-start">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-base font-semibold font-mono" style={{ color: T.primary }}>{selectedPart.mpn}</h3>
                    <LifecycleBadge status={selectedPart.lifecycle_status} />
                  </div>
                  <p className="text-sm text-slate-500">{selectedPart.description}</p>
                  <p className="text-xs text-slate-400 mt-1">
                    {selectedPart.manufacturer} · {selectedPart.category} · {selectedPart.package}
                  </p>
                </div>
                {selectedPart.datasheet_url && (
                  <a href={selectedPart.datasheet_url} target="_blank" rel="noreferrer"
                     className="text-xs flex items-center gap-1 px-3 py-1.5 rounded-md border border-slate-200 hover:bg-slate-50 transition-colors"
                     style={{ color: T.primary }}>
                    <ExternalLink className="w-3 h-3" /> Datasheet
                  </a>
                )}
              </div>
              {Object.keys(selectedPart.specs).length > 0 && (
                <div className="mt-4 grid grid-cols-4 gap-2">
                  {Object.entries(selectedPart.specs).sort().slice(0, 12).map(([k, v]) => (
                    <div key={k} className="rounded-md px-3 py-2 bg-slate-50">
                      <p className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">{k}</p>
                      <p className="text-xs font-medium text-slate-700 mt-0.5">{v}</p>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* Compatibility Scatter */}
            {alternatives.length > 3 && (
              <Card className="p-5">
                <h3 className="text-sm font-semibold text-slate-900 mb-3">Compatibility Overview</h3>
                <ResponsiveContainer width="100%" height={180}>
                  <ScatterChart margin={{ left: 10, right: 10, top: 10, bottom: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                    <XAxis type="number" dataKey="idx" name="Rank" tick={{ fill: T.textMuted, fontSize: 10 }} label={{ value: 'Rank', position: 'insideBottom', offset: -5, fontSize: 10, fill: T.textMuted }} />
                    <YAxis type="number" dataKey="pct" name="Compat" domain={[0, 100]} tick={{ fill: T.textMuted, fontSize: 10 }} label={{ value: 'Compatibility %', angle: -90, position: 'insideLeft', fontSize: 10, fill: T.textMuted }} />
                    <ZAxis range={[50, 180]} />
                    <Tooltip contentStyle={tooltipStyle}
                             formatter={(v: any, name: string) => [name === 'pct' ? `${v}%` : v, name === 'pct' ? 'Compatibility' : 'Rank']} />
                    <Scatter data={alternatives.map((a, i) => ({ idx: i + 1, pct: Math.round(a.compatibility_pct), name: a.mpn }))} >
                      {alternatives.map((a, i) => (
                        <Cell key={i} fill={a.compatibility_pct >= 80 ? T.success : a.compatibility_pct >= 50 ? T.warning : T.danger} />
                      ))}
                    </Scatter>
                  </ScatterChart>
                </ResponsiveContainer>
              </Card>
            )}

            {/* Alternatives List */}
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-semibold text-slate-900">{alternatives.length} Compatible Alternatives</p>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <label>Min:</label>
                <input type="range" min={0} max={90} value={minCompat}
                       onChange={e => setMinCompat(Number(e.target.value))} className="w-20" />
                <span className="font-mono w-8">{minCompat}%</span>
                <button onClick={() => selectPart(selectedPart.mpn)}
                  className="px-3 py-1 rounded-md text-xs font-medium ml-2 border border-slate-200 hover:bg-slate-50 transition-colors"
                  style={{ color: T.primary }}>
                  <RefreshCw className="w-3 h-3 inline mr-1" />Refresh
                </button>
              </div>
            </div>

            {alternatives.map((alt, idx) => (
              <Card key={alt.mpn} className={expandedAlt === idx ? 'ring-1 ring-blue-200' : ''}>
                <div className="flex items-start gap-4 p-4 cursor-pointer"
                     onClick={() => setExpandedAlt(expandedAlt === idx ? null : idx)}>
                  <CompatBadge pct={alt.compatibility_pct} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-xs font-bold text-slate-400">#{idx + 1}</span>
                      <span className="font-mono text-sm font-semibold" style={{ color: T.primary }}>{alt.mpn}</span>
                      {alt.is_drop_in && (
                        <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-emerald-50 text-emerald-600 uppercase tracking-wider">Drop-In</span>
                      )}
                    </div>
                    <p className="text-xs text-slate-500 truncate">{alt.description}</p>
                    <p className="text-[11px] text-slate-400 mt-0.5">{alt.manufacturer}</p>
                  </div>
                  <div className="text-right text-xs space-y-1 flex-shrink-0">
                    <LifecycleBadge status={alt.lifecycle_status} />
                    <p className="text-slate-400 mt-1">{alt.package}</p>
                  </div>
                  <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform flex-shrink-0 ${expandedAlt === idx ? 'rotate-180' : ''}`} />
                </div>

                {expandedAlt === idx && Object.keys(alt.spec_scores).length > 0 && (
                  <div className="px-4 pb-4 flex gap-6 border-t" style={{ borderColor: T.border }}>
                    <div className="flex-1 pt-3">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="text-slate-400">
                            <th className="text-left py-1.5 font-normal">Spec</th>
                            <th className="text-left py-1.5 font-normal">Target</th>
                            <th className="text-left py-1.5 font-normal">Candidate</th>
                            <th className="text-center py-1.5 font-normal">Match</th>
                            <th className="text-right py-1.5 font-normal">Score</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(alt.spec_scores).sort().map(([name, d]) => (
                            <tr key={name} className="border-t" style={{ borderColor: T.border }}>
                              <td className="py-1.5">
                                {d.required && <span className="text-red-500">* </span>}
                                <span className="text-slate-700">{name}</span>
                              </td>
                              <td className="py-1.5 font-mono text-slate-400">{d.target}</td>
                              <td className="py-1.5 font-mono text-slate-400">{d.candidate}</td>
                              <td className="py-1.5 text-center"><StatusDot status={d.status} /></td>
                              <td className="py-1.5 text-right font-mono text-slate-400">{d.score.toFixed(0)}/{d.max.toFixed(0)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {Object.keys(alt.spec_scores).length > 2 && (
                      <div className="w-60 flex-shrink-0 pt-3">
                        <ResponsiveContainer width="100%" height={220}>
                          <RadarChart data={Object.entries(alt.spec_scores).map(([name, d]) => ({
                            spec: name.length > 12 ? name.slice(0, 12) + '…' : name,
                            score: d.max > 0 ? (d.score / d.max) * 100 : 0,
                          }))}>
                            <PolarGrid stroke="#E2E8F0" />
                            <PolarAngleAxis dataKey="spec" tick={{ fill: T.textMuted, fontSize: 9 }} />
                            <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                            <Radar dataKey="score" stroke={T.primary} fill={T.primary} fillOpacity={0.15} strokeWidth={1.5} />
                          </RadarChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}

        {/* ══════════════ COMPARE ══════════════ */}
        {page === 'compare' && (
          <div className="space-y-5">
            <SectionHeader icon={GitCompare} title="Side-by-Side Comparison"
                           subtitle="Compare two parts across all specifications" />
            <Card className="p-5">
              <div className="grid grid-cols-2 gap-4 mb-4">
                <input value={cmpMpn1} onChange={e => setCmpMpn1(e.target.value)}
                  placeholder="Part 1 (e.g. MIC5501-3.0YM5-TR)"
                  className="px-3 py-2 rounded-lg text-sm bg-slate-50 border border-slate-200 text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20" />
                <input value={cmpMpn2} onChange={e => setCmpMpn2(e.target.value)}
                  placeholder="Part 2 (e.g. AP2112K-3.3TRG1)"
                  className="px-3 py-2 rounded-lg text-sm bg-slate-50 border border-slate-200 text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20" />
              </div>
              <button onClick={runCompare} disabled={loading || !cmpMpn1 || !cmpMpn2}
                className="px-5 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-colors"
                style={{ backgroundColor: T.primary }}>
                Compare
              </button>
            </Card>

            {cmpResult && (
              <Card>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-xs text-slate-500" style={{ borderColor: T.border }}>
                        <th className="text-left px-4 py-2.5 font-medium">Parameter</th>
                        <th className="text-left px-4 py-2.5 font-mono font-medium" style={{ color: T.primary }}>{cmpResult.part_a.mpn}</th>
                        <th className="text-left px-4 py-2.5 font-mono font-medium" style={{ color: T.accent }}>{cmpResult.part_b.mpn}</th>
                        <th className="text-center px-4 py-2.5 font-medium">Match</th>
                      </tr>
                    </thead>
                    <tbody>
                      {['manufacturer', 'category', 'package', 'mounting_type', 'lifecycle_status'].map(field => {
                        const va = cmpResult.part_a[field] || '-'
                        const vb = cmpResult.part_b[field] || '-'
                        const match = va.toLowerCase() === vb.toLowerCase()
                        return (
                          <tr key={field} className="border-b" style={{ borderColor: T.border }}>
                            <td className="px-4 py-2.5 capitalize text-slate-500 text-xs">{field.replace('_', ' ')}</td>
                            <td className="px-4 py-2.5 text-xs">{va}</td>
                            <td className="px-4 py-2.5 text-xs">{vb}</td>
                            <td className="px-4 py-2.5 text-center">
                              {match ? <CheckCircle className="w-4 h-4 inline" style={{ color: T.success }} />
                                     : <XCircle className="w-4 h-4 inline" style={{ color: T.danger }} />}
                            </td>
                          </tr>
                        )
                      })}
                      <tr><td colSpan={4} className="px-4 py-1.5 text-[10px] font-semibold uppercase tracking-widest text-slate-400 border-t" style={{ borderColor: T.border }}>Specifications</td></tr>
                      {cmpResult.all_spec_names.map((spec: string) => {
                        const va = cmpResult.part_a.specs[spec] || '-'
                        const vb = cmpResult.part_b.specs[spec] || '-'
                        const match = va.toLowerCase() === vb.toLowerCase()
                        return (
                          <tr key={spec} className="border-b" style={{ borderColor: T.border }}>
                            <td className="px-4 py-2 text-xs text-slate-500">{spec}</td>
                            <td className="px-4 py-2 text-xs font-mono">{va}</td>
                            <td className="px-4 py-2 text-xs font-mono">{vb}</td>
                            <td className="px-4 py-2 text-center">
                              {match ? <CheckCircle className="w-4 h-4 inline" style={{ color: T.success }} />
                                     : <AlertCircle className="w-4 h-4 inline" style={{ color: T.warning }} />}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t px-6 py-4 mt-8" style={{ borderColor: T.border }}>
        <div className="max-w-[1400px] mx-auto flex justify-between items-center">
          <span className="text-xs text-slate-400">
            IC Alternative Finder · {dashboard?.total.toLocaleString() || '...'} components · {Object.keys(dashboard?.categories || {}).length} categories
          </span>
          <span className="text-xs text-slate-400">
            Purely technical comparison — no stock or pricing in scoring
          </span>
        </div>
      </footer>
    </div>
  )
}