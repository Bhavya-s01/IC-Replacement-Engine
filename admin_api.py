"""
admin_api.py — Admin endpoints: run scraper/enricher scripts as background jobs.

Mounted by api.py under /api/admin. Jobs are subprocesses of the existing CLI
scripts (no extra database); metadata and logs live in admin_logs/.

Auth: send the ADMIN_TOKEN env var as the X-Admin-Token header. If ADMIN_TOKEN
is unset, only requests from localhost are accepted.
"""

import json
import os
import re
import secrets
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from config import CATEGORIES

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "admin_logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


def require_admin(request: Request):
    token = os.environ.get("ADMIN_TOKEN")
    if token:
        if not secrets.compare_digest(request.headers.get("x-admin-token", ""), token):
            raise HTTPException(401, "Invalid admin token")
    elif not request.client or request.client.host not in LOCAL_HOSTS:
        raise HTTPException(403, "Set ADMIN_TOKEN to use admin endpoints remotely")


router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])


# ── Task catalog ──
# Param type is int | float | bool | categories | categories_single; "flag" is the CLI flag.
TASKS: Dict[str, Dict[str, Any]] = {
    "scrape": {
        "label": "Scrape DigiKey",
        "description": "Scrape parametric data for selected categories into the database.",
        "script": "main.py", "base_args": ["scrape"],
        "params": {
            "category": {"type": "categories", "flag": "-c", "label": "Categories"},
            "all": {"type": "bool", "flag": "--all", "label": "All categories", "default": False},
            "max_pages": {"type": "int", "flag": "-m", "label": "Max pages", "default": 2, "min": 1},
        },
    },
    "fetch_datasheets": {
        "label": "Fetch datasheets",
        "description": "Download datasheet PDFs from DigiKey and optionally extract specs with the LLM.",
        "script": "fetch_datasheets.py", "base_args": [],
        "params": {
            "limit": {"type": "int", "flag": "--limit", "label": "Limit", "default": 30, "min": 1},
            "no_enrich": {"type": "bool", "flag": "--no-enrich", "label": "Skip LLM extraction", "default": False},
        },
    },
    "enrich_category": {
        "label": "Enrich category",
        "description": "Extract missing specs for one category from datasheets.",
        "script": "enrich_all.py", "base_args": ["--phase", "category"],
        "params": {
            "cat": {"type": "categories_single", "flag": "--cat", "label": "Category"},
            "limit": {"type": "int", "flag": "--limit", "label": "Limit", "default": 50, "min": 1},
        },
    },
    "enrich_supply_chain": {
        "label": "Enrich supply chain",
        "description": "Fetch supply-chain data (stock, lifecycle, pricing) for parts.",
        "script": "enrich_all.py", "base_args": ["--phase", "supply_chain"],
        "params": {"limit": {"type": "int", "flag": "--limit", "label": "Limit", "default": 50, "min": 1}},
    },
    "enrich_local": {
        "label": "Enrich from local datasheets",
        "description": "Parse PDFs already in datasheets/ with the LLM. Without 'Write to DB' it is a dry run.",
        "script": "enrich_local.py", "base_args": [],
        "params": {
            "limit": {"type": "int", "flag": "--limit", "label": "Limit (0 = all)", "default": 10, "min": 0},
            "delay": {"type": "float", "flag": "--delay", "label": "Delay between LLM calls (s)", "default": 4.0, "min": 0},
            "supply_chain": {"type": "bool", "flag": "--supply-chain", "label": "Supply-chain parts", "default": False},
            "write": {"type": "bool", "flag": "--write", "label": "Write to DB", "default": False},
        },
    },
    "reclassify": {
        "label": "Reclassify parts",
        "description": "Re-run category classification. Without 'Apply' it is a dry run.",
        "script": "reclassify.py", "base_args": [],
        "params": {"apply": {"type": "bool", "flag": "--apply", "label": "Apply changes", "default": False}},
    },
    "enrich_description": {
        "label": "Enrich from part descriptions (LLM)",
        "description": "Fill sparse supply-chain parts with specs stated in their Excel description. Without 'Write to DB' it is a dry run.",
        "script": "enrich_from_description.py", "base_args": [],
        "params": {"write": {"type": "bool", "flag": "--write", "label": "Write to DB", "default": False}},
    },
    "add_mpns": {
        "label": "Add new MPNs (fetch datasheet + extract specs)",
        "description": "Find each MPN's datasheet, extract its specs and make it available to the alternative finder.",
        "script": "add_mpns.py", "base_args": [],
        "params": {
            "cat": {"type": "categories_single", "flag": "-c", "label": "Category"},
            "mpns": {"type": "mpn_list", "label": "MPNs (space, comma or newline separated)"},
        },
    },
    "populate_queue": {
        "label": "Queue parts missing datasheets",
        "description": "Add every component without a datasheet URL to the fetch queue (supply-chain parts first).",
        "script": "populate_datasheet_queue.py", "base_args": [], "params": {},
    },
    "retry_datasheets": {
        "label": "Retry datasheets (alternate sources)",
        "description": "Look for missing supply-chain datasheets on LCSC, Alldatasheet and Datasheet4U.",
        "script": "retry_datasheets.py", "base_args": [],
        "params": {"limit": {"type": "int", "flag": "--limit", "label": "Limit (0 = all)", "default": 0, "min": 0}},
    },
    "import_supply_chain": {
        "label": "Import supply-chain template",
        "description": "Import an uploaded ODM template (.xlsx) into the supply_chain table.",
        "script": "import_template.py", "base_args": [], "params": {}, "hidden": True,
    },
    "enrich_stats": {
        "label": "Enrichment stats",
        "description": "Print enrichment coverage statistics.",
        "script": "enrich_all.py", "base_args": ["--phase", "stats"], "params": {},
    },
    "db_status": {
        "label": "Database status",
        "description": "Print database status report.",
        "script": "db_status.py", "base_args": [], "params": {},
    },
}


