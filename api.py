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
    """Find compatible alternatives with drop-in detail."""
    target = finder.lookup(mpn)
    if not target:
        raise HTTPException(status_code=404, detail="Part not found: {}".format(mpn))

    alts = finder.find_alternatives(
        target,
        top_n=top_n,
        min_compatibility_pct=min_compat,
        same_package_only=same_package,
    )

    results = []
    for a in alts:
        # Build drop-in checklist
        all_req_pass = all(
            v["status"] != "FAIL"
            for v in a.spec_scores.values()
            if v.get("required")
        )
        pkg_match = (target.package or "").lower() == (a.package or "").lower()
        mount_match = (target.mounting_type or "").lower() == (a.mounting_type or "").lower()

        # Filter out BOTH_MISSING rows for cleaner display
        filtered_scores = {}
        for name, d in a.spec_scores.items():
            if d["status"] == "BOTH_MISSING":
                continue  # hide rows where neither part has data
            filtered_scores[name] = d

        results.append({
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
            "spec_scores": filtered_scores,
            "drop_in_checklist": {
                "package_match": pkg_match,
                "mounting_match": mount_match,
                "required_specs_pass": all_req_pass,
                "lifecycle_active": (a.lifecycle_status or "").lower() == "active",
                "target_package": target.package or "",
                "candidate_package": a.package or "",
                "target_mounting": target.mounting_type or "",
                "candidate_mounting": a.mounting_type or "",
            },
        })

    return results


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

@app.get("/api/matching-rules")
def get_matching_rules():
    """Return all category matching rules for the methodology page."""
    from match_rules import RULES, get_rules
    from config import CATEGORIES

    result = []
    for slug, cat in CATEGORIES.items():
        rules = get_rules(slug)
        specs = []
        for rule in rules.rules:
            specs.append({
                "name": rule.spec_name,
                "weight": rule.weight,
                "match_type": rule.match_type,
                "tolerance_pct": rule.tolerance_pct,
                "required": rule.required,
                "aliases": rule.aliases,
            })
        result.append({
            "slug": slug,
            "name": cat.name,
            "description": cat.description,
            "package_weight": rules.package_weight,
            "mount_weight": rules.mount_weight,
            "temp_weight": rules.temp_weight,
            "lifecycle_weight": rules.lifecycle_weight,
            "specs": specs,
        })
    result.sort(key=lambda r: r["name"])
    return result

@app.get("/api/supply-chain/{mpn:path}")
def get_supply_chain(mpn: str):
    """Get supply chain data from TPV template — if available."""
    conn = db._get_conn()
    try:
        conn.execute("SELECT 1 FROM supply_chain LIMIT 1")
    except Exception:
        return {"available": False, "mpn": mpn}

    rows = conn.execute(
        "SELECT * FROM supply_chain WHERE mpn = ? OR mpn LIKE ?",
        (mpn, "%" + mpn + "%")
    ).fetchall()

    if not rows:
        return {"available": False, "mpn": mpn}

    entries = []
    for r in rows:
        entry = {
            "mpn": r["mpn"],
            "pin_count": r["pin_count"],
            "category": r["mpn_category"],
            "sourcing": r["component_sourcing"],
            "package_type": r["package_type"],
            "dual_fab_plan": r["dual_fab_plan"],
            "supplier_name": r["supplier_name"],
            "mpn_coo": r["mpn_coo"],
            "lead_time_days": r["lead_time_days"],
            "moq": r["moq"],
            "po_term": r["po_term"],
            "odm": r["odm_name"],
            "template_date": r["template_date"],
        }
        if r["fab1_supplier"]:
            entry["fab1"] = {
                "supplier": r["fab1_supplier"],
                "country": r["fab1_country"],
                "city": r["fab1_city"],
            }
        if r["p2p_supplier"] or r["p2p_mpn"]:
            entry["p2p_solution"] = {
                "supplier": r["p2p_supplier"],
                "mpn": r["p2p_mpn"],
            }
        if r["non_p2p_supplier"] or r["non_p2p_mpn"]:
            entry["non_p2p_solution"] = {
                "supplier": r["non_p2p_supplier"],
                "mpn": r["non_p2p_mpn"],
            }
        entries.append(entry)

    return {
        "available": True,
        "mpn": mpn,
        "entries": entries,
        "data_date": entries[0].get("template_date") if entries else None,
    }

