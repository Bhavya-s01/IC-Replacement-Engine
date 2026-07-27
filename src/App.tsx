import dellLogo from './assets/dell_logo.png'
import { useState, useEffect, useRef } from 'react'
import { api } from './api'
import {
  Search, Cpu, BarChart3, ArrowRight, CheckCircle, XCircle,
  AlertCircle, Layers, Zap, Database,
  RefreshCw, ExternalLink, ChevronDown, Home,
  FileText, Wrench, Activity, Shield, GitCompare, Award,
  Target, Network, BookOpen
} from 'lucide-react'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, ScatterChart, Scatter, ZAxis,
  CartesianGrid
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
  drop_in_checklist?: {
    package_match: boolean; mounting_match: boolean;
    required_specs_pass: boolean; lifecycle_active: boolean;
    target_package: string; candidate_package: string;
  };
}
type Category = { slug: string; name: string; description: string; count: number }
type DashboardData = {
  total: number; categories: Record<string, number>;
  category_names: Record<string, string>;
  lifecycle_breakdown: Record<string, number>;
}
type MatchingRule = {
  slug: string; name: string; description: string;
  package_weight: number; mount_weight: number;
  temp_weight: number; lifecycle_weight: number;
  specs: { name: string; weight: number; match_type: string;
           tolerance_pct: number; required: boolean; aliases: string[] }[];
}

// ═══════════════════════════════════════════
// Scroll Animation Hook
// ═══════════════════════════════════════════
function useScrollReveal() {
  const ref = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setVisible(true) },
      { threshold: 0.15, rootMargin: '0px 0px -40px 0px' }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  return { ref, visible }
}

function RevealSection({ children, className = '', delay = 0 }: {
  children: React.ReactNode; className?: string; delay?: number
}) {
  const { ref, visible } = useScrollReveal()
  return (
    <div ref={ref} className={className}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(32px)',
        transition: `opacity 600ms ease ${delay}ms, transform 600ms ease ${delay}ms`,
      }}>
      {children}
    </div>
  )
}

// ═══════════════════════════════════════════
// Design Tokens
// ═══════════════════════════════════════════
// Replace your existing T = { ... } block with:
const DELL = {
  blue: '#0076CE',
  black: '#000000',
  cosmos: '#1D2C3B',
  raven: '#40586D',
  mist: '#C5D4E3',
  white: '#FFFFFF',
  quartz: '#F0F0F0',
  titanium: '#D2D2D2',
  steel: '#B6B6B6',
  ocean: '#00468B',
  midnight: '#0D2155',
  forest: '#0B7C84',
  teal: '#044E52',
  plum: '#66278F',
  dusk: '#40155C',
}

const T = {
  // Backgrounds [1]
  bg: '#FFFFFF',                    // White
  bgAlt: DELL.quartz,              // Quartz (#F0F0F0)
  surface: '#FFFFFF',
  surfaceMuted: DELL.quartz,

  // Borders
  border: DELL.mist,               // Mist (#C5D4E3)

  // Text - approved colors on neutral backgrounds [1]
  text: DELL.cosmos,               // Cosmos (#1D2C3B) - primary text
  textSecondary: DELL.raven,       // Raven (#40586D)
  textMuted: DELL.steel,           // Steel (#B6B6B6)

  // Brand [1]
  primary: DELL.blue,              // Dell Blue (#0076CE)
  primaryDark: DELL.ocean,         // Ocean (#00468B)
  primaryLight: '#E0F2FE',         // Light blue tint

  // Semantic
  success: '#16A34A',
  successBg: '#F0FDF4',
  warning: '#CA8A04',
  warningBg: '#FEFCE8',
  danger: '#DC2626',
  dangerBg: '#FEF2F2',

  // Accent
  accent: DELL.midnight,           // Midnight (#0D2155) - approved for text [1]
}
const CHART_COLORS = ['#0076CE','#00447C','#0284C7','#0EA5E9','#38BDF8',
  '#7DD3FC','#06B6D4','#14B8A6','#10B981','#22C55E']
const tooltipStyle = { backgroundColor: '#fff', border: '1px solid #E2E8F0',
  borderRadius: 8, fontSize: 12, boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.05)' }

// ═══════════════════════════════════════════
// DDS Icon Component — uses Dell icon font [3]
// ═══════════════════════════════════════════
function DdsIcon({ name, size = 24, color, className = '' }: {
  name: string; size?: number; color?: string; className?: string
}) {
  return (
    <i
      className={`dds__icon dds__icon--${name} ${className}`}
      style={{ fontSize: size, color: color || 'inherit' }}
      aria-hidden="true"
    />
  )
}

// Lucide icon wrapper with Dell stroke weights [3]
function DellIcon({ icon: Icon, size = 24, color = '#0076CE', className = '' }: {
  icon: any; size?: 16 | 24 | 32 | 40 | 48; color?: string; className?: string
}) {
  const strokeMap: Record<number, number> = {
    16: 1, 24: 1.5, 32: 2, 40: 2.5, 48: 3
  }
  return (
    <Icon
      className={className}
      width={size}
      height={size}
      style={{ color }}
      strokeWidth={strokeMap[size] || 1.5}
    />
  )
}