def build_args(task: Dict[str, Any], values: Dict[str, Any]) -> List[str]:
    args: List[str] = list(task["base_args"])
    for key, spec in task["params"].items():
        val = values.get(key, spec.get("default"))
        kind = spec["type"]
        if kind == "bool":
            if val:
                args.append(spec["flag"])
        elif kind in ("int", "float"):
            if val is None or val == "":
                continue
            try:
                num = int(val) if kind == "int" else float(val)
            except (TypeError, ValueError):
                raise HTTPException(400, f"{key} must be a number")
            if "min" in spec and num < spec["min"]:
                raise HTTPException(400, f"{key} must be >= {spec['min']}")
            args += [spec["flag"], str(num)]
        elif kind == "categories":
            if values.get("all"):
                continue
            cats = val or []
            bad = [c for c in cats if c not in CATEGORIES]
            if bad:
                raise HTTPException(400, f"Unknown categories: {bad}")
            if not cats:
                raise HTTPException(400, "Select at least one category or 'All categories'")
            args += [spec["flag"], *cats]
        elif kind == "mpn_list":
            mpns = [m for m in re.split(r"[\s,;]+", str(val or "")) if m]
            if not mpns or len(mpns) > 50 or not all(MPN_RE.match(m) for m in mpns):
                raise HTTPException(400, "Give 1-50 valid MPNs")
            args += mpns
        elif kind == "categories_single":
            if val not in CATEGORIES:
                raise HTTPException(400, f"Unknown category: {val}")
            args += [spec["flag"], val]
    return args


# ── Job registry ──
_jobs: Dict[str, Dict[str, Any]] = {}
_procs: Dict[str, subprocess.Popen] = {}
_lock = threading.Lock()


def _meta_path(job_id: str) -> str:
    return os.path.join(LOG_DIR, f"{job_id}.json")


def _log_path(job_id: str) -> str:
    return os.path.join(LOG_DIR, f"{job_id}.log")


def _save(job: Dict[str, Any]):
    with open(_meta_path(job["id"]), "w", encoding="utf-8") as f:
        json.dump(job, f)


def _load_history():
    for name in os.listdir(LOG_DIR):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(LOG_DIR, name), encoding="utf-8") as f:
                job = json.load(f)
        except (OSError, ValueError):
            continue
        if job.get("status") == "running":  # server restarted mid-run
            job["status"] = "interrupted"
        _jobs[job["id"]] = job


_load_history()


def _watch(job_id: str, proc: subprocess.Popen):
    code = proc.wait()
    with _lock:
        job = _jobs[job_id]
        if job["status"] != "cancelled":
            job["status"] = "succeeded" if code == 0 else "failed"
        job["exit_code"] = code
        job["finished_at"] = time.time()
        _procs.pop(job_id, None)
        _save(job)


def _running_job() -> Optional[str]:
    return next((i for i, j in _jobs.items() if j["status"] == "running"), None)


class JobRequest(BaseModel):
    task: str
    params: Dict[str, Any] = {}


@router.get("/tasks")
def list_tasks():
    return {
        "tasks": {k: {f: v[f] for f in ("label", "description", "params")}
                  for k, v in TASKS.items() if not v.get("hidden")},
        "categories": {slug: c.name for slug, c in CATEGORIES.items()},
    }


