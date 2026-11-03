import { useEffect, useRef, useState } from 'react'
import { Play, Square, Terminal, ArrowLeft, KeyRound, Loader2 } from 'lucide-react'
import { adminApi, getAdminToken, setAdminToken } from '../api'

type Param = {
  type: 'int' | 'float' | 'bool' | 'categories' | 'categories_single'
  label: string; default?: number | boolean; min?: number
}
type Task = { label: string; description: string; params: Record<string, Param> }
type Job = {
  id: string; task: string; label: string; command: string; status: string
  started_at: number; finished_at: number | null; exit_code: number | null
}

const STATUS_STYLE: Record<string, string> = {
  running: 'bg-blue-50 text-blue-700',
  succeeded: 'bg-emerald-50 text-emerald-700',
  failed: 'bg-red-50 text-red-700',
  cancelled: 'bg-slate-100 text-slate-600',
  interrupted: 'bg-amber-50 text-amber-700',
}

const errMsg = (e: any) =>
  e?.response?.data?.detail ?? (e?.response ? `HTTP ${e.response.status}` : 'Cannot reach backend on localhost:8000')

type Overview = {
  components: number; with_datasheet_url: number; parts_with_specs: number
  llm_enriched_parts: number; datasheet_pdfs_on_disk: number; llm_configured: boolean
  categories: { slug: string; name: string; count: number }[]
  datasheet_queue: Record<string, number>; supply_chain_mpns: number
}
type MpnResult = {
  received: number; queued: number; requeued: number; already_queued: number
  already_have_datasheet: number; invalid: string[]; invalid_count: number
}