@app.get("/api/supply-chain-stats")
def supply_chain_stats():
    """Stats from the TPV Golden Template data."""
    conn = db._get_conn()
    try:
        conn.execute("SELECT 1 FROM supply_chain LIMIT 1")
    except Exception:
        return {"total": 0}

    total = conn.execute("SELECT COUNT(*) FROM supply_chain").fetchone()[0]
    by_odm = conn.execute(
        "SELECT odm_name, COUNT(*) as cnt FROM supply_chain "
        "GROUP BY odm_name ORDER BY cnt DESC"
    ).fetchall()
    by_sourcing = conn.execute(
        "SELECT component_sourcing, COUNT(*) as cnt FROM supply_chain "
        "WHERE component_sourcing IS NOT NULL "
        "GROUP BY component_sourcing ORDER BY cnt DESC"
    ).fetchall()
    p2p_count = conn.execute(
        "SELECT COUNT(*) FROM supply_chain WHERE p2p_mpn IS NOT NULL"
    ).fetchone()[0]
    sole_count = conn.execute(
        "SELECT COUNT(*) FROM supply_chain WHERE LOWER(component_sourcing) = 'sole'"
    ).fetchone()[0]
    overlap = conn.execute(
        "SELECT COUNT(DISTINCT sc.mpn) FROM supply_chain sc "
        "INNER JOIN components c ON c.manufacturer_part_number = sc.mpn"
    ).fetchone()[0]

    return {
        "total": total,
        "by_odm": [{"name": r[0] or "Unknown", "count": r[1]} for r in by_odm],
        "by_sourcing": [{"type": r[0], "count": r[1]} for r in by_sourcing],
        "p2p_solutions": p2p_count,
        "sole_source": sole_count,
        "overlap_with_db": overlap,
    }

@app.get("/api/alternatives-full/{mpn:path}")
def find_alternatives_full(
    mpn: str,
    top_n: int = Query(10, le=50),
    min_compat: float = Query(30.0, ge=0, le=100),
):
    """Find alternatives with both technical scoring AND supply chain data."""
    target = finder.lookup(mpn)
    if not target:
        raise HTTPException(status_code=404,
                            detail="Part not found: {}".format(mpn))

    alts = finder.find_alternatives(
        target, top_n=top_n,
        min_compatibility_pct=min_compat,
    )

    conn = db._get_conn()

    # Get supply chain data for the TARGET
    target_sc = None
    try:
        sc_rows = conn.execute(
            "SELECT * FROM supply_chain WHERE mpn = ?", (mpn,)
        ).fetchall()
        if sc_rows:
            target_sc = {
                "sourcing": sc_rows[0]["component_sourcing"],
                "dual_fab": sc_rows[0]["dual_fab_plan"],
                "lead_time": sc_rows[0]["lead_time_days"],
                "moq": sc_rows[0]["moq"],
                "odm": sc_rows[0]["odm_name"],
                "p2p_mpn": sc_rows[0]["p2p_mpn"],
                "p2p_supplier": sc_rows[0]["p2p_supplier"],
            }
    except Exception:
        pass

    # Build results with supply chain enrichment
    results = []
    for a in alts:
        entry = {
            "mpn": a.mpn,
            "manufacturer": a.manufacturer,
            "description": a.description,
            "category": a.category,
            "package": a.package,
            "mounting_type": a.mounting_type,
            "lifecycle_status": a.lifecycle_status,
            "datasheet_url": a.datasheet_url,
            "compatibility_pct": a.compatibility_pct,
            "is_drop_in": a.is_drop_in,
            "spec_scores": a.spec_scores,
        }

        # Check if this alternative has supply chain data
        try:
            sc_row = conn.execute(
                "SELECT * FROM supply_chain WHERE mpn = ? LIMIT 1",
                (a.mpn,)
            ).fetchone()
            if sc_row:
                entry["supply_chain"] = {
                    "sourcing": sc_row["component_sourcing"],
                    "dual_fab": sc_row["dual_fab_plan"],
                    "lead_time": sc_row["lead_time_days"],
                    "moq": sc_row["moq"],
                    "odm": sc_row["odm_name"],
                    "p2p_mpn": sc_row["p2p_mpn"],
                    "p2p_supplier": sc_row["p2p_supplier"],
                    "template_date": sc_row["template_date"],
                }
        except Exception:
            pass

        results.append(entry)

    return {
        "target": {
            "mpn": target.mpn,
            "manufacturer": target.manufacturer,
            "description": target.description,
            "category": target.category,
            "package": target.package,
            "specs": target.specs,
            "supply_chain": target_sc,
        },
        "alternatives": results,
        "total_found": len(alts),
    }
@app.get("/api/alternatives/{mpn:path}")
def find_alternatives(
    mpn: str,
    top_n: int = Query(10, le=50),
    min_compat: float = Query(30.0, ge=0, le=100),
    same_package: bool = False,
):
    target = finder.lookup(mpn)
    if not target:
        raise HTTPException(status_code=404, detail="Part not found: {}".format(mpn))

    alts = finder.find_alternatives(
        target, top_n=top_n,
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
            "drop_in_checklist": getattr(a, 'drop_in_checklist', {}),
            "notes": getattr(a, 'notes', ''),
        }
        for a in alts
    ]