def _launch(task_key: str, params: Dict[str, Any], extra_args: Optional[List[str]] = None) -> Dict[str, Any]:
    task = TASKS[task_key]
    args = build_args(task, params) + (extra_args or [])
    with _lock:
        running = _running_job()
        if running:
            raise HTTPException(409, f"Job {running} is still running (database is single-writer)")
        job_id = uuid.uuid4().hex[:10]
        cmd = [sys.executable, "-u", task["script"], *args]
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        with open(_log_path(job_id), "wb") as log:
            proc = subprocess.Popen(cmd, cwd=BASE_DIR, stdout=log, stderr=subprocess.STDOUT, env=env)
        job = {
            "id": job_id, "task": task_key, "label": task["label"], "params": params,
            "command": " ".join(["python", task["script"], *args]),
            "status": "running", "started_at": time.time(), "finished_at": None, "exit_code": None,
        }
        _jobs[job_id] = job
        _procs[job_id] = proc
        _save(job)
    threading.Thread(target=_watch, args=(job_id, proc), daemon=True).start()
    return job


@router.post("/jobs")
def start_job(req: JobRequest):
    task = TASKS.get(req.task)
    if not task or task.get("hidden"):
        raise HTTPException(404, f"Unknown task: {req.task}")
    return _launch(req.task, req.params)


@router.get("/jobs")
def list_jobs():
    return sorted(_jobs.values(), key=lambda j: j["started_at"], reverse=True)


@router.get("/jobs/{job_id}")
def get_job(job_id: str, offset: int = 0):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    try:
        with open(_log_path(job_id), "rb") as f:
            f.seek(max(offset, 0))
            data = f.read()
    except OSError:
        data = b""
    return {**job, "log": data.decode("utf-8", errors="replace"), "next_offset": max(offset, 0) + len(data)}


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    with _lock:
        job, proc = _jobs.get(job_id), _procs.get(job_id)
        if not job or not proc or job["status"] != "running":
            raise HTTPException(409, "Job is not running")
        job["status"] = "cancelled"
    if os.name == "nt":  # kill the whole tree (Playwright spawns browsers)
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.terminate()
    return job


# ── Overview ──
def _count(conn, sql: str) -> int:
    return conn.execute(sql).fetchone()[0]


def _llm_configured() -> bool:
    import finder_extras.llm_parser as lp  # loads .env on import
    return bool((lp.LLM_API_KEY and lp.LLM_BASE_URL) or lp.NVIDIA_API_KEY)


@router.get("/overview")
def overview():
    """Database health snapshot for the admin dashboard (read-only)."""
    import sqlite3
    from database import DB_PATH

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        total = _count(conn, "SELECT COUNT(*) FROM components")
        with_ds = _count(conn, "SELECT COUNT(*) FROM components WHERE datasheet_url IS NOT NULL AND datasheet_url != ''")
        parts_with_specs = _count(
            conn, "SELECT COUNT(DISTINCT component_id) FROM specifications WHERE substr(spec_name, 1, 1) != '_'")
        enriched = _count(
            conn, "SELECT COUNT(DISTINCT component_id) FROM specifications WHERE spec_name = '_enriched' AND spec_value = '1'")
        try:
            queue = dict(conn.execute("SELECT status, COUNT(*) FROM datasheet_queue GROUP BY status").fetchall())
            supply_chain_rows = _count(conn, "SELECT COUNT(*) FROM supply_chain")
            supply_chain_mpns = _count(conn, "SELECT COUNT(DISTINCT upper(trim(mpn))) FROM supply_chain")
        except sqlite3.OperationalError:  # tables not created yet
            queue, supply_chain_rows, supply_chain_mpns = {}, 0, 0
        by_cat = conn.execute(
            "SELECT category, COUNT(*) FROM components GROUP BY category ORDER BY 2 DESC").fetchall()
    finally:
        conn.close()

    ds_dir = os.path.join(BASE_DIR, "datasheets")
    pdfs = len([f for f in os.listdir(ds_dir) if f.lower().endswith(".pdf")]) if os.path.isdir(ds_dir) else 0
    jobs = sorted(_jobs.values(), key=lambda j: j["started_at"], reverse=True)
    return {
        "components": total,
        "with_datasheet_url": with_ds,
        "parts_with_specs": parts_with_specs,
        "llm_enriched_parts": enriched,
        "datasheet_pdfs_on_disk": pdfs,
        "categories": [
            {"slug": c, "name": CATEGORIES[c].name if c in CATEGORIES else c, "count": n}
            for c, n in by_cat
        ],
        "running_job": _running_job(),
        "last_job": jobs[0] if jobs else None,
        "llm_configured": _llm_configured(),
        "datasheet_queue": queue,
        "supply_chain_rows": supply_chain_rows,
        "supply_chain_mpns": supply_chain_mpns,
    }


