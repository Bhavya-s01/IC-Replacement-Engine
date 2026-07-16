#!/usr/bin/env python3
"""
finder_cli.py — Interactive CLI for the IC Alternative Finder.

Usage:
  python finder_cli.py lookup MIC5501-3.0YM5-TR
  python finder_cli.py find MIC5501-3.0YM5-TR
  python finder_cli.py find MIC5501-3.0YM5-TR --top 20
  python finder_cli.py compare MIC5501-3.0YM5-TR AP2112K-3.3TRG1
  python finder_cli.py search LDO 3.3V
  python finder_cli.py stats
  python finder_cli.py interactive
"""

import argparse, logging, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from finder import AlternativeFinder, PartInfo, MatchResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")


def print_part(part, show_specs=True):
    print("")
    print("=" * 70)
    print("  MPN:          {}".format(part.mpn))
    print("  Manufacturer: {}".format(part.manufacturer))
    print("  Description:  {}".format(part.description))
    print("  Category:     {}".format(part.category))
    print("  Subcategory:  {}".format(part.subcategory))
    print("  Package:      {}".format(part.package))
    print("  Mounting:     {}".format(part.mounting_type))
    print("  Status:       {}".format(part.lifecycle_status))
    print("  Stock:        {}".format(part.stock))
    print("  Price:        ${:.4f}".format(part.unit_price))
    if part.datasheet_url:
        print("  Datasheet:    {}".format(part.datasheet_url))
    print("=" * 70)
    if show_specs and part.specs:
        print("  SPECIFICATIONS ({} params):".format(len(part.specs)))
        print("  " + "-" * 66)
        for name, value in sorted(part.specs.items()):
            print("  {:<40} {}".format(name, value))
    print("")


def print_alternatives(target, alternatives):
    if not alternatives:
        print("\n  No compatible alternatives found in database.\n")
        return

    print("\n" + "=" * 95)
    print("  ALTERNATIVES FOR: {} ({})".format(target.mpn, target.description[:50]))
    print("  Category: {} | {} candidates found".format(target.category, len(alternatives)))
    print("=" * 95)

    for i, alt in enumerate(alternatives):
        di = " [DROP-IN]" if alt.is_drop_in else ""
        print("")
        print("  #{} — {} ({:.1f}% compatible){}".format(i + 1, alt.mpn, alt.compatibility_pct, di))
        print("  " + "-" * 75)
        print("    Manufacturer: {}".format(alt.manufacturer))
        print("    Description:  {}".format(alt.description[:60]))
        print("    Package:      {}".format(alt.package))
        print("    Mounting:     {}".format(alt.mounting_type))
        print("    Status:       {}".format(alt.lifecycle_status))
        print("    Stock:        {}   Price: ${:.4f}".format(alt.stock, alt.unit_price))
        print("    Score:        {:.1f} / {:.1f}".format(alt.total_score, alt.max_possible_score))

        if alt.spec_scores:
            print("")
            print("    {:<35} {:<20} {:<20} {}".format("SPEC", "TARGET", "CANDIDATE", "STATUS"))
            print("    " + "-" * 85)
            for spec_name, d in sorted(alt.spec_scores.items()):
                icon = {"MATCH": "OK", "PARTIAL": "~", "CLOSE": "~", "FAIL": "X",
                        "CAND_MISSING": "?", "TARGET_MISSING": "?",
                        "BOTH_MISSING": "-", "UNPARSEABLE": "?"}.get(d["status"], "?")
                req = "*" if d.get("required") else " "
                tv = str(d["target"])[:18]
                cv = str(d["candidate"])[:18]
                print("   {}{:<34} {:<20} {:<20} [{}] {:.0f}/{:.0f}".format(
                    req, spec_name, tv, cv, icon, d["score"], d["max"]))

    print("")
    print("  Legend: * = required, OK = match, ~ = partial, X = fail, ? = missing")
    print("")


