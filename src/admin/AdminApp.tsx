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
  const offset = useRef(0)
  const logEnd = useRef<HTMLPreElement>(null)

  const load = async () => {
    try {
      const [t, j] = await Promise.all([adminApi.tasks(), adminApi.jobs()])
      setTasks(t.data.tasks); setCategories(t.data.categories); setJobs(j.data)
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

        <section className="bg-white border border-slate-200 rounded-lg p-4 self-start">
          <h2 className="font-medium mb-3">Run a task</h2>
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