# ── Uploads ──
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_MPNS = 20000
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
MPN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-/+#()]{1,63}$")
MPN_HEADERS = {"MPN", "PART NUMBER", "PART_NUMBER", "MANUFACTURER PART NUMBER", "MANUFACTURER_PART_NUMBER"}


async def _read_upload(file: UploadFile, exts: tuple) -> bytes:
    name = (file.filename or "").lower()
    if not name.endswith(exts):
        raise HTTPException(400, f"Unsupported file type; expected {', '.join(exts)}")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large (max 25 MB)")
    if not data:
        raise HTTPException(400, "File is empty")
    return data


def _mpns_from_file(name: str, data: bytes) -> List[str]:
    import io
    import pandas as pd
    lower = name.lower()
    if not lower.endswith((".xlsx", ".xls", ".csv")):
        return re.split(r"[\s,;]+", data.decode("utf-8", errors="replace"))
    try:
        if lower.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(data), header=None, dtype=str, encoding_errors="replace")
        else:
            df = pd.read_excel(io.BytesIO(data), header=None, dtype=str)
    except Exception as e:
        raise HTTPException(400, f"Could not read file: {e}")
    if df.empty:
        return []
    col = 0
    for i in range(df.shape[1]):  # use a column whose header says MPN, else the first
        if str(df.iat[0, i]).strip().upper() in MPN_HEADERS:
            col = i
            break
    return [str(v) for v in df.iloc[:, col].dropna().tolist()]


@router.post("/upload/supply-chain")
async def upload_supply_chain(file: UploadFile = File(...)):
    """Save an ODM golden template into templates/ and import it as a background job."""
    data = await _read_upload(file, (".xlsx", ".xls"))
    if _running_job():
        raise HTTPException(409, "A job is already running")
    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._ -]", "_", os.path.basename(file.filename or "template.xlsx"))
    path = os.path.join(TEMPLATE_DIR, safe)
    with open(path, "wb") as f:
        f.write(data)
    return _launch("import_supply_chain", {"file": safe}, extra_args=[path])


@router.post("/upload/mpns")
async def upload_mpns(
    file: Optional[UploadFile] = File(None),
    text: str = Form(""),
    category: str = Form(""),
    requeue: bool = Form(False),
):
    """Add new MPNs (pasted text and/or a .txt/.csv/.xlsx file) to the datasheet fetch queue."""
    if category and category not in CATEGORIES:
        raise HTTPException(400, f"Unknown category: {category}")
    raw = re.split(r"[\s,;]+", text)
    if file is not None and file.filename:
        raw += _mpns_from_file(file.filename, await _read_upload(file, (".txt", ".csv", ".xlsx", ".xls")))

    seen, mpns, invalid = set(), [], []
    for m in (r.strip() for r in raw):
        if not m or m.upper() in MPN_HEADERS:
            continue
        if not MPN_RE.match(m):
            invalid.append(m)
        elif m.upper() not in seen:
            seen.add(m.upper())
            mpns.append(m)
    if not mpns:
        raise HTTPException(400, "No valid MPNs found")
    if len(mpns) > MAX_MPNS:
        raise HTTPException(400, f"Too many MPNs (max {MAX_MPNS})")

    from import_template import create_tables
    from database import DB_PATH
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        create_tables(conn)
        have_url = {r[0].upper() for r in conn.execute(
            "SELECT manufacturer_part_number FROM components WHERE datasheet_url IS NOT NULL AND datasheet_url != ''")}
        queued = requeued = already_queued = has_datasheet = 0
        for m in mpns:
            if m.upper() in have_url:
                has_datasheet += 1
                continue
            cur = conn.execute(
                "INSERT OR IGNORE INTO datasheet_queue (mpn, category_slug, source, status) VALUES (?, ?, 'admin_upload', 'pending')",
                (m, category or None))
            if cur.rowcount:
                queued += 1
            elif requeue and conn.execute(
                    "UPDATE datasheet_queue SET status = 'pending' WHERE mpn = ? AND status NOT IN ('pending', 'found')",
                    (m,)).rowcount:
                requeued += 1
            else:
                already_queued += 1
        conn.commit()
    finally:
        conn.close()
    return {
        "received": len(mpns), "queued": queued, "requeued": requeued,
        "already_queued": already_queued, "already_have_datasheet": has_datasheet,
        "invalid": invalid[:20], "invalid_count": len(invalid),
    }
