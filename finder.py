"""
finder.py — IC Alternative Finder engine.

Given a target part number, finds compatible replacements from the
AutoScraper database [2] using the full set of category-specific
comparison rules from the replaceability matrix [1].
"""

import logging
import sqlite3
import sys
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from finder_extras.spec_normalizer import normalize_spec_name
from spec_parser import (
    parse_value, parse_range, parse_temperature_range,
    values_compatible, range_covers, candidate_meets_or_exceeds,
)
from match_rules import get_rules, SpecRule, CategoryRules
from config import DB_PATH

log = logging.getLogger(__name__)


@dataclass
class MatchResult:
    component_id: int
    mpn: str
    manufacturer: str
    description: str
    category: str
    subcategory: str
    package: str
    mounting_type: str
    lifecycle_status: str
    stock: int = 0
    unit_price: float = 0.0
    datasheet_url: str = ""
    product_url: str = ""
    total_score: float = 0.0
    max_possible_score: float = 0.0
    compatibility_pct: float = 0.0
    spec_scores: Dict[str, dict] = field(default_factory=dict)
    is_drop_in: bool = False
    disqualified: bool = False
    disqualify_reason: str = ""


@dataclass
class PartInfo:
    component_id: int
    mpn: str
    manufacturer: str
    description: str
    category: str
    subcategory: str
    package: str
    mounting_type: str
    lifecycle_status: str
    stock: int
    unit_price: float
    datasheet_url: str
    product_url: str
    specs: Dict[str, str] = field(default_factory=dict)