function CompatBadge({ pct }: { pct: number }) {
  const color = pct >= 80 ? T.success : pct >= 50 ? T.warning : T.danger
  return (
    <span className="inline-flex items-center px-2 py-0.5 text-xs font-mono font-semibold"
          style={{ color, backgroundColor: 'transparent', border: `1px solid ${color}`, borderRadius: 2 }}>
      {pct.toFixed(0)}%
    </span>
  )
}

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-white border ${className}`}
         style={{ borderColor: T.border, borderRadius: 4 }}>
      {children}
    </div>
  )
}

function KpiCard({ label, value, icon: Icon, dds }: {
  label: string; value: string | number; icon?: any; dds?: string
}) {
  return (
    <Card className="px-5 py-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-neutral-500 font-medium uppercase tracking-wide">{label}</p>
          <p className="text-xl font-semibold mt-1" style={{ color: T.text }}>{value}</p>
        </div>
        {dds
          ? <DdsIcon name={dds} size={16} color={T.textMuted} />
          : Icon
            ? <Icon className="w-4 h-4" style={{ color: T.textMuted }} />
            : null}
      </div>
    </Card>
  )
}

function SectionHeader({ icon: Icon, dds, title, subtitle }: {
  icon?: any; dds?: string; title: string; subtitle?: string
}) {
  return (
    <div className="flex items-center gap-2.5 mb-5">
      {dds
        ? <DdsIcon name={dds} size={18} color={T.primary} />
        : Icon
          ? <Icon className="w-4 h-4" style={{ color: T.primary }} />
          : null}
      <div>
        <h2 className="text-sm font-semibold" style={{ color: T.text }}>{title}</h2>
        {subtitle && <p className="text-xs" style={{ color: T.textMuted }}>{subtitle}</p>}
      </div>
    </div>
  )
}

// function CompatBadge({ pct }: { pct: number }) {
//   const color = pct >= 80 ? T.success : pct >= 50 ? T.warning : T.danger
//   return (
//     <span className="inline-flex items-center px-2 py-0.5 text-xs font-mono font-semibold"
//           style={{ color, backgroundColor: 'transparent', border: `1px solid ${color}`, borderRadius: 2 }}>
//       {pct.toFixed(0)}%
//     </span>
//   )
// }

function LifecycleBadge({ status }: { status: string }) {
  const s = (status || '').toLowerCase()
  const color = s === 'active' ? T.success
    : s.includes('obsolete') ? T.danger
    : s.includes('not for new') || s.includes('last time') ? T.warning
    : T.textMuted
  return (
    <span className="text-[11px] font-medium uppercase tracking-wide" style={{ color }}>
      {status || '—'}
    </span>
  )
}

function StatusDot({ status }: { status: string }) {
  const color = status === 'MATCH' ? T.success : status === 'FAIL' ? T.danger : T.warning
  return (
    <span className="inline-block w-1.5 h-1.5" style={{ backgroundColor: color, borderRadius: 1 }} />
  )
}

// ═══════════════════════════════════════════
// Graph Component
// ═══════════════════════════════════════════
function CompatibilityGraph({ target, alternatives }: { target: PartDetail; alternatives: Alternative[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const animRef = useRef<number>(0)

  useEffect(() => {
    if (!canvasRef.current || !containerRef.current || !alternatives.length) return
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const context: CanvasRenderingContext2D = ctx
    const W = containerRef.current.clientWidth
    const H = 480
    canvas.width = W * 2; canvas.height = H * 2
    canvas.style.width = W + 'px'; canvas.style.height = H + 'px'
    context.scale(2, 2)

    const nodes = [
      { id: target.mpn, x: W / 2, y: H / 2, vx: 0, vy: 0, group: 'target', pct: 100, lifecycle: 'Active', pkg: target.package },
      ...alternatives.map((a, i) => ({
        id: a.mpn, group: a.is_drop_in ? 'dropin' : 'alt', pct: a.compatibility_pct,
        x: W / 2 + Math.cos(i * (2 * Math.PI / alternatives.length)) * 180,
        y: H / 2 + Math.sin(i * (2 * Math.PI / alternatives.length)) * 180,
        vx: 0, vy: 0, lifecycle: a.lifecycle_status, pkg: a.package,
        samePackage: (a.package || '').toLowerCase() === (target.package || '').toLowerCase(),
      }))
    ]

    function simulate() {
      for (let i = 1; i < nodes.length; i++) {
        const s = nodes[0], t = nodes[i]
        const dx = t.x - s.x, dy = t.y - s.y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const targetDist = 200 - t.pct * 0.8
        const force = (dist - targetDist) * 0.002
        s.vx += dx / dist * force; s.vy += dy / dist * force
        t.vx -= dx / dist * force; t.vy -= dy / dist * force
      }
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[j].x - nodes[i].x, dy = nodes[j].y - nodes[i].y
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          if (dist < 120) {
            const f = (120 - dist) * 0.008
            nodes[i].vx -= dx / dist * f; nodes[i].vy -= dy / dist * f
            nodes[j].vx += dx / dist * f; nodes[j].vy += dy / dist * f
          }
        }
        nodes[i].vx += (W / 2 - nodes[i].x) * 0.0003
        nodes[i].vy += (H / 2 - nodes[i].y) * 0.0003
        nodes[i].vx *= 0.92; nodes[i].vy *= 0.92
        nodes[i].x += nodes[i].vx; nodes[i].y += nodes[i].vy
        nodes[i].x = Math.max(50, Math.min(W - 50, nodes[i].x))
        nodes[i].y = Math.max(50, Math.min(H - 50, nodes[i].y))
      }
    }

    function draw() {
      simulate()
      context.fillStyle = '#F8FAFC'; context.fillRect(0, 0, W, H)
      // Links
      for (let i = 1; i < nodes.length; i++) {
        const s = nodes[0], t = nodes[i], compat = t.pct
        context.strokeStyle = compat >= 80 ? '#16A34A60' : compat >= 50 ? '#CA8A0440' : '#DC262630'
        context.lineWidth = (t as any).samePackage ? 3 : Math.max(1, compat / 40)
        context.setLineDash((t as any).samePackage ? [] : [4, 4])
        context.beginPath(); context.moveTo(s.x, s.y); context.lineTo(t.x, t.y); context.stroke()
        context.setLineDash([])
        const mx = (s.x + t.x) / 2, my = (s.y + t.y) / 2
        context.fillStyle = '#475569'; context.font = '9px Inter, sans-serif'; context.textAlign = 'center'
        context.fillText(`${compat.toFixed(0)}%`, mx, my - 5)
      }
      // Nodes
      for (const node of nodes) {
        const isTarget = node.group === 'target'
        const isDropin = node.group === 'dropin'
        const r = isTarget ? 20 : isDropin ? 13 : 10
        const lc = (node.lifecycle || '').toLowerCase()
        const nodeColor = isTarget ? T.primary : lc === 'active' ? T.success
          : lc.includes('obsolete') ? T.danger : T.warning
        context.beginPath(); context.arc(node.x, node.y, r, 0, Math.PI * 2)
        context.fillStyle = isTarget ? T.primaryLight : '#F8FAFC'; context.fill()
        context.strokeStyle = nodeColor; context.lineWidth = isDropin ? 3 : 2; context.stroke()
        if ((node as any).samePackage && !isTarget) {
          context.beginPath(); context.arc(node.x, node.y, 3, 0, Math.PI * 2)
          context.fillStyle = T.primary; context.fill()
        }
        if (isDropin) {
          context.fillStyle = T.successBg
          context.fillRect(node.x - 18, node.y - r - 14, 36, 12)
          context.fillStyle = T.success; context.font = 'bold 7px Inter, sans-serif'
          context.fillText('DROP-IN', node.x, node.y - r - 6)
        }
        context.fillStyle = T.text; context.textAlign = 'center'
        context.font = `${isTarget ? 'bold 11' : '9'}px Inter, monospace`
        const label = node.id.length > 20 ? node.id.slice(0, 20) + '…' : node.id
        context.fillText(label, node.x, node.y + r + 14)
      }
      animRef.current = requestAnimationFrame(draw)
    }
    draw()
    return () => cancelAnimationFrame(animRef.current)
  }, [target, alternatives])

  return <div ref={containerRef} style={{ width: '100%', height: 480 }}><canvas ref={canvasRef} /></div>
}

// ═══════════════════════════════════════════
// MAIN APP
// ═══════════════════════════════════════════
export default function App() {
  type Page = 'home' | 'methodology' | 'dashboard' | 'browse' | 'search' | 'alternatives' | 'compare' | 'graph'
  // Temporary value to keep a stale fragment from rendering until it is removed.
  const entry = { dual_fab_plan: '' }
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
  const [matchingRules, setMatchingRules] = useState<MatchingRule[]>([])
  const [expandedRule, setExpandedRule] = useState<string | null>(null)
  const [supplyChainData, setSupplyChainData] = useState<Record<string, any>>({})
  const [showSupplyChain, setShowSupplyChain] = useState<number | null>(null)
  useEffect(() => { loadDashboard() }, [])

  const loadDashboard = async () => {
    try {
      const [d, c, m] = await Promise.all([api.dashboard(), api.categories(), api.topManufacturers()])
      setDashboard(d.data); setCategories(c.data); setTopMfrs(m.data)
    } catch (e) { console.error(e) }
  }
  const loadMatchingRules = async () => {
    try { const r = await api.matchingRules(); setMatchingRules(r.data) }
    catch (e) { console.error(e) }
  }
  const search = async () => {
    if (!query.trim()) return; setLoading(true)
    try { const r = await api.search(query, 30); setSearchResults(r.data); setPage('search') }
    catch (e) { console.error(e) } setLoading(false)
  }
  const selectPart = async (mpn: string) => {
    setLoading(true)
    try {
      const [p, a] = await Promise.all([api.lookup(mpn), api.alternatives(mpn, 15, minCompat)])
      setSelectedPart(p.data); setAlternatives(a.data); setPage('alternatives'); setExpandedAlt(null)
    } catch (e) { console.error(e) } setLoading(false)
  }
  const runCompare = async () => {
    if (!cmpMpn1 || !cmpMpn2) return; setLoading(true)
    try { const r = await api.compare(cmpMpn1, cmpMpn2); setCmpResult(r.data) }
    catch (e) { console.error(e) } setLoading(false)
  }
  const loadBrowse = async (cat: string) => {
    setBrowseCat(cat)
    try { const r = await api.browse(cat, 50); setBrowseParts(r.data.parts); setBrowseTotal(r.data.total); setPage('browse') }
    catch (e) { console.error(e) }
  }

  const loadSupplyChain = async (mpn: string, idx: number) => {
  if (supplyChainData[mpn]) {
    setShowSupplyChain(showSupplyChain === idx ? null : idx)
    return
  }
  try {
    const r = await api.supplyChain(mpn)
    setSupplyChainData(prev => ({ ...prev, [mpn]: r.data }))
    setShowSupplyChain(idx)
  } catch (e) {
    console.error(e)
  }
}

  const section = page === 'home' || page === 'methodology' ? 'home'
    : ['dashboard', 'browse'].includes(page) ? 'data' : 'finder'

  const matchTypeLabel: Record<string, string> = {
    'exact': 'Exact Match', 'numeric_close': 'Numeric ±%', 'meets_or_exceeds': '≥ Target',
    'range_covers': 'Range Covers', 'contains': 'Contains',
  }

  return (
    <div className="min-h-screen" style={{ backgroundColor: T.bgAlt, color: T.text }}>
      {/* TOP NAV */}
      <header className="sticky top-0 z-50 bg-white border-b" style={{ borderColor: T.border }}>
        <div className="max-w-[1400px] mx-auto px-6 h-12 flex items-center justify-between">
          <div className="flex items-center gap-5">
            <button onClick={() => setPage('home')} className="flex items-center gap-3">
              <img src={dellLogo} alt="Dell Technologies" className="h-5 w-auto" />
              <div className="h-4 w-px" style={{ backgroundColor: T.border }} />
              <span className="text-[13px] font-medium" style={{ color: T.text }}>IC Alternative Finder</span>
            </button>
            <div className="h-4 w-px bg-neutral-200" />
            <nav className="flex items-center gap-0.5">
              {([
                ['home', 'Home', 'home'],
                ['data', 'Datasheet', 'doc-search'],
                ['finder', 'Replacement', 'wrench-tools'],
              ] as const).map(([id, label, ddsIcon]) => (
                <button key={id}
                  onClick={() => { if (id === 'home') setPage('home'); else if (id === 'data') setPage('dashboard'); else setPage('search') }}
                  className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium transition-colors"
                  style={{
                    color: section === id ? T.primary : T.textSecondary,
                    borderBottom: section === id ? `2px solid ${T.primary}` : '2px solid transparent',
                  }}>
                  <DdsIcon name={ddsIcon} size={13} /> {label}
                </button>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <DdsIcon name="search" size={14} className="absolute left-2.5 top-[7px] text-neutral-400" />
              <input type="text" value={query} onChange={e => setQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && search()} placeholder="Search MPN..."
                className="w-56 pl-8 pr-3 py-1.5 text-xs bg-neutral-50 border text-neutral-900 placeholder-neutral-400 focus:outline-none focus:border-blue-400"
                style={{ borderColor: T.border, borderRadius: 2 }} />
            </div>
            <button onClick={search} disabled={loading}
              className="px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
              style={{ backgroundColor: T.primary, borderRadius: 2 }}>
              Search
            </button>
          </div>
        </div>

        {/* Sub-nav — Data section */}
        {section === 'data' && (
          <div className="border-t" style={{ borderColor: T.border }}>
            <div className="max-w-[1400px] mx-auto px-6 flex gap-0.5 h-9 items-center">
              {([
                ['dashboard', 'Dashboard', 'dashboard'],
                ['browse', 'Browse', 'view-grid'],
              ] as const).map(([id, label, ddsIcon]) => (
                <button key={id} onClick={() => setPage(id as Page)}
                  className="flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-medium transition-colors"
                  style={{ color: page === id ? T.text : T.textMuted }}>
                  <DdsIcon name={ddsIcon} size={12} /> {label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Sub-nav — Finder section */}
        {section === 'finder' && (
          <div className="border-t" style={{ borderColor: T.border }}>
            <div className="max-w-[1400px] mx-auto px-6 flex gap-0.5 h-9 items-center">
              {([
                ['search', 'Search', 'search'],
                ['alternatives', 'Alternatives', 'bolt'],
                ['compare', 'Compare', 'compare'],
                ['graph', 'Graph', 'network-connected'],
              ] as const).map(([id, label, ddsIcon]) => (
                <button key={id} onClick={() => setPage(id as Page)}
                  className="flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-medium transition-colors"
                  style={{ color: page === id ? T.text : T.textMuted }}>
                  <DdsIcon name={ddsIcon} size={12} /> {label}
                </button>
              ))}
            </div>
          </div>
        )}
      </header>

      <main className="max-w-[1400px] mx-auto px-6 py-6">

        {/* ══════════════ HOME ══════════════ */}
        {page === 'home' && (
          <div className="-mx-6 -mt-6" style={{ backgroundColor: '#FFFFFF' }}>

            {/* ═══════════════════════════════════════
                SECTION 1 — HERO / LANDING
            ═══════════════════════════════════════ */}
            <section className="relative overflow-hidden"
              style={{
                minHeight: '80vh',
                backgroundColor: '#0D1B2A',
                backgroundAttachment: 'fixed',
                backgroundImage: 'radial-gradient(ellipse at 20% 80%, rgba(0,118,206,0.12) 0%, transparent 60%), radial-gradient(ellipse at 80% 20%, rgba(0,68,124,0.08) 0%, transparent 50%)',
              }}>
              <div className="absolute inset-0 opacity-[0.03]"
                style={{
                  backgroundImage: 'linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)',
                  backgroundSize: '48px 48px',
                }} />

              <div className="relative z-10 max-w-[1200px] mx-auto px-12 flex flex-col justify-center" style={{ minHeight: '80vh' }}>
                <RevealSection>
                  <div className="flex items-center gap-2 mb-6">
                    <div className="h-px flex-1 max-w-[48px]" style={{ backgroundColor: '#0076CE' }} />
                    <span className="text-[11px] font-medium tracking-[0.2em] uppercase" style={{ color: '#60A5FA' }}>
                      Engineering Tool
                    </span>
                  </div>
                </RevealSection>

                <RevealSection delay={100}>
                  <h1 className="text-5xl font-bold text-white leading-[1.1] mb-5 max-w-2xl">
                    IC Alternative<br />Finder
                  </h1>
                </RevealSection>

                <RevealSection delay={200}>
                  <p className="text-lg leading-relaxed max-w-xl mb-10" style={{ color: '#94A3B8' }}>
                    A technical IC replaceability engine for flat-panel monitor components.
                    Full electrical spec comparison with weighted scoring, lifecycle awareness,
                    and drop-in detection.
                  </p>
                </RevealSection>

                <RevealSection delay={300}>
                  <div className="flex items-center gap-3 mb-16">
                    <button onClick={() => setPage('search')}
                      className="px-6 py-2.5 text-sm font-medium text-white transition-all hover:opacity-90"
                      style={{ backgroundColor: '#0076CE', borderRadius: 6 }}>
                      Get Started
                    </button>
                    <button onClick={() => {
                      const el = document.getElementById('section-stats')
                      el?.scrollIntoView({ behavior: 'smooth' })
                    }}
                      className="px-6 py-2.5 text-sm font-medium border transition-all hover:bg-white/5"
                      style={{ color: '#94A3B8', borderColor: '#334155', borderRadius: 6 }}>
                      Learn More
                    </button>
                  </div>
                </RevealSection>
              </div>

              <div className="absolute bottom-0 left-0 right-0 h-24"
                style={{ background: 'linear-gradient(to bottom, transparent, #FFFFFF)' }} />
            </section>

            {/* ═══════════════════════════════════════
                SECTION 2 — DATABASE STATS BAR
            ═══════════════════════════════════════ */}
            <section id="section-stats" className="relative py-16 px-12" style={{ backgroundColor: '#FFFFFF' }}>
              <div className="max-w-[1200px] mx-auto">
                <RevealSection>
                  <div className="flex items-center gap-2 mb-8">
                    <div className="h-px w-8" style={{ backgroundColor: '#0076CE' }} />
                    <span className="text-[11px] font-medium tracking-[0.2em] uppercase" style={{ color: '#0076CE' }}>
                      Database at a Glance
                    </span>
                  </div>
                </RevealSection>

                <div className="grid grid-cols-4 gap-6">
                  {[
                    { value: dashboard?.total.toLocaleString() || '33,710', label: 'Total Components', icon: 'microchip' },
                    { value: String(categories.length || 22), label: 'IC Categories', icon: 'view-grid' },
                    { value: (dashboard?.lifecycle_breakdown?.['Active'] || 0).toLocaleString(), label: 'Active Parts', icon: 'alert-check' },
                    { value: `${topMfrs.length || 10}+`, label: 'Manufacturers', icon: 'network-connected' },
                  ].map(({ value, label, icon }, i) => (
                    <RevealSection key={label} delay={i * 100}>
                      <div className="border p-6 h-full"
                          style={{ borderColor: T.border, borderRadius: 10, backgroundColor: '#FFFFFF' }}>
                        <div className="flex items-center gap-3 mb-3">
                          <div className="w-9 h-9 flex items-center justify-center"
                              style={{ backgroundColor: T.primaryLight, borderRadius: 8 }}>
                            <DdsIcon name={icon} size={18} color={T.primary} />
                          </div>
                        </div>
                        <p className="text-3xl font-bold" style={{ color: T.text }}>{value}</p>
                        <p className="text-xs mt-1" style={{ color: T.textSecondary }}>{label}</p>
                      </div>
                    </RevealSection>
                  ))}
                </div>
              </div>
            </section>

            {/* ═══════════════════════════════════════
                SECTION 3 — TOOLS
            ═══════════════════════════════════════ */}
            <section className="relative py-20 px-12"
              style={{ backgroundColor: T.bgAlt }}>
              <div className="max-w-[1200px] mx-auto">
                <RevealSection>
                  <div className="flex items-center gap-2 mb-3">
                    <div className="h-px w-8" style={{ backgroundColor: '#0076CE' }} />
                    <span className="text-[11px] font-medium tracking-[0.2em] uppercase" style={{ color: '#0076CE' }}>
                      Tools
                    </span>
                  </div>
                  <h2 className="text-2xl font-bold mb-2" style={{ color: T.text }}>
                    Two ways to explore
                  </h2>
                  <p className="text-sm mb-12 max-w-lg" style={{ color: T.textSecondary }}>
                    Browse the full component database or find compatible replacements for any IC.
                  </p>
                </RevealSection>

                <div className="grid grid-cols-2 gap-6">
                  <RevealSection delay={100}>
                    <button onClick={() => setPage('dashboard')}
                      className="group text-left w-full border overflow-hidden transition-all hover:shadow-lg hover:border-blue-200 h-full"
                      style={{ borderColor: T.border, borderRadius: 12, backgroundColor: '#FFFFFF' }}>
                      <div className="h-1 w-full" style={{ backgroundColor: '#0076CE' }} />
                      <div className="p-8">
                        <div className="w-12 h-12 flex items-center justify-center mb-5"
                          style={{ backgroundColor: T.primaryLight, borderRadius: 10 }}>
                          <DdsIcon name="doc-search" size={24} color="#0076CE" />
                        </div>
                        <h3 className="text-lg font-semibold mb-2" style={{ color: T.text }}>View Datasheet</h3>
                        <p className="text-sm leading-relaxed mb-6" style={{ color: T.textSecondary }}>
                          Browse the complete IC database with parametric specifications, lifecycle status,
                          and manufacturer data across {categories.length || 22} categories.
                          View detailed electrical specs extracted from datasheets including PSRR,
                          dropout voltage, quiescent current, and more.
                        </p>
                        <div className="flex items-center gap-2 text-sm font-medium transition-all group-hover:gap-3"
                          style={{ color: '#0076CE' }}>
                          Browse database <ArrowRight className="w-4 h-4" />
                        </div>
                      </div>
                    </button>
                  </RevealSection>

                  <RevealSection delay={200}>
                    <button onClick={() => setPage('search')}
                      className="group text-left w-full border overflow-hidden transition-all hover:shadow-lg hover:border-blue-200 h-full"
                      style={{ borderColor: T.border, borderRadius: 12, backgroundColor: '#FFFFFF' }}>
                      <div className="h-1 w-full" style={{ backgroundColor: '#00447C' }} />
                      <div className="p-8">
                        <div className="w-12 h-12 flex items-center justify-center mb-5"
                          style={{ backgroundColor: T.primaryLight, borderRadius: 10 }}>
                          <DdsIcon name="wrench-tools" size={24} color="#00447C" />
                        </div>
                        <h3 className="text-lg font-semibold mb-2" style={{ color: T.text }}>Find Replacement</h3>
                        <p className="text-sm leading-relaxed mb-6" style={{ color: T.textSecondary }}>
                          Enter any IC part number to find ranked alternatives with full electrical spec
                          comparison. The engine uses category-specific weighted scoring across 8–13 parameters,
                          identifies drop-in replacements with matching packages and pinouts,
                          and provides side-by-side comparison with radar charts.
                        </p>
                        <div className="flex items-center gap-2 text-sm font-medium transition-all group-hover:gap-3"
                          style={{ color: '#00447C' }}>
                          Find alternatives <ArrowRight className="w-4 h-4" />
                        </div>
                      </div>
                    </button>
                  </RevealSection>
                </div>
              </div>
            </section>

            {/* ═══════════════════════════════════════
                SECTION 4 — CAPABILITIES
            ═══════════════════════════════════════ */}
            <section className="relative py-20 px-12"
              style={{
                backgroundColor: '#0F172A',
                backgroundAttachment: 'fixed',
                backgroundImage: 'radial-gradient(ellipse at 70% 50%, rgba(0,118,206,0.06) 0%, transparent 60%)',
              }}>
              <div className="max-w-[1200px] mx-auto">
                <RevealSection>
                  <div className="flex items-center gap-2 mb-3">
                    <div className="h-px w-8" style={{ backgroundColor: '#60A5FA' }} />
                    <span className="text-[11px] font-medium tracking-[0.2em] uppercase" style={{ color: '#60A5FA' }}>
                      Capabilities
                    </span>
                  </div>
                  <h2 className="text-2xl font-bold text-white mb-2">
                    What powers the engine
                  </h2>
                  <p className="text-sm mb-14 max-w-lg" style={{ color: '#64748B' }}>
                    Technical comparison across multiple dimensions — no stock or pricing in compatibility scoring.
                  </p>
                </RevealSection>

                <div className="grid grid-cols-3 gap-6">
                  {[
                    {
                      icon: 'shield-check',
                      title: 'Spec-Based Matching',
                      desc: 'Every IC category has its own set of matching rules with 8–13 electrical parameters compared using weighted scoring algorithms. Required specs must pass — if they fail, the candidate is disqualified.',
                      bullets: [
                        'Voltage output/input ranges',
                        'Current capacity and quiescent current',
                        'PSRR, dropout, load/line regulation',
                        'Temperature range and thermal resistance',
                      ],
                    },
                    {
                      icon: 'microchip',
                      title: 'Drop-In Detection',
                      desc: 'Automatically identifies pin-compatible, same-package replacements that require zero PCB changes. The checklist verifies package footprint, mounting type, and lifecycle status.',
                      bullets: [
                        'Package footprint match verification',
                        'Mounting type compatibility check',
                        'Required spec pass/fail gate',
                        'Active lifecycle confirmation',
                      ],
                    },
                    {
                      icon: 'chart-bars',
                      title: 'Supply Chain Availability',
                      desc: 'View supplier data, lead times, minimum order quantities, and multi-source availability for each candidate alternative alongside technical compatibility.',
                      bullets: [
                        'Distributor stock levels',
                        'Lead time estimates',
                        'Minimum order quantities (MOQ)',
                        'Multi-source availability check',
                      ],
                      asterisk: true,
                    },
                  ].map(({ icon, title, desc, bullets, asterisk }, i) => (
                    <RevealSection key={title} delay={i * 100}>
                      <div className="border p-8 h-full flex flex-col"
                          style={{ borderColor: '#1E293B', borderRadius: 12 }}>
                        <DdsIcon name={icon} size={28} color="#60A5FA" />
                        <h3 className="text-lg font-semibold text-white mt-4 mb-3">
                          {title}{asterisk && <span className="text-[10px] text-slate-500 align-super ml-1">*</span>}
                        </h3>
                        <p className="text-sm leading-relaxed mb-5 flex-1" style={{ color: '#94A3B8' }}>
                          {desc}
                        </p>
                        <div className="space-y-2">
                          {bullets.map(item => (
                            <div key={item} className="flex items-center gap-2">
                              <div className="w-1 h-1 rounded-full flex-shrink-0" style={{ backgroundColor: '#60A5FA' }} />
                              <span className="text-xs" style={{ color: '#94A3B8' }}>{item}</span>
                            </div>
                          ))}
                        </div>
                        {asterisk && (
                          <p className="text-[10px] mt-4 pt-3 border-t" style={{ color: '#475569', borderColor: '#1E293B' }}>
                            * Based on ODM supply chain data — availability varies by distributor and region.
                          </p>
                        )}
                      </div>
                    </RevealSection>
                  ))}
                </div>
              </div>
            </section>

            {/* ═══════════════════════════════════════
                SECTION 5 — METHODOLOGY
            ═══════════════════════════════════════ */}
            <section className="relative py-20 px-12" style={{ backgroundColor: '#FFFFFF' }}>
              <div className="max-w-[1200px] mx-auto">
                <RevealSection>
                  <div className="flex items-center gap-2 mb-3">
                    <div className="h-px w-8" style={{ backgroundColor: '#0076CE' }} />
                    <span className="text-[11px] font-medium tracking-[0.2em] uppercase" style={{ color: '#0076CE' }}>
                      Methodology
                    </span>
                  </div>
                  <h2 className="text-2xl font-bold mb-2" style={{ color: T.text }}>
                    How matching works
                  </h2>
                  <p className="text-sm mb-12 max-w-lg" style={{ color: T.textSecondary }}>
                    Every category has its own rule set defining which specs to compare,
                    their weights, and tolerance thresholds.
                  </p>
                </RevealSection>

                <div className="grid grid-cols-3 gap-6">
                  {[
                    {
                      icon: 'chart-bars',
                      title: 'Weighted Scoring',
                      bullets: [
                        'Each spec assigned a weight (1–10) based on criticality',
                        'Required specs act as pass/fail gates',
                        'Score = matched points / max possible × 100%',
                        'Missing specs score 0 — no free points',
                      ],
                    },
                    {
                      icon: 'compare',
                      title: 'Match Types',
                      bullets: [
                        'Exact Match — values must be identical',
                        'Numeric ±% — within tolerance percentage',
                        '≥ Target — candidate meets or exceeds',
                        'Range Covers — candidate range is equal or wider',
                        'Contains — partial text match',
                      ],
                    },
                    {
                      icon: 'view-grid',
                      title: 'Category Rules',
                      bullets: [
                        `${categories.length || 22} IC categories with dedicated rule sets`,
                        'Package, mounting, and temperature weights per category',
                        'Lifecycle status factored into scoring',
                        'Datasheet-extracted specs enrich DigiKey data',
                      ],
                    },
                  ].map(({ icon, title, bullets }, i) => (
                    <RevealSection key={title} delay={i * 100}>
                      <div className="border p-6 h-full flex flex-col"
                          style={{ borderColor: T.border, borderRadius: 10 }}>
                        <div className="w-9 h-9 flex items-center justify-center mb-4"
                          style={{ backgroundColor: T.primaryLight, borderRadius: 8 }}>
                          <DdsIcon name={icon} size={18} color="#0076CE" />
                        </div>
                        <h3 className="text-sm font-semibold mb-3" style={{ color: T.text }}>{title}</h3>
                        <ul className="space-y-2 flex-1">
                          {bullets.map(item => (
                            <li key={item} className="flex items-start gap-2">
                              <div className="w-1 h-1 rounded-full mt-1.5 flex-shrink-0" style={{ backgroundColor: '#0076CE' }} />
                              <span className="text-xs leading-relaxed" style={{ color: T.textSecondary }}>{item}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    </RevealSection>
                  ))}
                </div>

                <RevealSection delay={400}>
                  <div className="mt-10 text-center">
                    <button onClick={() => { setPage('methodology'); loadMatchingRules() }}
                      className="group inline-flex items-center gap-2 px-6 py-2.5 text-sm font-medium border transition-all hover:shadow-md hover:border-blue-300"
                      style={{ borderColor: T.border, color: '#0076CE', borderRadius: 8 }}>
                      <DdsIcon name="book-open" size={16} color="#0076CE" />
                      View Detailed Methodology
                      <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
                    </button>
                  </div>
                </RevealSection>
              </div>
            </section>

            <div className="h-px" style={{ backgroundColor: T.border }} />
          </div>
        )}

        {/* ══════════════ METHODOLOGY ══════════════ */}
        {page === 'methodology' && (
          <div className="space-y-6">
            <SectionHeader dds="book-open" title="Matching Rules & Methodology"
              subtitle="How the IC Alternative Finder scores compatibility across categories" />

            <Card className="p-5">
              <h3 className="text-sm font-semibold text-slate-900 mb-3">How Scoring Works</h3>
              <div className="text-xs text-slate-500 space-y-2 leading-relaxed">
                <p>For each candidate in the same category, every electrical specification is compared using a weighted scoring system. Required specs must pass — if they fail, the candidate is disqualified regardless of other scores.</p>
                <p><strong>Score = sum(matched_spec_points) / sum(max_possible_points) × 100%</strong></p>
                <p>Missing specs score 0 (no free points). Stock and price do NOT affect scoring — purely technical.</p>
              </div>
              <div className="grid grid-cols-5 gap-2 mt-4">
                {[{ label: 'Exact Match', desc: 'Values must be identical', color: '#0076CE' },
                  { label: 'Numeric ±%', desc: 'Within tolerance percentage', color: '#0284C7' },
                  { label: '≥ Target', desc: 'Candidate meets or exceeds', color: '#16A34A' },
                  { label: 'Range Covers', desc: 'Candidate range is equal or wider', color: '#14B8A6' },
                  { label: 'Contains', desc: 'Partial text match', color: '#CA8A04' },
                ].map(({ label, desc, color }) => (
                  <div key={label} className="  p-3 bg-slate-50">
                    <div className="w-2 h-2   mb-2" style={{ backgroundColor: color }} />
                    <p className="text-xs font-semibold text-slate-700">{label}</p>
                    <p className="text-[10px] text-slate-500 mt-0.5">{desc}</p>
                  </div>
                ))}
              </div>
            </Card>

            {matchingRules.length === 0 ? (
              <Card className="p-12 text-center">
                <BookOpen className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                <p className="text-sm text-slate-500">Loading matching rules...</p>
              </Card>
            ) : (
              <div className="space-y-3">
                {matchingRules.map(rule => (
                  <Card key={rule.slug}>
                    <div className="p-4 cursor-pointer flex items-center justify-between"
                      onClick={() => setExpandedRule(expandedRule === rule.slug ? null : rule.slug)}>
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-semibold text-slate-900">{rule.name}</h3>
                          <span className="px-2 py-0.5 bg-slate-100 text-slate-500 text-[10px]   font-medium">
                            {rule.specs.length} specs
                          </span>
                          <span className="px-2 py-0.5 bg-blue-50 text-[10px]   font-medium" style={{ color: T.primary }}>
                            {rule.specs.filter(s => s.required).length} required
                          </span>
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5">{rule.description}</p>
                      </div>
                      <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${expandedRule === rule.slug ? 'rotate-180' : ''}`} />
                    </div>

                    {expandedRule === rule.slug && (
                      <div className="border-t px-4 pb-4 pt-3" style={{ borderColor: T.border }}>
                        <div className="flex gap-6">
                          <div className="flex-1">
                            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-2">Electrical Spec Rules</p>
                            <table className="w-full text-xs">
                              <thead><tr className="text-slate-400">
                                <th className="text-left py-1 font-normal">Specification</th>
                                <th className="text-center py-1 font-normal">Weight</th>
                                <th className="text-left py-1 font-normal">Match Type</th>
                                <th className="text-center py-1 font-normal">Tolerance</th>
                                <th className="text-center py-1 font-normal">Required</th>
                              </tr></thead>
                              <tbody>
                                {rule.specs.sort((a, b) => b.weight - a.weight).map(spec => (
                                  <tr key={spec.name} className="border-t" style={{ borderColor: T.border }}>
                                    <td className="py-1.5">
                                      {spec.required && <span className="text-red-500 font-bold">* </span>}
                                      <span className="text-slate-700">{spec.name}</span>
                                      {spec.aliases.length > 0 && (
                                        <span className="text-slate-400 ml-1 text-[10px]">({spec.aliases.join(', ')})</span>
                                      )}
                                    </td>
                                    <td className="py-1.5 text-center">
                                      <span className="inline-block w-8 h-5 rounded text-[10px] font-bold flex items-center justify-center"
                                        style={{ backgroundColor: spec.weight >= 8 ? '#FEF2F2' : spec.weight >= 5 ? '#FEFCE8' : '#F0FDF4',
                                          color: spec.weight >= 8 ? T.danger : spec.weight >= 5 ? T.warning : T.success }}>
                                        {spec.weight}
                                      </span>
                                    </td>
                                    <td className="py-1.5 text-slate-500">{matchTypeLabel[spec.match_type] || spec.match_type}</td>
                                    <td className="py-1.5 text-center text-slate-500">
                                      {spec.match_type === 'numeric_close' ? `±${spec.tolerance_pct}%` : '—'}
                                    </td>
                                    <td className="py-1.5 text-center">
                                      {spec.required ? <CheckCircle className="w-4 h-4 inline" style={{ color: T.danger }} />
                                        : <span className="text-slate-300">—</span>}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                            <p className="text-[10px] text-slate-400 mt-2">
                              <span className="text-red-500 font-bold">*</span> = required (fail = candidate disqualified)
                            </p>
                          </div>

                          {/* Radar preview */}
                          <div className="w-56 flex-shrink-0">
                            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-2">Weight Distribution</p>
                            <ResponsiveContainer width="100%" height={200}>
                              <RadarChart data={rule.specs.map(s => ({
                                spec: s.name.length > 12 ? s.name.slice(0, 12) + '…' : s.name,
                                weight: s.weight,
                              }))}>
                                <PolarGrid stroke="#E2E8F0" />
                                <PolarAngleAxis dataKey="spec" tick={{ fill: T.textMuted, fontSize: 8 }} />
                                <PolarRadiusAxis domain={[0, 10]} tick={false} axisLine={false} />
                                <Radar dataKey="weight" stroke={T.primary} fill={T.primary} fillOpacity={0.15} strokeWidth={1.5} />
                              </RadarChart>
                            </ResponsiveContainer>
                            <div className="mt-2 space-y-1 text-[10px] text-slate-500">
                              <div className="flex justify-between"><span>Package weight:</span><span className="font-mono">{rule.package_weight}</span></div>
                              <div className="flex justify-between"><span>Mounting weight:</span><span className="font-mono">{rule.mount_weight}</span></div>
                              <div className="flex justify-between"><span>Temperature weight:</span><span className="font-mono">{rule.temp_weight}</span></div>
                              <div className="flex justify-between"><span>Lifecycle weight:</span><span className="font-mono">{rule.lifecycle_weight}</span></div>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ══════════════ DASHBOARD ══════════════ */}
        {page === 'dashboard' && dashboard && (
          <div className="space-y-6">
            <SectionHeader dds="dashboard" title="Database Overview"
              subtitle={`${dashboard.total.toLocaleString()} components across ${Object.keys(dashboard.categories).length} categories`} />
            <div className="grid grid-cols-4 gap-4">
              <KpiCard label="Total Components" value={dashboard.total.toLocaleString()} icon={Database} />
              <KpiCard label="Categories" value={Object.keys(dashboard.categories).length} icon={Layers} />
              <KpiCard label="Active Parts" value={(dashboard.lifecycle_breakdown['Active'] || 0).toLocaleString()} icon={CheckCircle} />
              <KpiCard label="Manufacturers" value={topMfrs.length + '+'} icon={Activity} />
            </div>
            <div className="grid grid-cols-5 gap-6">
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
              <Card className="col-span-2 p-5">
                <h3 className="text-sm font-semibold text-slate-900 mb-4">Lifecycle Status</h3>
                <ResponsiveContainer width="100%" height={380}>
                  <PieChart>
                    <Pie data={Object.entries(dashboard.lifecycle_breakdown).map(([name, value]) => ({ name, value }))}
                      cx="50%" cy="45%" outerRadius={100} innerRadius={55} dataKey="value" paddingAngle={2} strokeWidth={0}>
                      {Object.keys(dashboard.lifecycle_breakdown).map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                    </Pie>
                    <Tooltip contentStyle={tooltipStyle} />
                    <Legend wrapperStyle={{ fontSize: 11, color: T.textMuted }} />
                  </PieChart>
                </ResponsiveContainer>
              </Card>
            </div>
            <div><h3 className="text-sm font-semibold text-slate-900 mb-3">Browse by Category</h3>
              <div className="grid grid-cols-4 gap-3">
                {categories.filter(c => c.count > 0).sort((a, b) => b.count - a.count).map(cat => (
                  <button key={cat.slug} onClick={() => loadBrowse(cat.slug)}
                    className="text-left p-4 border border-slate-200 bg-white hover:border-blue-300 hover:shadow-sm transition-all">
                    <p className="text-xs font-medium text-slate-500">{cat.name}</p>
                    <p className="text-lg font-semibold text-slate-900 mt-1">{cat.count.toLocaleString()}</p>
                  </button>))}
              </div>
            </div>
          </div>
        )}

        {/* ══════════════ BROWSE ══════════════ */}
        {page === 'browse' && (
          <div className="space-y-4">
            <SectionHeader dds="view-grid" title="Browse Components" />
            <div className="flex items-center gap-4 mb-4">
              <select value={browseCat} onChange={e => loadBrowse(e.target.value)}
                className="px-3 py-2   text-sm bg-white border border-slate-200 text-slate-900">
                <option value="">Select category</option>
                {categories.filter(c => c.count > 0).map(c => <option key={c.slug} value={c.slug}>{c.name} ({c.count})</option>)}
              </select>
              <span className="text-xs text-slate-500">{browseTotal > 0 ? `${browseTotal.toLocaleString()} parts` : ''}</span>
            </div>
            {browseParts.length > 0 && (
              <Card><div className="overflow-x-auto"><table className="w-full text-sm">
                <thead><tr className="border-b text-xs text-slate-500" style={{ borderColor: T.border }}>
                  <th className="text-left px-4 py-3 font-medium">MPN</th><th className="text-left px-4 py-3 font-medium">Manufacturer</th>
                  <th className="text-left px-4 py-3 font-medium">Description</th><th className="text-left px-4 py-3 font-medium">Status</th>
                  <th className="text-left px-4 py-3 font-medium">Package</th><th className="px-4 py-3"></th>
                </tr></thead><tbody>
                  {browseParts.map((p: any) => (
                    <tr key={p.manufacturer_part_number} className="border-b hover:bg-slate-50 cursor-pointer transition-colors"
                      style={{ borderColor: T.border }} onClick={() => selectPart(p.manufacturer_part_number)}>
                      <td className="px-4 py-3 font-mono text-xs font-medium" style={{ color: T.primary }}>{p.manufacturer_part_number}</td>
                      <td className="px-4 py-3 text-xs">{p.manufacturer}</td>
                      <td className="px-4 py-3 text-xs text-slate-500 truncate max-w-xs">{p.description}</td>
                      <td className="px-4 py-3"><LifecycleBadge status={p.lifecycle_status} /></td>
                      <td className="px-4 py-3 text-xs text-slate-500">{p.package}</td>
                      <td className="px-4 py-3"><ArrowRight className="w-3.5 h-3.5 text-slate-400" /></td>
                    </tr>))}
                </tbody></table></div></Card>
            )}
          </div>
        )}

        {/* ══════════════ SEARCH ══════════════ */}
        {page === 'search' && (
          <div><SectionHeader dds="search" title="Search Components" subtitle="Enter a part number or keyword to find components" />
            {searchResults.length > 0 && (
              <Card><div className="px-5 py-3 border-b" style={{ borderColor: T.border }}>
                <p className="text-sm font-medium text-slate-900">{searchResults.length} results for "{query}"</p></div>
                <div className="overflow-x-auto"><table className="w-full text-sm">
                  <thead><tr className="border-b text-xs text-slate-500" style={{ borderColor: T.border }}>
                    <th className="text-left px-4 py-2.5 font-medium">MPN</th><th className="text-left px-4 py-2.5 font-medium">Manufacturer</th>
                    <th className="text-left px-4 py-2.5 font-medium">Category</th><th className="text-left px-4 py-2.5 font-medium">Status</th>
                    <th className="px-4 py-2.5"></th></tr></thead><tbody>
                    {searchResults.map(p => (
                      <tr key={p.mpn} className="border-b hover:bg-slate-50 cursor-pointer transition-colors"
                        style={{ borderColor: T.border }} onClick={() => selectPart(p.mpn)}>
                        <td className="px-4 py-3 font-mono text-xs font-medium" style={{ color: T.primary }}>{p.mpn}</td>
                        <td className="px-4 py-3 text-xs">{p.manufacturer}</td>
                        <td className="px-4 py-3 text-xs text-slate-500">{p.category}</td>
                        <td className="px-4 py-3"><LifecycleBadge status={p.lifecycle_status} /></td>
                        <td className="px-4 py-3"><ArrowRight className="w-3.5 h-3.5 text-slate-400" /></td>
                      </tr>))}
                  </tbody></table></div></Card>
            )}
            {searchResults.length === 0 && query && <Card className="p-12 text-center"><Search className="w-10 h-10 text-slate-300 mx-auto mb-3" />
              <p className="text-sm text-slate-500">No results found for "{query}"</p></Card>}
            {!query && <Card className="p-12 text-center"><Search className="w-10 h-10 text-slate-300 mx-auto mb-3" />
              <p className="text-sm text-slate-500">Enter a part number or keyword above to search</p></Card>}
          </div>
        )}

        {/* ══════════════ ALTERNATIVES ══════════════ */}
        {page === 'alternatives' && selectedPart && (
          <div className="space-y-5">
            <SectionHeader dds="bolt" title="Alternative Finder" subtitle={`Alternatives for ${selectedPart.mpn}`} />
            <Card className="p-5">
              <div className="flex justify-between items-start">
                <div><div className="flex items-center gap-2 mb-1">
                  <h3 className="text-base font-semibold font-mono" style={{ color: T.primary }}>{selectedPart.mpn}</h3>
                  <LifecycleBadge status={selectedPart.lifecycle_status} /></div>
                  <p className="text-sm text-slate-500">{selectedPart.description}</p>
                  <p className="text-xs text-slate-400 mt-1">{selectedPart.manufacturer} · {selectedPart.category} · {selectedPart.package}</p>
                </div>
                {selectedPart.datasheet_url && <a href={selectedPart.datasheet_url} target="_blank" rel="noreferrer"
                  className="text-xs flex items-center gap-1 px-3 py-1.5 rounded-md border border-slate-200 hover:bg-slate-50"
                  style={{ color: T.primary }}><ExternalLink className="w-3 h-3" /> Datasheet</a>}
              </div>
              {Object.keys(selectedPart.specs || {}).length > 0 && (
                <div className="mt-4 grid grid-cols-4 gap-2">
                  {Object.entries(selectedPart.specs).sort().filter(([, v]) => v && v !== '-').slice(0, 16).map(([k, v]) => (
                    <div key={k} className="rounded-md px-3 py-2 bg-slate-50">
                      <p className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">{k}</p>
                      <p className="text-xs font-medium text-slate-700 mt-0.5">{v}</p></div>))}
                </div>)}
            </Card>
            {alternatives.length > 3 && (
              <Card className="p-5"><h3 className="text-sm font-semibold text-slate-900 mb-3">Compatibility Overview</h3>
                <ResponsiveContainer width="100%" height={180}>
                  <ScatterChart margin={{ left: 10, right: 10, top: 10, bottom: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                    <XAxis type="number" dataKey="idx" name="Rank" tick={{ fill: T.textMuted, fontSize: 10 }} />
                    <YAxis type="number" dataKey="pct" name="Compat" domain={[0, 100]} tick={{ fill: T.textMuted, fontSize: 10 }} />
                    <ZAxis range={[50, 180]} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Scatter data={alternatives.map((a, i) => ({ idx: i + 1, pct: Math.round(a.compatibility_pct), name: a.mpn }))}>
                      {alternatives.map((a, i) => <Cell key={i} fill={a.compatibility_pct >= 80 ? T.success : a.compatibility_pct >= 50 ? T.warning : T.danger} />)}
                    </Scatter>
                  </ScatterChart>
                </ResponsiveContainer>
              </Card>
            )}
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-semibold text-slate-900">{alternatives.length} Compatible Alternatives</p>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <label>Min:</label>
                <input type="range" min={0} max={90} value={minCompat} onChange={e => setMinCompat(Number(e.target.value))} className="w-20" />
                <span className="font-mono w-8">{minCompat}%</span>
                <button onClick={() => selectPart(selectedPart.mpn)} className="px-3 py-1 rounded-md text-xs font-medium ml-2 border border-slate-200 hover:bg-slate-50"
                  style={{ color: T.primary }}><RefreshCw className="w-3 h-3 inline mr-1" />Refresh</button>
              </div>
            </div>
            {alternatives.map((alt, idx) => (
              <Card key={alt.mpn} className={expandedAlt === idx ? 'ring-1 ring-blue-200' : ''}>
                <div className="flex items-start gap-4 p-4 cursor-pointer" onClick={() => setExpandedAlt(expandedAlt === idx ? null : idx)}>
                  <CompatBadge pct={alt.compatibility_pct} />
                          {/* Supply Chain Data */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-xs font-bold text-slate-400">#{idx + 1}</span>
                      <span className="font-mono text-sm font-semibold" style={{ color: T.primary }}>{alt.mpn}</span>
                      {alt.is_drop_in && <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-emerald-50 text-emerald-600 uppercase tracking-wider">Drop-In</span>}
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
                {expandedAlt === idx && (

                  
                    <>
                    {/* DROP-IN CHECKLIST */}
                    {alt.drop_in_checklist && (
                      <div className="px-4 pt-3 pb-2">
                        <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-2">
                          Drop-In Checklist
                        </p>
                        <div className="grid grid-cols-4 gap-2">
                          {[
                            {
                              label: 'Package Match',
                              pass: alt.drop_in_checklist.package_match,
                              detail: alt.drop_in_checklist.package_match
                                ? alt.drop_in_checklist.target_package
                                : (alt.drop_in_checklist.target_package || '') + ' \u2260 ' + (alt.drop_in_checklist.candidate_package || '')
                            },
                            {
                              label: 'Mounting Type',
                              pass: alt.drop_in_checklist.mounting_match,
                              detail: alt.drop_in_checklist.mounting_match ? 'Same' : 'Different'
                            },
                            {
                              label: 'Required Specs',
                              pass: alt.drop_in_checklist.required_specs_pass,
                              detail: alt.drop_in_checklist.required_specs_pass ? 'All pass' : 'Some fail'
                            },
                            {
                              label: 'Lifecycle',
                              
                              pass: alt.drop_in_checklist.lifecycle_active,
                              detail: alt.lifecycle_status || 'Unknown'
                            },
                          ].map(({ label, pass: ok, detail }) => (
                            <div key={label}  className="flex items-start gap-2 p-2 rounded"
                                 style={{ backgroundColor: ok ? '#F0FDF4' : '#FEF2F2' }}>
                              {ok
                                ? <CheckCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" style={{ color: '#16A34A' }} />
                                : <XCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" style={{ color: '#DC2626' }} />}
                              <div>
                                <p className="text-[11px] font-medium text-slate-700">{label}</p>
                                <p className="text-[10px] text-slate-500">{detail}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                        <div className="mt-2 px-3 py-2 rounded text-xs"
                             style={{
                               backgroundColor: alt.is_drop_in ? '#F0FDF4' : '#FFFBEB',
                               color: alt.is_drop_in ? '#16A34A' : '#CA8A04',
                               border: '1px solid ' + (alt.is_drop_in ? '#BBF7D0' : '#FDE68A'),
                             }}>
                          {alt.is_drop_in
                            ? '\u2713 Drop-in replacement \u2014 same package, same mounting, all required specs match.'
                            : '\u26A0 Not a direct drop-in \u2014 verify package, pinout, and footprint before substitution.'}
                        </div>
                      </div>
                  )}
<div className="border-t px-4 pb-4 pt-2 flex gap-6" style={{ borderColor: T.border }}>
                    <div className="flex-1">
                      <table className="w-full text-xs"><thead><tr className="text-slate-400">
                        <th className="text-left py-1.5 font-normal">Spec</th><th className="text-left py-1.5 font-normal">Target</th>
                        <th className="text-left py-1.5 font-normal">Candidate</th><th className="text-center py-1.5 font-normal">Match</th>
                        <th className="text-right py-1.5 font-normal">Score</th>
                      </tr></thead><tbody>
                        {Object.entries(alt.spec_scores).sort(([, a]: any, [, b]: any) => b.max - a.max).map(([name, d]: [string, any]) => (
                          <tr key={name} className="border-t" style={{ borderColor: T.border }}>
                            <td className="py-1.5">{d.required && <span className="text-red-500 font-bold">* </span>}<span className="text-slate-700">{name}</span></td>
                            <td className="py-1.5 font-mono text-slate-500">{d.target === '-' || d.target === 'n/a' ? <span className="text-slate-300 italic">n/a</span> : d.target}</td>
                            <td className="py-1.5 font-mono text-slate-500">{d.candidate === '-' || d.candidate === 'n/a' ? <span className="text-slate-300 italic">n/a</span> : d.candidate}</td>
                            <td className="py-1.5 text-center"><StatusDot status={d.status} /></td>
                            <td className="py-1.5 text-right font-mono text-slate-400">{d.score.toFixed(0)}/{d.max.toFixed(0)}</td>
                          </tr>))}
                      </tbody></table>
                    </div>
                    {Object.keys(alt.spec_scores).length > 2 && (
                      <div className="w-60 flex-shrink-0">
                        <ResponsiveContainer width="100%" height={220}>
                          <RadarChart data={Object.entries(alt.spec_scores).map(([name, d]: [string, any]) => ({
                            spec: name.length > 12 ? name.slice(0, 12) + '…' : name,
                            score: d.max > 0 ? (d.score / d.max) * 100 : 0 }))}>
                            <PolarGrid stroke="#E2E8F0" /><PolarAngleAxis dataKey="spec" tick={{ fill: T.textMuted, fontSize: 9 }} />
                            <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                            <Radar dataKey="score" stroke={T.primary} fill={T.primary} fillOpacity={0.15} strokeWidth={1.5} />
                          </RadarChart>
                        </ResponsiveContainer>
                      </div>)}
                    </div>

                    {/* Supply Chain Data */}
                    <div className="px-4 pb-4">
                      <button
                        onClick={(e) => { e.stopPropagation(); loadSupplyChain(alt.mpn, idx) }}
                        className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-md border transition-colors hover:bg-slate-50"
                        style={{ borderColor: T.border, color: T.primary }}>
                        <Layers className="w-3.5 h-3.5" />
                        {showSupplyChain === idx ? 'Hide' : 'View'} Supply Chain Data
                      </button>

                      {showSupplyChain === idx && supplyChainData[alt.mpn] && (
                        <div className="mt-3">
                          {!supplyChainData[alt.mpn].available ? (
                            <p className="text-xs text-slate-400 italic">No supply chain data available for this part.</p>
                          ) : (
                            <div className="border   p-4" style={{ borderColor: T.border, backgroundColor: T.bgAlt }}>
                              <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-3">
                                Supply Chain Data
                              </p>
                              <div className="grid grid-cols-3 gap-3">
                                {supplyChainData[alt.mpn].entries.map((entry: any, i: number) => (
                                  <React.Fragment key={i}>
                                    <div className="p-3 rounded bg-white border" style={{ borderColor: T.border }}>
                                      <p className="text-[10px] text-slate-400 uppercase font-medium">Sourcing</p>
                                      <p className="text-sm font-semibold mt-1" style={{
                                        color: (entry.sourcing || '').toLowerCase().includes('multi') ? T.success
                                             : (entry.sourcing || '').toLowerCase() === 'sole' ? T.danger
                                             : T.warning
                                      }}>{entry.sourcing || 'Unknown'}</p>
                                    </div>
                                    {entry.lead_time_days && (
                                      <div className="p-3 rounded bg-white border" style={{ borderColor: T.border }}>
                                        <p className="text-[10px] text-slate-400 uppercase font-medium">Lead Time</p>
                                        <p className="text-sm font-semibold mt-1">{entry.lead_time_days} days</p>
                                      </div>
                                    )}
                                    {entry.moq && (
                                      <div className="p-3 rounded bg-white border" style={{ borderColor: T.border }}>
                                        <p className="text-[10px] text-slate-400 uppercase font-medium">MOQ</p>
                                        <p className="text-sm font-semibold mt-1">{Number(entry.moq).toLocaleString()}</p>
                                      </div>
                                    )}
                                    {entry.pin_count && (
                                      <div className="p-3 rounded bg-white border" style={{ borderColor: T.border }}>
                                        <p className="text-[10px] text-slate-400 uppercase font-medium">Pin Count</p>
                                        <p className="text-sm font-semibold mt-1">{entry.pin_count} pins</p>
                                      </div>
                                    )}
                                    <div className="p-3 rounded bg-white border" style={{ borderColor: T.border }}>
                                      <p className="text-[10px] text-slate-400 uppercase font-medium">Dual Fab</p>
                                      <p className="text-sm font-semibold mt-1" style={{
                                        color: entry.dual_fab_plan === 'Y' ? T.success : T.warning
                                      }}>{entry.dual_fab_plan === 'Y' ? 'Yes' : 'No'}</p>
                                    </div>
                                    {entry.fab1 && (
                                      <div className="p-3 rounded bg-white border" style={{ borderColor: T.border }}>
                                        <p className="text-[10px] text-slate-400 uppercase font-medium">Primary Fab</p>
                                        <p className="text-xs font-medium mt-1">{entry.fab1.supplier}</p>
                                        <p className="text-[10px] text-slate-500">{entry.fab1.country}</p>
                                      </div>
                                    )}
                                    {entry.p2p_solution && (
                                      <div className="p-3 rounded border col-span-3"
                                           style={{ borderColor: '#BBF7D0', backgroundColor: T.successBg }}>
                                        <p className="text-[10px] uppercase font-medium" style={{ color: T.success }}>
                                          P2P Solution Available
                                        </p>
                                        <p className="text-xs font-medium mt-1" style={{ color: T.success }}>
                                          {entry.p2p_solution.supplier}: {entry.p2p_solution.mpn}
                                        </p>
                                      </div>
                                    )}
                                    <div className="col-span-3 flex justify-between text-[10px] text-slate-400 italic mt-1">
                                      <span>ODM: {entry.odm}</span>
                                      <span>* Based on template data dated {entry.template_date}</span>
                                    </div>
                                  </React.Fragment>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    </>
                  )}
              </Card>))}
          </div>
        )}

        {/* ══════════════ COMPARE ══════════════ */}
        {page === 'compare' && (
          <div className="space-y-5">
            <SectionHeader dds="compare" title="Side-by-Side Comparison" subtitle="Compare two parts across all specifications" />
            <Card className="p-5">
              <div className="grid grid-cols-2 gap-4 mb-4">
                <input value={cmpMpn1} onChange={e => setCmpMpn1(e.target.value)} placeholder="Part 1 (e.g. MIC5501-3.0YM5-TR)"
                  className="px-3 py-2   text-sm bg-slate-50 border border-slate-200 text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20" />
                <input value={cmpMpn2} onChange={e => setCmpMpn2(e.target.value)} placeholder="Part 2 (e.g. AP2112K-3.3TRG1)"
                  className="px-3 py-2   text-sm bg-slate-50 border border-slate-200 text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20" />
              </div>
              <button onClick={runCompare} disabled={loading || !cmpMpn1 || !cmpMpn2}
                className="px-5 py-2   text-sm font-medium text-white disabled:opacity-50" style={{ backgroundColor: T.primary }}>Compare</button>
            </Card>
            {cmpResult && (
              <Card><div className="overflow-x-auto"><table className="w-full text-sm">
                <thead><tr className="border-b text-xs text-slate-500" style={{ borderColor: T.border }}>
                  <th className="text-left px-4 py-2.5 font-medium">Parameter</th>
                  <th className="text-left px-4 py-2.5 font-mono font-medium" style={{ color: T.primary }}>{cmpResult.part_a.mpn}</th>
                  <th className="text-left px-4 py-2.5 font-mono font-medium" style={{ color: T.accent }}>{cmpResult.part_b.mpn}</th>
                  <th className="text-center px-4 py-2.5 font-medium">Match</th>
                </tr></thead><tbody>
                  {['manufacturer', 'category', 'package', 'mounting_type', 'lifecycle_status'].map(field => {
                    const va = cmpResult.part_a[field] || '-', vb = cmpResult.part_b[field] || '-'
                    const match = va.toLowerCase() === vb.toLowerCase()
                    return <tr key={field} className="border-b" style={{ borderColor: T.border }}>
                      <td className="px-4 py-2.5 capitalize text-slate-500 text-xs">{field.replace('_', ' ')}</td>
                      <td className="px-4 py-2.5 text-xs">{va}</td><td className="px-4 py-2.5 text-xs">{vb}</td>
                      <td className="px-4 py-2.5 text-center">{match ? <CheckCircle className="w-4 h-4 inline" style={{ color: T.success }} />
                        : <XCircle className="w-4 h-4 inline" style={{ color: T.danger }} />}</td></tr>})}
                  <tr><td colSpan={4} className="px-4 py-1.5 text-[10px] font-semibold uppercase tracking-widest text-slate-400 border-t" style={{ borderColor: T.border }}>Specifications</td></tr>
                  {cmpResult.all_spec_names.map((spec: string) => {
                    const va = cmpResult.part_a.specs[spec] || '-', vb = cmpResult.part_b.specs[spec] || '-'
                    const match = va.toLowerCase() === vb.toLowerCase()
                    return <tr key={spec} className="border-b" style={{ borderColor: T.border }}>
                      <td className="px-4 py-2 text-xs text-slate-500">{spec}</td>
                      <td className="px-4 py-2 text-xs font-mono">{va}</td><td className="px-4 py-2 text-xs font-mono">{vb}</td>
                      <td className="px-4 py-2 text-center">{match ? <CheckCircle className="w-4 h-4 inline" style={{ color: T.success }} />
                        : <AlertCircle className="w-4 h-4 inline" style={{ color: T.warning }} />}</td></tr>})}
                </tbody></table></div></Card>)}
          </div>
        )}

        {/* ══════════════ GRAPH ══════════════ */}
        {page === 'graph' && (
          <div className="space-y-5">
            <SectionHeader dds="network-connected" title="Compatibility Network"
              subtitle={selectedPart ? `${alternatives.length} alternatives for ${selectedPart.mpn}` : 'Search for a part first'} />
            {selectedPart && alternatives.length > 0 ? (
              <>
                <Card className="p-4">
                  <div className="flex gap-4 text-xs text-slate-500 mb-3">
                    <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded-full border-2" style={{ borderColor: T.primary, backgroundColor: T.primaryLight }} /> Target part</div>
                    <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded-full border-2" style={{ borderColor: T.success }} /> Active</div>
                    <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded-full border-2" style={{ borderColor: T.danger }} /> Obsolete</div>
                    <div className="flex items-center gap-1.5"><span className="text-emerald-600 font-bold text-[9px] bg-emerald-50 px-1 rounded">DROP-IN</span> Same package + all specs</div>
                    <div className="flex items-center gap-1.5"><span className="w-4 border-t-2 border-dashed" style={{ borderColor: '#94A3B8' }} /> Different package</div>
                    <div className="flex items-center gap-1.5"><span className="w-4 border-t-2" style={{ borderColor: '#94A3B8' }} /> Same package</div>
                  </div>
                  <CompatibilityGraph target={selectedPart} alternatives={alternatives} />
                </Card>
                <Card className="p-4">
                  <p className="text-xs text-slate-500">
                    <strong>How to read:</strong> Node size reflects compatibility %. Line thickness = compatibility strength.
                    Solid lines = same package (potential drop-in). Dashed lines = different package.
                    Green nodes = Active lifecycle. Red = Obsolete. Inner dot = matching package footprint.
                  </p>
                </Card>
              </>
            ) : (
              <Card className="p-12 text-center">
                <Network className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                <p className="text-sm text-slate-500">Search for a part and find alternatives first to see the compatibility network graph.</p>
              </Card>
            )}
          </div>
        )}
      </main>

      <footer className="border-t px-6 py-4 mt-8" style={{ borderColor: T.border }}>
        <div className="max-w-[1400px] mx-auto flex justify-between items-center">
          <span className="text-xs text-slate-400">IC Alternative Finder · {dashboard?.total.toLocaleString() || '...'} components · {Object.keys(dashboard?.categories || {}).length} categories</span>
          <span className="text-xs text-slate-400">© 2026 Dell Technologies. All rights reserved.</span>
        </div>
      </footer>
    </div>
  )
}