function duration(j: Job) {
  const s = Math.round((j.finished_at ?? Date.now() / 1000) - j.started_at)
  return s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`
}

export default function AdminApp() {
  const [tasks, setTasks] = useState<Record<string, Task>>({})
  const [categories, setCategories] = useState<Record<string, string>>({})
  const [taskKey, setTaskKey] = useState('')
  const [values, setValues] = useState<Record<string, any>>({})
  const [jobs, setJobs] = useState<Job[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [log, setLog] = useState('')
  const [error, setError] = useState('')
  const [token, setToken] = useState(getAdminToken())
  const [overview, setOverview] = useState<Overview | null>(null)
  const [mpnText, setMpnText] = useState('')
  const [mpnFile, setMpnFile] = useState<File | null>(null)
  const [mpnCategory, setMpnCategory] = useState('')
  const [requeue, setRequeue] = useState(false)
  const [mpnResult, setMpnResult] = useState<MpnResult | null>(null)
  const [uploading, setUploading] = useState(false)
  const offset = useRef(0)
  const logEnd = useRef<HTMLPreElement>(null)

  const load = async () => {
    try {
      const [t, j, o] = await Promise.all([adminApi.tasks(), adminApi.jobs(), adminApi.overview()])
      setTasks(t.data.tasks); setCategories(t.data.categories); setJobs(j.data); setOverview(o.data)
      setTaskKey(k => k || Object.keys(t.data.tasks)[0])
      setError('')
    } catch (e) { setError(errMsg(e)) }
  }
  useEffect(() => { load() }, [])

  // Reset form defaults when the task changes
  useEffect(() => {
    const task = tasks[taskKey]
    if (!task) return
    setValues(Object.fromEntries(Object.entries(task.params).map(([k, p]) =>
      [k, p.type === 'categories' ? [] : p.type === 'categories_single' ? '' : p.default ?? ''])))
  }, [taskKey, tasks])

  // Poll jobs list + the selected job's log while anything is running
  const anyRunning = jobs.some(j => j.status === 'running')
  // Refresh DB stats when a job finishes
  const wasRunning = useRef(false)
  useEffect(() => {
    if (wasRunning.current && !anyRunning) adminApi.overview().then(o => setOverview(o.data)).catch(() => {})
    wasRunning.current = anyRunning
  }, [anyRunning])
  useEffect(() => {
    if (!anyRunning && !selected) return
    const id = setInterval(async () => {
      try {
        const j = await adminApi.jobs(); setJobs(j.data)
        if (selected) {
          const r = await adminApi.job(selected, offset.current)
          if (r.data.log) { offset.current = r.data.next_offset; setLog(l => l + r.data.log) }
        }
      } catch (e) { setError(errMsg(e)) }
    }, 2000)
    return () => clearInterval(id)
  }, [anyRunning, selected])

  useEffect(() => { logEnd.current?.scrollTo(0, logEnd.current.scrollHeight) }, [log])

  const openJob = (id: string) => { setSelected(id); setLog(''); offset.current = 0 }

  const start = async () => {
    try {
      const { data } = await adminApi.startJob(taskKey, values)
      setError(''); await load(); openJob(data.id)
    } catch (e) { setError(errMsg(e)) }
  }
  const submitMpns = async () => {
    const form = new FormData()
    form.append('text', mpnText); form.append('category', mpnCategory)
    form.append('requeue', String(requeue))
    if (mpnFile) form.append('file', mpnFile)
    setUploading(true); setMpnResult(null)
    try {
      const { data } = await adminApi.uploadMpns(form)
      setMpnResult(data); setError(''); setMpnText(''); setMpnFile(null)
      adminApi.overview().then(o => setOverview(o.data)).catch(() => {})
    } catch (e) { setError(errMsg(e)) }
    setUploading(false)
  }
  const submitTemplate = async (file: File) => {
    setUploading(true)
    try {
      const { data } = await adminApi.uploadSupplyChain(file)
      setError(''); await load(); openJob(data.id)
    } catch (e) { setError(errMsg(e)) }
    setUploading(false)
  }
  const cancel = async (id: string) => {
    try { await adminApi.cancelJob(id); await load() } catch (e) { setError(errMsg(e)) }
  }

  const task = tasks[taskKey]
  const setVal = (k: string, v: any) => setValues(s => ({ ...s, [k]: v }))
  const sel = jobs.find(j => j.id === selected)

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="bg-white border-b border-slate-200 px-6 py-3 flex items-center gap-4">
        <a href="#/" onClick={() => setTimeout(() => location.reload())} className="text-slate-500 hover:text-slate-800">
          <ArrowLeft className="w-5 h-5" />
        </a>
        <h1 className="text-lg font-medium">IC Finder — Admin</h1>
        <div className="ml-auto flex items-center gap-2 text-sm">
          <KeyRound className="w-4 h-4 text-slate-400" />
          <input type="password" placeholder="Admin token (optional on localhost)" value={token}
            onChange={e => setToken(e.target.value)}
            onBlur={() => { setAdminToken(token); load() }}
            className="border border-slate-300 rounded px-2 py-1 w-64" />
        </div>
      </header>

      <main className="max-w-6xl mx-auto p-6 grid gap-6 lg:grid-cols-[360px_1fr]">
        {error && <div className="lg:col-span-2 bg-red-50 text-red-700 border border-red-200 rounded px-4 py-2 text-sm">{error}</div>}

        {overview && (
          <section className="lg:col-span-2 bg-white border border-slate-200 rounded-lg p-4">
            <h2 className="font-medium mb-3">Database</h2>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
              {([
                ['Components', overview.components],
                ['With datasheet URL', overview.with_datasheet_url],
                ['With specs', overview.parts_with_specs],
                ['LLM-enriched', overview.llm_enriched_parts],
                ['PDFs on disk', overview.datasheet_pdfs_on_disk],
                ['Supply-chain MPNs', overview.supply_chain_mpns],
                ['Awaiting datasheet', overview.datasheet_queue.pending ?? 0],
              ] as [string, number][]).map(([label, n]) => (
                <div key={label} className="bg-slate-50 rounded p-3">
                  <div className="text-xs text-slate-500">{label}</div>
                  <div className="text-lg font-medium">{n.toLocaleString()}</div>
                  {!['Components', 'Supply-chain MPNs', 'Awaiting datasheet'].includes(label) && overview.components > 0 && (
                    <div className="text-xs text-slate-400">{Math.round(n * 100 / overview.components)}%</div>)}
                </div>))}
            </div>
            {!overview.llm_configured && (
              <p className="mt-3 text-xs text-amber-700 bg-amber-50 rounded px-2 py-1">
                No LLM API key set on the backend — enrichment tasks that use the LLM will fail.
              </p>)}
            <details className="mt-3 text-sm">
              <summary className="cursor-pointer text-slate-500">Parts per category</summary>
              <ul className="mt-2 grid sm:grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-1">
                {overview.categories.map(c => (
                  <li key={c.slug} className="flex justify-between border-b border-slate-100">
                    <span>{c.name}</span><span className="text-slate-500">{c.count.toLocaleString()}</span>
                  </li>))}
              </ul>
            </details>
          </section>)}

        <section className="lg:col-span-2 grid gap-6 md:grid-cols-2">
          <div className="bg-white border border-slate-200 rounded-lg p-4">
            <h2 className="font-medium mb-1">Update supply-chain data</h2>
            <p className="text-xs text-slate-500 mb-3">
              Upload an ODM golden template (.xlsx). It is imported into the supply-chain table;
              new MPNs are queued for datasheet lookup.
            </p>
            <input type="file" accept=".xlsx,.xls" disabled={uploading || anyRunning}
              onChange={e => { const f = e.target.files?.[0]; if (f) submitTemplate(f); e.target.value = '' }}
              className="block w-full text-sm file:mr-3 file:rounded file:border-0 file:bg-[#0076CE] file:text-white file:px-3 file:py-1.5 disabled:opacity-50" />
            {anyRunning && <p className="text-xs text-amber-700 mt-2">Wait for the running job to finish.</p>}
          </div>

          <div className="bg-white border border-slate-200 rounded-lg p-4">
            <h2 className="font-medium mb-1">Add new IC part numbers</h2>
            <p className="text-xs text-slate-500 mb-2">
              Paste MPNs (comma/space/line separated) and/or upload a .txt/.csv/.xlsx. They are queued for the datasheet fetcher.
            </p>
            <textarea value={mpnText} onChange={e => setMpnText(e.target.value)} rows={3} placeholder="LM1117-3.3, TPS62130RGTR, …"
              className="w-full border border-slate-300 rounded px-2 py-1 text-sm font-mono" />
            <div className="flex flex-wrap items-center gap-3 mt-2 text-sm">
              <input type="file" accept=".txt,.csv,.xlsx,.xls" onChange={e => setMpnFile(e.target.files?.[0] ?? null)} className="text-xs max-w-[14rem]" />
              <select value={mpnCategory} onChange={e => setMpnCategory(e.target.value)} className="border border-slate-300 rounded px-2 py-1">
                <option value="">Category: auto</option>
                {Object.entries(categories).map(([s, n]) => <option key={s} value={s}>{n}</option>)}
              </select>
              <label className="flex items-center gap-1 text-xs text-slate-600">
                <input type="checkbox" checked={requeue} onChange={e => setRequeue(e.target.checked)} /> Retry previously not-found
              </label>
              <button onClick={submitMpns} disabled={uploading || (!mpnText.trim() && !mpnFile)}
                className="ml-auto bg-[#0076CE] text-white rounded px-3 py-1.5 disabled:opacity-50">Queue</button>
            </div>
            {mpnResult && (
              <div className="mt-3 text-xs bg-emerald-50 text-emerald-800 rounded px-3 py-2 space-y-1">
                <p>{mpnResult.queued} queued{mpnResult.requeued ? `, ${mpnResult.requeued} re-queued` : ''} of {mpnResult.received} unique MPNs
                  ({mpnResult.already_queued} already queued, {mpnResult.already_have_datasheet} already have a datasheet).</p>
                {mpnResult.invalid_count > 0 && (
                  <p className="text-amber-700">Skipped {mpnResult.invalid_count} invalid: {mpnResult.invalid.join(', ')}{mpnResult.invalid_count > mpnResult.invalid.length ? '…' : ''}</p>)}
                {mpnResult.queued + mpnResult.requeued > 0 && (
                  <button onClick={() => { setTaskKey('fetch_datasheets'); window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }) }}
                    className="underline">Next: fetch datasheets →</button>)}
              </div>)}
          </div>
        </section>

        <section className="bg-white border border-slate-200 rounded-lg p-4 self-start">
          <h2 className="font-medium mb-3">Run a task</h2>
          <div className="flex flex-wrap gap-2 mb-3 text-xs">
            {([['fetch_datasheets', 'Datasheet fetcher'], ['enrich_supply_chain', 'LLM enrichment'], ['scrape', 'Scraper']] as [string, string][])
              .filter(([k]) => tasks[k]).map(([k, label]) => (
                <button key={k} onClick={() => setTaskKey(k)}
                  className={`px-2 py-1 rounded border ${taskKey === k ? 'bg-slate-800 text-white border-slate-800' : 'border-slate-300 text-slate-600 hover:bg-slate-50'}`}>
                  {label}
                </button>))}
          </div>
          <select value={taskKey} onChange={e => setTaskKey(e.target.value)}
            className="w-full border border-slate-300 rounded px-2 py-1.5 mb-2">
            {Object.entries(tasks).map(([k, t]) => <option key={k} value={k}>{t.label}</option>)}
          </select>
          {task && <p className="text-xs text-slate-500 mb-3">{task.description}</p>}

          <div className="space-y-3">
            {task && Object.entries(task.params).map(([k, p]) => (
              <label key={k} className="block text-sm">
                {p.type === 'bool' ? (
                  <span className="flex items-center gap-2">
                    <input type="checkbox" checked={!!values[k]} onChange={e => setVal(k, e.target.checked)} />
                    {p.label}
                  </span>
                ) : p.type === 'int' || p.type === 'float' ? (
                  <>
                    <span className="block text-slate-600 mb-1">{p.label}</span>
                    <input type="number" min={p.min} step={p.type === 'float' ? 'any' : 1}
                      value={values[k] ?? ''} onChange={e => setVal(k, e.target.value)}
                      className="w-full border border-slate-300 rounded px-2 py-1" />
                  </>
                ) : p.type === 'categories_single' ? (
                  <>
                    <span className="block text-slate-600 mb-1">{p.label}</span>
                    <select value={values[k] ?? ''} onChange={e => setVal(k, e.target.value)}
                      className="w-full border border-slate-300 rounded px-2 py-1">
                      <option value="">Select…</option>
                      {Object.entries(categories).map(([s, n]) => <option key={s} value={s}>{n}</option>)}
                    </select>
                  </>
                ) : (
                  <>
                    <span className="block text-slate-600 mb-1">{p.label}</span>
                    <div className={`max-h-40 overflow-y-auto border border-slate-300 rounded p-2 space-y-1 ${values.all ? 'opacity-40 pointer-events-none' : ''}`}>
                      {Object.entries(categories).map(([s, n]) => (
                        <span key={s} className="flex items-center gap-2">
                          <input type="checkbox" checked={(values[k] ?? []).includes(s)}
                            onChange={e => setVal(k, e.target.checked ? [...values[k], s] : values[k].filter((x: string) => x !== s))} />
                          {n}
                        </span>
                      ))}
                    </div>
                  </>
                )}
              </label>
            ))}
          </div>

          <button onClick={start} disabled={!task || anyRunning}
            className="mt-4 w-full flex items-center justify-center gap-2 bg-[#0076CE] text-white rounded py-2 disabled:opacity-50">
            {anyRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            {anyRunning ? 'A job is running' : 'Start'}
          </button>
        </section>

        <div className="space-y-6 min-w-0">
          <section className="bg-white border border-slate-200 rounded-lg p-4">
            <h2 className="font-medium mb-3">Jobs</h2>
            {jobs.length === 0 ? <p className="text-sm text-slate-400">No jobs yet.</p> : (
              <table className="w-full text-sm">
                <thead><tr className="text-left text-slate-400 text-xs">
                  <th className="py-1 font-normal">Task</th><th className="font-normal">Status</th>
                  <th className="font-normal">Started</th><th className="font-normal">Duration</th><th />
                </tr></thead>
                <tbody>
                  {jobs.map(j => (
                    <tr key={j.id} onClick={() => openJob(j.id)}
                      className={`border-t border-slate-100 cursor-pointer hover:bg-slate-50 ${j.id === selected ? 'bg-slate-50' : ''}`}>
                      <td className="py-1.5">{j.label}</td>
                      <td><span className={`px-2 py-0.5 rounded text-xs ${STATUS_STYLE[j.status] ?? ''}`}>{j.status}</span></td>
                      <td className="text-slate-500">{new Date(j.started_at * 1000).toLocaleString()}</td>
                      <td className="text-slate-500">{duration(j)}</td>
                      <td className="text-right">
                        {j.status === 'running' && (
                          <button onClick={e => { e.stopPropagation(); cancel(j.id) }}
                            className="inline-flex items-center gap-1 text-red-600 text-xs hover:underline">
                            <Square className="w-3 h-3" /> Cancel
                          </button>)}
                      </td>
                    </tr>))}
                </tbody>
              </table>)}
          </section>

          <section className="bg-white border border-slate-200 rounded-lg p-4">
            <h2 className="font-medium mb-2 flex items-center gap-2"><Terminal className="w-4 h-4" /> Log</h2>
            {sel && <p className="text-xs text-slate-500 font-mono mb-2 break-all">$ {sel.command}</p>}
            <pre ref={logEnd} className="bg-slate-900 text-slate-100 text-xs rounded p-3 h-80 overflow-auto whitespace-pre-wrap">
              {sel ? (log || 'No output yet…') : 'Select a job to see its output.'}
            </pre>
          </section>
        </div>
      </main>
    </div>
  )
}