class AlternativeFinder:
    """
    Finds compatible IC alternatives from the AutoScraper database.

    Uses the full category-specific electrical-spec filters [1] to score
    each candidate against the target part across ALL relevant parameters.
    """

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._conn = None

    def _get_conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── LOOKUP ──────────────────────────────────────
    def lookup(self, mpn):
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM components WHERE manufacturer_part_number = ? LIMIT 1", (mpn,)
        ).fetchone()
        if not row:
            row = conn.execute(
                "SELECT * FROM components WHERE manufacturer_part_number LIKE ? LIMIT 1",
                ("%" + mpn + "%",)
            ).fetchone()
        if not row:
            return None
        specs_rows = conn.execute(
            "SELECT spec_name, spec_value FROM specifications WHERE component_id = ?",
            (row["id"],)
        ).fetchall()
        return PartInfo(
            component_id=row["id"], mpn=row["manufacturer_part_number"],
            manufacturer=row["manufacturer"] or "", description=row["description"] or "",
            category=row["category"] or "", subcategory=row["subcategory"] or "",
            package=row["package"] or "", mounting_type=row["mounting_type"] or "",
            lifecycle_status=row["lifecycle_status"] or "", stock=row["stock"] or 0,
            unit_price=row["unit_price"] or 0.0, datasheet_url=row["datasheet_url"] or "",
            product_url=row["product_url"] or "",
            specs={r["spec_name"]: r["spec_value"] for r in specs_rows},
        )

    def search(self, keyword, limit=10):
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM components WHERE manufacturer_part_number LIKE ? "
            "OR description LIKE ? OR manufacturer LIKE ? LIMIT ?",
            ("%" + keyword + "%",) * 3 + (limit,)
        ).fetchall()
        results = []
        for row in rows:
            specs_rows = conn.execute(
                "SELECT spec_name, spec_value FROM specifications WHERE component_id = ?",
                (row["id"],)
            ).fetchall()
            results.append(PartInfo(
                component_id=row["id"], mpn=row["manufacturer_part_number"],
                manufacturer=row["manufacturer"] or "", description=row["description"] or "",
                category=row["category"] or "", subcategory=row["subcategory"] or "",
                package=row["package"] or "", mounting_type=row["mounting_type"] or "",
                lifecycle_status=row["lifecycle_status"] or "", stock=row["stock"] or 0,
                unit_price=row["unit_price"] or 0.0, datasheet_url=row["datasheet_url"] or "",
                product_url=row["product_url"] or "",
                specs={r["spec_name"]: r["spec_value"] for r in specs_rows},
            ))
        return results

    # ── FIND ALTERNATIVES ──────────────────────────
    def find_alternatives(self, target, top_n=10, same_category_only=True,
                          same_package_only=False, exclude_same_mpn=True,
                          min_compatibility_pct=30.0):
        conn = self._get_conn()
        rules = get_rules(target.category)

        conditions, params = [], []
        if same_category_only and target.category:
            conditions.append("category = ?")
            params.append(target.category)
        if same_package_only and target.package:
            conditions.append("package = ?")
            params.append(target.package)
        if exclude_same_mpn:
            conditions.append("manufacturer_part_number != ?")
            params.append(target.mpn)

        where = " AND ".join(conditions) if conditions else "1=1"
        candidates = conn.execute(
            "SELECT * FROM components WHERE {} ORDER BY stock DESC".format(where), params
        ).fetchall()

        log.info("Evaluating %d candidates for %s", len(candidates), target.mpn)

        results = []
        for cand_row in candidates:
            cand_specs_rows = conn.execute(
                "SELECT spec_name, spec_value FROM specifications WHERE component_id = ?",
                (cand_row["id"],)
            ).fetchall()
            cand_specs = {r["spec_name"]: r["spec_value"] for r in cand_specs_rows}
            result = self._score_candidate(target, cand_row, cand_specs, rules)
            if not result.disqualified and result.compatibility_pct >= min_compatibility_pct:
                # Check lifecycle filter
                from finder_extras.lifecycle_filter import should_include_part
                if (not result.disqualified
                        and result.compatibility_pct >= min_compatibility_pct
                        and should_include_part(result.lifecycle_status)):
                    results.append(result)

        results.sort(key=lambda r: r.compatibility_pct, reverse=True)
        return results[:top_n]

    # ── SCORING ────────────────────────────────────
    def _score_candidate(self, target, cand_row, cand_specs, rules):
        result = MatchResult(
            component_id=cand_row["id"],
            mpn=cand_row["manufacturer_part_number"] or "",
            manufacturer=cand_row["manufacturer"] or "",
            description=cand_row["description"] or "",
            category=cand_row["category"] or "",
            subcategory=cand_row["subcategory"] or "",
            package=cand_row["package"] or "",
            mounting_type=cand_row["mounting_type"] or "",
            lifecycle_status=cand_row["lifecycle_status"] or "",
            ##stock=cand_row["stock"] or 0,
            ##unit_price=cand_row["unit_price"] or 0.0,
            datasheet_url=cand_row["datasheet_url"] or "",
            product_url=cand_row["product_url"] or "",
        )

        total_score, max_score = 0.0, 0.0

        # Score every spec rule
        for rule in rules.rules:
            target_val = self._get_spec(target.specs, rule.spec_name, rule.aliases)
            cand_val = self._get_spec(cand_specs, rule.spec_name, rule.aliases)
            spec_score, spec_max, status = self._score_spec(rule, target_val, cand_val)

            result.spec_scores[rule.spec_name] = {
                "target": target_val or "-", "candidate": cand_val or "-",
                "score": spec_score, "max": spec_max, "status": status,
                "required": rule.required,
            }

            if rule.required and status == "FAIL":
                result.disqualified = True
                result.disqualify_reason = "Required spec '{}' mismatch".format(rule.spec_name)

            total_score += spec_score
            max_score += spec_max

        # Package match
        pkg_s, pkg_m = self._score_package(target, result, rules)
        total_score += pkg_s; max_score += pkg_m

        # Mounting type
        if target.mounting_type and result.mounting_type:
            mm = rules.mount_weight
            ms = mm if target.mounting_type.lower() == result.mounting_type.lower() else 0
            total_score += ms; max_score += mm

        # Temperature range
        ts, tm = self._score_temperature(target.specs, cand_specs, rules)
        total_score += ts; max_score += tm

        # Lifecycle
        lm = rules.lifecycle_weight
        ls = lm if (result.lifecycle_status or "").lower() == "active" else 0
        total_score += ls; max_score += lm

        # Stock
        # sm = rules.stock_weight
        # ss = sm if result.stock > 0 else 0
        # total_score += ss; max_score += sm

        # Final
        result.total_score = total_score
        result.max_possible_score = max_score
        result.compatibility_pct = (total_score / max_score * 100) if max_score > 0 else 0

        all_req_pass = all(
            v["status"] != "FAIL" for v in result.spec_scores.values() if v.get("required")
        )
        result.is_drop_in = (
            all_req_pass and pkg_s == pkg_m
            and (target.mounting_type.lower() == result.mounting_type.lower()
                 if target.mounting_type and result.mounting_type else all_req_pass)
        )
        return result

    def _get_spec(self, specs, name, aliases=None):
        from finder_extras.spec_normalizer import normalize_spec_name
        name = normalize_spec_name(name)
        if name in specs and specs[name] and specs[name] != "-":
            return specs[name]
        for alias in (aliases or []):
            norm_alias = normalize_spec_name(alias)
            if norm_alias in specs and specs[norm_alias] and specs[norm_alias] != "-":
                return specs[norm_alias]
        return None

    def _score_spec(self, rule, target_val, cand_val):
        mx = rule.weight
        if not target_val and not cand_val:
            return (mx * 0.5, mx, "BOTH_MISSING")
        if target_val and not cand_val:
            return (0, mx, "CAND_MISSING")
        if not target_val and cand_val:
            return (mx * 0.3, mx, "TARGET_MISSING")

        if rule.match_type == "exact":
            if target_val.strip().lower() == cand_val.strip().lower():
                return (mx, mx, "MATCH")
            if target_val.lower() in cand_val.lower() or cand_val.lower() in target_val.lower():
                return (mx * 0.6, mx, "PARTIAL")
            return (0, mx, "FAIL")

        elif rule.match_type == "contains":
            from finder_extras.protocol_matcher import protocols_compatible
            compat, quality, mult = protocols_compatible(target_val, cand_val)
            if quality not in ("unknown", "different"):
                return (mx * mult, mx, quality.upper())
            # Fallback to original substring logic
            t, c = target_val.lower(), cand_val.lower()
            if t == c: return (mx, mx, "MATCH")
            if t in c or c in t: return (mx * 0.7, mx, "PARTIAL")
            tw, cw = set(t.split()), set(c.split())
            ov = tw & cw
            if ov: return (mx * len(ov) / max(len(tw), 1) * 0.8, mx, "PARTIAL")
            return (0, mx, "FAIL")
            

        elif rule.match_type == "numeric_close":
            tn, cn = parse_value(target_val), parse_value(cand_val)
            if tn is None or cn is None:
                if target_val.strip().lower() == cand_val.strip().lower():
                    return (mx, mx, "MATCH")
                return (mx * 0.3, mx, "UNPARSEABLE")
            if values_compatible(tn, cn, rule.tolerance_pct):
                return (mx, mx, "MATCH")
            if tn != 0:
                d = abs(cn - tn) / abs(tn) * 100
                if d < rule.tolerance_pct * 2:
                    return (mx * 0.5, mx, "CLOSE")
            return (0, mx, "FAIL")

        elif rule.match_type == "meets_or_exceeds":
            tn, cn = parse_value(target_val), parse_value(cand_val)
            if tn is None or cn is None:
                if target_val.strip().lower() == cand_val.strip().lower():
                    return (mx, mx, "MATCH")
                return (mx * 0.3, mx, "UNPARSEABLE")
            if candidate_meets_or_exceeds(tn, cn):
                return (mx, mx, "MATCH")
            if tn != 0 and cn / tn > 0.7:
                return (mx * 0.4, mx, "CLOSE")
            return (0, mx, "FAIL")

        elif rule.match_type == "range_covers":
            tr, cr = parse_range(target_val), parse_range(cand_val)
            if range_covers(tr, cr):
                return (mx, mx, "MATCH")
            return (mx * 0.3, mx, "PARTIAL")

        return (0, mx, "UNKNOWN")

    def _score_package(self, target, candidate, rules):
        from finder_extras.pin_compat import score_package_compatibility
        mx = rules.package_weight
        score = score_package_compatibility(
            target.package, candidate.package, max_weight=mx
        )
        return (score, mx)
        
    def _score_temperature(self, target_specs, cand_specs, rules):
        mx = rules.temp_weight
        tk = ["Operating Temperature", "Temperature Range"]
        tt = cc = None
        for k in tk:
            if k in target_specs: tt = target_specs[k]
            if k in cand_specs: cc = cand_specs[k]
        if not tt or not cc:
            return (mx * 0.3, mx)
        tr, cr = parse_temperature_range(tt), parse_temperature_range(cc)
        if range_covers(tr, cr):
            return (mx, mx)
        return (mx * 0.3, mx)

    def compare_pinouts(self, mpn1, mpn2):
        """
        Download datasheets for two parts and compare their pinouts.
        Returns (score, details) where score is 0.0-1.0.
        """
        from finder_extras.datasheet_parser import DatasheetParser, compare_pinouts

        parser = DatasheetParser()

        part1 = self.lookup(mpn1)
        part2 = self.lookup(mpn2)

        if not part1 or not part2:
            return 0.0, {"error": "Part not found"}

        # Check if pinouts are already cached in DB
        conn = self._get_conn()

        pinout1_json = conn.execute(
            "SELECT spec_value FROM specifications WHERE component_id = ? AND spec_name = '_pinout_json'",
            (part1.component_id,)
        ).fetchone()

        pinout2_json = conn.execute(
            "SELECT spec_value FROM specifications WHERE component_id = ? AND spec_name = '_pinout_json'",
            (part2.component_id,)
        ).fetchone()

        # Pinouts created by the former broad-regex parser have no validation
        # metadata. Never reuse them for a safety-related comparison.
        def usable_cache(row):
            if not row:
                return False
            try:
                data = json.loads(row[0])
                return data.get("parser_version") == 2 and data.get("valid") is True
            except (ValueError, TypeError, KeyError):
                return False

        import json
        pinout1_json = pinout1_json if usable_cache(pinout1_json) else None
        pinout2_json = pinout2_json if usable_cache(pinout2_json) else None

        # If not cached, try to extract from datasheets
        if not pinout1_json and part1.datasheet_url:
            specs1, pin1 = parser.parse_datasheet(part1.datasheet_url, part1.mpn, part1.package)
            if pin1.is_valid():
                conn.execute(
                    "INSERT OR REPLACE INTO specifications (component_id, spec_name, spec_value) VALUES (?, ?, ?)",
                    (part1.component_id, "_pinout_json", pin1.to_json())
                )
                conn.commit()
        else:
            from finder_extras.datasheet_parser import PinoutInfo
            import json
            pin1 = PinoutInfo(mpn=part1.mpn, package=part1.package)
            if pinout1_json:
                data = json.loads(pinout1_json[0])
                for pn, pd in data.get("pins", {}).items():
                    pin1.add_pin(int(pn), pd["name"], pd.get("description", ""))

        if not pinout2_json and part2.datasheet_url:
            specs2, pin2 = parser.parse_datasheet(part2.datasheet_url, part2.mpn, part2.package)
            if pin2.is_valid():
                conn.execute(
                    "INSERT OR REPLACE INTO specifications (component_id, spec_name, spec_value) VALUES (?, ?, ?)",
                    (part2.component_id, "_pinout_json", pin2.to_json())
                )
                conn.commit()
        else:
            from finder_extras.datasheet_parser import PinoutInfo
            import json
            pin2 = PinoutInfo(mpn=part2.mpn, package=part2.package)
            if pinout2_json:
                data = json.loads(pinout2_json[0])
                for pn, pd in data.get("pins", {}).items():
                    pin2.add_pin(int(pn), pd["name"], pd.get("description", ""))

        score, details = compare_pinouts(pin1, pin2)
        return score, details

    # ── DB STATS ───────────────────────────────────
    def stats(self):
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT category, COUNT(*) as cnt FROM components GROUP BY category"
        ).fetchall()
        return {r["category"]: r["cnt"] for r in rows}

    def total_parts(self):
        return self._get_conn().execute("SELECT COUNT(*) FROM components").fetchone()[0]
