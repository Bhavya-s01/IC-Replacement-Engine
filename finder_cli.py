#!/usr/bin/env python3
"""
finder_cli.py — CLI for IC Alternative Finder.
Datasheet enrichment happens automatically on every find.
"""

import argparse, logging, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from finder import AlternativeFinder, PartInfo, MatchResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")


def print_part(part, show_specs=True):
    print("\n" + "=" * 70)
    print("  MPN:          {}".format(part.mpn))
    print("  Manufacturer: {}".format(part.manufacturer))
    print("  Description:  {}".format(part.description))
    print("  Category:     {}".format(part.category))
    print("  Subcategory:  {}".format(part.subcategory))
    print("  Package:      {}".format(part.package))
    print("  Mounting:     {}".format(part.mounting_type))
    print("  Status:       {}".format(""))
    if part.datasheet_url:
        print("  Datasheet:    {}".format(part.datasheet_url))
    print("=" * 70)
    if show_specs and part.specs:
        print("  SPECIFICATIONS ({} params):".format(len(part.specs)))
        print("  " + "-" * 66)
        for name, value in sorted(part.specs.items()):
            print("  {:<40} {}".format(name, value))
    print("")


def print_alternatives(target, alts):
    if not alts:
        print("\n  No compatible alternatives found.\n")
        return
    print("\n" + "=" * 95)
    print("  ALTERNATIVES FOR: {} ({})".format(target.mpn, target.description[:50]))
    print("  Category: {} | {} candidates found".format(target.category, len(alts)))
    print("=" * 95)

    for i, alt in enumerate(alts):
        di = " [DROP-IN]" if alt.is_drop_in else ""
        print("\n  #{} -- {} ({:.1f}% compatible){}".format(i+1, alt.mpn, alt.compatibility_pct, di))
        print("  " + "-" * 75)
        print("    Manufacturer: {}".format(alt.manufacturer))
        print("    Description:  {}".format(alt.description[:60]))
        print("    Package:      {}".format(alt.package))
        print("    Status:       {}".format("—"  # lifecycle removed))
        print("    Score:        {:.1f} / {:.1f}".format(alt.total_score, alt.max_possible_score))

        if alt.spec_scores:
            print("\n    {:<35} {:<20} {:<20} {}".format("SPEC", "TARGET", "CANDIDATE", "STATUS"))
            print("    " + "-" * 85)
            for spec_name, d in sorted(alt.spec_scores.items()):
                icon = {"MATCH":"OK", "PARTIAL":"~", "CLOSE":"~", "FAIL":"X",
                        "CAND_MISSING":"?", "TARGET_MISSING":"?",
                        "BOTH_MISSING":"-", "UNPARSEABLE":"?"}.get(d["status"], "?")
                req = "*" if d.get("required") else " "
                print("   {}{:<34} {:<20} {:<20} [{}] {:.0f}/{:.0f}".format(
                    req, spec_name, str(d["target"])[:18], str(d["candidate"])[:18],
                    icon, d["score"], d["max"]))

    print("\n  Legend: * = required, OK = match, ~ = partial, X = fail, ? = missing\n")


def cmd_pinout(args):
    finder = AlternativeFinder()
    print("\nComparing pinouts: {} vs {}".format(args.mpn1, args.mpn2))
    print("(Downloads datasheets on first run)\n")
    score, details = finder.compare_pinouts(args.mpn1, args.mpn2)
    print("=" * 60)
    print("PIN COMPATIBILITY: {:.0f}%".format(score * 100))
    print("=" * 60)
    status = details.get("status", "unknown")
    if status == "invalid_pinout_data":
        print("  Could not extract validated pinout from datasheets.")
        print("  Target:    {} pins (expected {}, valid={})".format(
            details.get("target_pins"), details.get("target_expected"), details.get("target_valid")))
        print("  Candidate: {} pins (expected {}, valid={})".format(
            details.get("candidate_pins"), details.get("candidate_expected"), details.get("candidate_valid")))
        print("  PDF pin tables are often graphical — use 'find' for electrical comparison.")
    elif status == "pin_count_mismatch":
        print("  PIN COUNT MISMATCH!")
        print("  Target: {} pins  Candidate: {} pins".format(
            details.get("target_pins"), details.get("candidate_pins")))
    elif status == "compared":
        print("  Pins compared: {}  Matches: {}  Critical mismatches: {}".format(
            details.get("total_pins"), details.get("matches"), details.get("critical_mismatches")))
        for m in details.get("mismatches", []):
            print("  Pin {} | {} -> {} | {}".format(m["pin"], m["target"], m.get("candidate","?"), m.get("severity","")))
    elif status == "missing_pinout_data":
        print("  Pinout data not available. Use 'find' for electrical comparison.")
    print("")
    finder.close()


def cmd_interactive(args):
    finder = AlternativeFinder()
    print("\n  IC Alternative Finder -- Interactive Mode")
    print("  Commands: lookup <mpn>, find <mpn>, compare <mpn1> <mpn2>, search <kw>, stats, quit\n")
    while True:
        try:
            inp = input("  >> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Bye!"); break
        if not inp: continue
        parts = inp.split()
        cmd = parts[0].lower()
        if cmd in ("quit","exit","q"):
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
            if a and b:
                all_specs = sorted(set(list(a.specs.keys()) + list(b.specs.keys())))
                print("\n  {:<30} {:<30} {:<30}".format("SPEC", a.mpn, b.mpn))
                print("  " + "-" * 90)
                for s in all_specs:
                    va, vb = a.specs.get(s,"-")[:28], b.specs.get(s,"-")[:28]
                    m = "==" if va.lower()==vb.lower() else "!="
                    print("  {:<30} {:<30} {:<30} {}".format(s[:28], va, vb, m))
            else:
                if not a: print("  Not found: {}".format(parts[1]))
                if not b: print("  Not found: {}".format(parts[2]))
        elif cmd == "search" and len(parts) >= 2:
            for r in finder.search(" ".join(parts[1:]), limit=10):
                print("  {} | {} | {} | {}".format(r.mpn, r.manufacturer, r.category, ""))
        elif cmd == "stats":
            for cat, cnt in sorted(finder.stats().items()):
                print("  {:<30} {}".format(cat, cnt))
        elif cmd == "pinout" and len(parts) >= 3:
            class A: pass
            a = A(); a.mpn1 = parts[1]; a.mpn2 = parts[2]
            cmd_pinout(a)
        else:
            t = finder.lookup(inp)
            if t:
                print_part(t, show_specs=False)
                alts = finder.find_alternatives(t, top_n=5)
                print_alternatives(t, alts)
            else: print("  Not found. Try: lookup, find, compare, search, stats, pinout, quit")
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
    sp = sub.add_parser("pinout"); sp.add_argument("mpn1"); sp.add_argument("mpn2")

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
                same_package_only=args.same_package, min_compatibility_pct=args.min_compat)
            print_alternatives(t, alts)
        else: print("  Not found: {}".format(args.mpn))
    elif args.command == "compare":
        a, b = finder.lookup(args.mpn1), finder.lookup(args.mpn2)
        if a and b:
            all_specs = sorted(set(list(a.specs.keys()) + list(b.specs.keys())))
            print("\n  {:<30} {:<30} {:<30}".format("SPEC", a.mpn, b.mpn))
            print("  " + "-" * 90)
            for s in all_specs:
                va, vb = a.specs.get(s,"-")[:28], b.specs.get(s,"-")[:28]
                m = "==" if va.lower()==vb.lower() else "!="
                print("  {:<30} {:<30} {:<30} {}".format(s[:28], va, vb, m))
        else:
            if not a: print("  Not found: {}".format(args.mpn1))
            if not b: print("  Not found: {}".format(args.mpn2))
    elif args.command == "search":
        for r in finder.search(" ".join(args.keywords), limit=args.limit):
            print("  {:<30} {:<25} {:<20}".format(r.mpn[:28], r.manufacturer[:23], r.category[:18]))
    elif args.command == "stats":
        s = finder.stats(); t = finder.total_parts()
        for cat in sorted(s.keys()):
            print("  {:<30} {:>8}".format(cat, s[cat]))
        print("  {:<30} {:>8}".format("TOTAL", t))
    elif args.command == "interactive":
        cmd_interactive(args)
    elif args.command == "pinout":
        cmd_pinout(args)
    else:
        parser.print_help()
        print("\n  Quick start:")
        print("    python finder_cli.py find MIC5501-3.0YM5-TR")
        print("    python finder_cli.py interactive")

    finder.close()


if __name__ == "__main__":
    main()