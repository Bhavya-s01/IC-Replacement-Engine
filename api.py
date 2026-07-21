"""
api.py — FastAPI backend for the IC Alternative Finder.
Run: python -m uvicorn api:app --reload --port 8000
Docs: http://localhost:8000/docs
"""

import sys
import os
import logging
from typing import Optional, List, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from finder import AlternativeFinder
from database import Database
from config import CATEGORIES

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("api")

app = FastAPI(
    title="IC Alternative Finder API",
    description="Find technically compatible IC replacements",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

finder = AlternativeFinder()
db = Database()


# ═══════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════

@app.get("/api/health")
def health():
    return {"status": "ok", "components": finder.total_parts()}


@app.get("/api/dashboard")
def get_dashboard():
    counts = finder.stats()
    total = finder.total_parts()
    conn = db._get_conn()

    lifecycle = {}
    rows = conn.execute(
        "SELECT lifecycle_status, COUNT(*) as cnt FROM components "
        "WHERE lifecycle_status != '' GROUP BY lifecycle_status"
    ).fetchall()
    for r in rows:
        lifecycle[r["lifecycle_status"]] = r["cnt"]

    return {
        "total": total,
        "categories": counts,
        "category_names": {slug: cat.name for slug, cat in CATEGORIES.items()},
        "lifecycle_breakdown": lifecycle,
    }


@app.get("/api/categories")
def get_categories():
    counts = finder.stats()
    result = []
    for slug, cat in CATEGORIES.items():
        result.append({
            "slug": slug,
            "name": cat.name,
            "description": cat.description,
            "count": counts.get(slug, 0),
        })
    result.sort(key=lambda c: c["name"])
    return result


@app.get("/api/search")
def search_parts(
    q: str = Query(..., min_length=1),
    category: Optional[str] = None,
    limit: int = Query(20, le=100),
):
    results = finder.search(q, limit=limit)
    if category:
        results = [r for r in results if r.category == category]
    return [
        {
            "mpn": r.mpn,
            "manufacturer": r.manufacturer,
            "description": r.description,
            "category": r.category,
            "package": r.package,
            "stock": r.stock,
            "unit_price": r.unit_price,
            "lifecycle_status": r.lifecycle_status,
        }
        for r in results
    ]


@app.get("/api/lookup/{mpn:path}")
def lookup_part(mpn: str):
    """Get full details — :path allows dots in MPN like ADP122AUJZ-3.0-R7"""
    part = finder.lookup(mpn)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found: {}".format(mpn))
    return {
        "mpn": part.mpn,
        "manufacturer": part.manufacturer,
        "description": part.description,
        "category": part.category,
        "subcategory": part.subcategory,
        "package": part.package,
        "mounting_type": part.mounting_type,
        "lifecycle_status": part.lifecycle_status,
        "stock": part.stock,
        "unit_price": part.unit_price,
        "datasheet_url": part.datasheet_url,
        "product_url": part.product_url,
        "specs": part.specs,
    }


@app.get("/api/alternatives/{mpn:path}")
def find_alternatives(
    mpn: str,
    top_n: int = Query(10, le=50),
    min_compat: float = Query(30.0, ge=0, le=100),
    same_package: bool = False,
):
    """Find compatible alternatives — :path allows dots in MPN"""
    target = finder.lookup(mpn)
    if not target:
        raise HTTPException(status_code=404, detail="Part not found: {}".format(mpn))

    alts = finder.find_alternatives(
        target,
        top_n=top_n,
        min_compatibility_pct=min_compat,
        same_package_only=same_package,
    )

    return [
        {
            "mpn": a.mpn,
            "manufacturer": a.manufacturer,
            "description": a.description,
            "category": a.category,
            "package": a.package,
            "mounting_type": a.mounting_type,
            "lifecycle_status": a.lifecycle_status,
            "stock": a.stock,
            "unit_price": a.unit_price,
            "datasheet_url": a.datasheet_url,
            "product_url": a.product_url,
            "compatibility_pct": a.compatibility_pct,
            "total_score": a.total_score,
            "max_possible_score": a.max_possible_score,
            "is_drop_in": a.is_drop_in,
            "spec_scores": a.spec_scores,
        }
        for a in alts
    ]


@app.get("/api/compare")
def compare_parts(mpn1: str, mpn2: str):
    a = finder.lookup(mpn1)
    b = finder.lookup(mpn2)
    if not a:
        raise HTTPException(status_code=404, detail="Not found: {}".format(mpn1))
    if not b:
        raise HTTPException(status_code=404, detail="Not found: {}".format(mpn2))

    all_specs = sorted(set(list(a.specs.keys()) + list(b.specs.keys())))

    return {
        "part_a": {
            "mpn": a.mpn, "manufacturer": a.manufacturer,
            "description": a.description, "category": a.category,
            "package": a.package, "mounting_type": a.mounting_type,
            "lifecycle_status": a.lifecycle_status,
            "stock": a.stock, "unit_price": a.unit_price,
            "specs": a.specs,
        },
        "part_b": {
            "mpn": b.mpn, "manufacturer": b.manufacturer,
            "description": b.description, "category": b.category,
            "package": b.package, "mounting_type": b.mounting_type,
            "lifecycle_status": b.lifecycle_status,
            "stock": b.stock, "unit_price": b.unit_price,
            "specs": b.specs,
        },
        "all_spec_names": all_specs,
    }


@app.get("/api/browse")
def browse_category(
    category: str,
    sort_by: str = "stock",
    sort_dir: str = "desc",
    limit: int = Query(50, le=500),
    offset: int = 0,
):
    conn = db._get_conn()

    valid_sorts = {
        "stock": "stock", "price": "unit_price",
        "mpn": "manufacturer_part_number",
        "manufacturer": "manufacturer",
    }
    sort_col = valid_sorts.get(sort_by, "stock")
    direction = "DESC" if sort_dir == "desc" else "ASC"

    rows = conn.execute(
        "SELECT manufacturer_part_number, manufacturer, description, "
        "stock, unit_price, package, mounting_type, lifecycle_status "
        "FROM components WHERE category=? ORDER BY {} {} LIMIT ? OFFSET ?".format(sort_col, direction),
        (category, limit, offset)
    ).fetchall()

    total = conn.execute(
        "SELECT COUNT(*) FROM components WHERE category=?", (category,)
    ).fetchone()[0]

    return {
        "category": category,
        "category_name": CATEGORIES[category].name if category in CATEGORIES else category,
        "total": total,
        "offset": offset,
        "limit": limit,
        "parts": [dict(r) for r in rows],
    }


@app.get("/api/lifecycle-summary")
def lifecycle_summary():
    conn = db._get_conn()
    rows = conn.execute(
        "SELECT lifecycle_status, category, COUNT(*) as cnt "
        "FROM components WHERE lifecycle_status != '' "
        "GROUP BY lifecycle_status, category"
    ).fetchall()

    summary = {}
    for r in rows:
        status = r["lifecycle_status"]
        if status not in summary:
            summary[status] = {"total": 0, "categories": {}}
        summary[status]["total"] += r["cnt"]
        cat_name = CATEGORIES[r["category"]].name if r["category"] in CATEGORIES else r["category"]
        summary[status]["categories"][cat_name] = r["cnt"]

    return summary


@app.get("/api/top-manufacturers")
def top_manufacturers(category: Optional[str] = None, limit: int = 15):
    """Top manufacturers by part count — used by Dashboard charts."""
    conn = db._get_conn()
    if category:
        rows = conn.execute(
            "SELECT manufacturer, COUNT(*) as cnt FROM components "
            "WHERE category=? AND manufacturer != '' "
            "GROUP BY manufacturer ORDER BY cnt DESC LIMIT ?",
            (category, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT manufacturer, COUNT(*) as cnt FROM components "
            "WHERE manufacturer != '' "
            "GROUP BY manufacturer ORDER BY cnt DESC LIMIT ?",
            (limit,)
        ).fetchall()

    return [{"manufacturer": r["manufacturer"], "count": r["cnt"]} for r in rows]


@app.get("/api/stats")
def get_stats():
    counts = finder.stats()
    total = finder.total_parts()
    return {
        "total": total,
        "categories": counts,
        "category_names": {slug: cat.name for slug, cat in CATEGORIES.items()},
    }