def print_comparison(a, b):
    print("\n" + "=" * 100)
    print("  SIDE-BY-SIDE COMPARISON")
    print("=" * 100)
    print("  {:<30} {:<30} {:<30}".format("FIELD", a.mpn, b.mpn))
    print("  " + "-" * 92)
    for label, va, vb in [
        ("Manufacturer", a.manufacturer, b.manufacturer),
        ("Description", a.description[:28], b.description[:28]),
        ("Category", a.category, b.category),
        ("Package", a.package, b.package),
        ("Mounting", a.mounting_type, b.mounting_type),
        ("Status", a.lifecycle_status, b.lifecycle_status),
        ("Stock", str(a.stock), str(b.stock)),
        ("Price", "${:.4f}".format(a.unit_price), "${:.4f}".format(b.unit_price)),
    ]:
        m = "==" if va.lower() == vb.lower() else "!="
        print("  {:<30} {:<30} {:<30} {}".format(label, va, vb, m))

    all_specs = sorted(set(list(a.specs.keys()) + list(b.specs.keys())))
    if all_specs:
        print("\n  {:<30} {:<30} {:<30}".format("SPECIFICATION", a.mpn, b.mpn))
        print("  " + "-" * 92)
        for s in all_specs:
            va = a.specs.get(s, "-")[:28]
            vb = b.specs.get(s, "-")[:28]
            m = "==" if va.lower() == vb.lower() else "!="
            print("  {:<30} {:<30} {:<30} {}".format(s[:28], va, vb, m))
    print("")


def cmd_interactive(args):
    finder = AlternativeFinder()
    print("\n  IC Alternative Finder — Interactive Mode")
    print("  Commands: lookup <mpn>, find <mpn>, compare <mpn1> <mpn2>, search <kw>, stats, quit\n")

    while True:
        try:
            inp = input("  >> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Bye!"); break
        if not inp: continue
        parts = inp.split()
        cmd = parts[0].lower()

        if cmd in ("quit", "exit", "q"):
            print("  Bye!"); break
        elif cmd == "lookup" and len(parts) >= 2:
            p = finder.lookup(parts[1])
            if p: print_part(p)
            else: print("  Not found: {}".format(parts[1]))
        elif cmd == "find" and len(parts) >= 2:
            t = finder.lookup(parts[1])
            if t:
                print_part(t, show_specs=False)
                alts = finder.find_alternatives(t, top_n=10)
                print_alternatives(t, alts)
            else: print("  Not found: {}".format(parts[1]))
        elif cmd == "compare" and len(parts) >= 3:
            a, b = finder.lookup(parts[1]), finder.lookup(parts[2])
            if a and b: print_comparison(a, b)
            else:
                if not a: print("  Not found: {}".format(parts[1]))
                if not b: print("  Not found: {}".format(parts[2]))
        elif cmd == "search" and len(parts) >= 2:
            kw = " ".join(parts[1:])
            for r in finder.search(kw, limit=10):
                print("  {} | {} | {} | stk={}".format(r.mpn, r.manufacturer, r.category, r.stock))
        elif cmd == "stats":
            for cat, cnt in sorted(finder.stats().items()):
                print("  {:<30} {}".format(cat, cnt))
        else:
            t = finder.lookup(inp)
            if t:
                print_part(t, show_specs=False)
                alts = finder.find_alternatives(t, top_n=5)
                print_alternatives(t, alts)
            else:
                print("  Not found. Try: lookup <mpn>, find <mpn>, search <kw>, stats, quit")
    finder.close()


def main():
    parser = argparse.ArgumentParser(description="IC Alternative Finder")
    sub = parser.add_subparsers(dest="command")

    sp = sub.add_parser("lookup"); sp.add_argument("mpn")
    sp = sub.add_parser("find"); sp.add_argument("mpn")
    sp.add_argument("--top", type=int, default=10)
    sp.add_argument("--same-package", action="store_true")
    sp.add_argument("--min-compat", type=float, default=30.0)
    sp = sub.add_parser("compare"); sp.add_argument("mpn1"); sp.add_argument("mpn2")
    sp = sub.add_parser("search"); sp.add_argument("keywords", nargs="+")
    sp.add_argument("--limit", type=int, default=10)
    sub.add_parser("stats")
    sub.add_parser("interactive")
        # Add after the other subparser definitions:
    sp = sub.add_parser("pinout", help="Compare pinouts of two parts")
    sp.add_argument("mpn1")
    sp.add_argument("mpn2")

    args = parser.parse_args()
    finder = AlternativeFinder()

    if args.command == "lookup":
        p = finder.lookup(args.mpn)
        if p: print_part(p)
        else: print("  Not found: {}".format(args.mpn))
    elif args.command == "find":
        t = finder.lookup(args.mpn)
        if t:
            print_part(t, show_specs=False)
            alts = finder.find_alternatives(t, top_n=args.top,
                                             same_package_only=args.same_package,
                                             min_compatibility_pct=args.min_compat)
            print_alternatives(t, alts)
        else: print("  Not found: {}".format(args.mpn))
    elif args.command == "compare":
        a, b = finder.lookup(args.mpn1), finder.lookup(args.mpn2)
        if a and b: print_comparison(a, b)
        else:
            if not a: print("  Not found: {}".format(args.mpn1))
            if not b: print("  Not found: {}".format(args.mpn2))
    elif args.command == "search":
        kw = " ".join(args.keywords)
        results = finder.search(kw, limit=args.limit)
        if not results: print("  No results."); finder.close(); return
        print("\n  {:<30} {:<25} {:<20} {:>8} {:>10}".format("MPN","MFR","CATEGORY","STOCK","PRICE"))
        print("  " + "-" * 95)
        for r in results:
            print("  {:<30} {:<25} {:<20} {:>8} ${:>9.4f}".format(
                r.mpn[:28], r.manufacturer[:23], r.category[:18], r.stock, r.unit_price))
    elif args.command == "stats":
        s = finder.stats(); t = finder.total_parts()
        print("\n  IC DATABASE STATUS"); print("  " + "-" * 40)
        for cat in sorted(s.keys()):
            print("  {:<30} {:>8}".format(cat, s[cat]))
        print("  " + "-" * 40)
        print("  {:<30} {:>8}".format("TOTAL", t))
    elif args.command == "interactive":
        cmd_interactive(args)

    elif args.command == "pinout":
        cmd_pinout(args)
    else:
        parser.print_help()
        print("\n  Quick start:")
        print("    python finder_cli.py stats")
        print("    python finder_cli.py lookup MIC5501-3.0YM5-TR")
        print("    python finder_cli.py find MIC5501-3.0YM5-TR")
        print("    python finder_cli.py interactive")


    finder.close()

def cmd_pinout(args):
    """Compare pinouts of two parts using datasheet data."""
    finder = AlternativeFinder()

    print("\nComparing pinouts: {} vs {}".format(args.mpn1, args.mpn2))
    print("(This may download datasheets — first run takes longer)\n")

    score, details = finder.compare_pinouts(args.mpn1, args.mpn2)

    print("=" * 60)
    print("PIN COMPATIBILITY: {:.0f}%".format(score * 100))
    print("=" * 60)

    status = details.get("status", "unknown")
    if status == "missing_pinout_data":
        print("  Could not extract pinout data from datasheets.")
        print("  Datasheets may not contain machine-readable pin tables.")
    elif status == "pin_count_mismatch":
        print("  PIN COUNT MISMATCH!")
        print("  Target:    {} pins".format(details.get("target_pins")))
        print("  Candidate: {} pins".format(details.get("candidate_pins")))
        print("  These parts are NOT pin-compatible.")
    elif status == "compared":
        print("  Total pins compared: {}".format(details.get("total_pins")))
        print("  Matching pins:       {}".format(details.get("matches")))
        print("  Critical mismatches: {}".format(details.get("critical", 0)))
        mismatches = details.get("mismatches", [])
        if not mismatches:
            print("\n  All validated pin labels match.")
        else:
            print("\n  MISMATCHES:")
            for m in mismatches:
                print("  Pin {pin}: {target} vs {candidate} ({severity})".format(
                    pin=m["pin"], target=m["target"],
                    candidate=m.get("candidate", "?"), severity=m.get("severity", "?")))
        
    elif status == "invalid_pinout_data":
        print("  Could not extract VALIDATED pinout from datasheets.")
        print("  Target:    {} pins extracted (expected {}, valid={})".format(
            details.get("target_pins"), details.get("target_expected"), details.get("target_valid")))
        print("  Candidate: {} pins extracted (expected {}, valid={})".format(
            details.get("candidate_pins"), details.get("candidate_expected"), details.get("candidate_valid")))
        print("  Target confidence:    {:.0f}%".format(details.get("target_confidence", 0) * 100))
        print("  Candidate confidence: {:.0f}%".format(details.get("candidate_confidence", 0) * 100))
        print("")
        print("  PDF pin tables are often graphical or multi-column,")
        print("  making automated text extraction unreliable.")
        print("  Use 'find <mpn>' for electrical-spec comparison instead.")
    print("")
    finder.close()


if __name__ == "__main__":
    main()
