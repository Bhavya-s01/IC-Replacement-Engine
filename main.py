#!/usr/bin/env python3
"""
IC Database Ingestion Engine - CLI entry point.

Usage:
  python main.py scrape --all
  python main.py scrape --category power_ic --max-pages 3
  python main.py scrape --category power_ic --plugin digikey_curl
  python main.py import-csv --category power_ic
  python main.py status
  python main.py search --category power_ic --keyword LDO
  python main.py categories
"""

from __future__ import annotations

import logging
import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CATEGORIES, all_category_slugs
from database import Database
from engine import IngestionEngine

try:
    from rich.console import Console
    from rich.table import Table as RichTable
    from rich.logging import RichHandler
    RICH = True
except ImportError:
    RICH = False


def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    if RICH:
        logging.basicConfig(level=level, format="%(message)s", datefmt="[%X]",
                            handlers=[RichHandler(rich_tracebacks=True)])
    else:
        logging.basicConfig(level=level,
                            format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")


log = logging.getLogger("ic_scraper")


def build_engine(plugin_name="digikey_playwright"):
    db = Database()
    engine = IngestionEngine(db=db)

    if plugin_name == "digikey_playwright":
        from plugins.digikey_playwright import DigiKeyPlaywrightPlugin
        plugin = DigiKeyPlaywrightPlugin()
    elif plugin_name == "digikey_curl":
        from plugins.digikey_curl import DigiKeyCurlPlugin
        plugin = DigiKeyCurlPlugin()
    elif plugin_name == "csv_import":
        from plugins.csv_import import CSVImportPlugin
        plugin = CSVImportPlugin()
    else:
        print(f"Unknown plugin: {plugin_name}")
        sys.exit(1)

    engine.register_plugin(plugin)
    return engine


def cmd_scrape(args):
    engine = build_engine(args.plugin)
    p = engine._get_plugin()
    p.setup()

    try:
        if args.all:
            results = engine.scrape_all(plugin_name=args.plugin, max_pages=args.max_pages)
        elif args.category:
            results = {}
            for cat in args.category:
                count = engine.scrape_category(cat, plugin_name=args.plugin, max_pages=args.max_pages)
                results[cat] = count
        else:
            print("Specify --all or --category <slug>. Use 'categories' to list slugs.")
            return

        print("\n=== Scrape Results ===")
        for slug, cnt in results.items():
            name = CATEGORIES[slug].name if slug in CATEGORIES else slug
            print(f"  {name:<25} {cnt:>8}")
        print(f"  {'TOTAL':<25} {sum(results.values()):>8}")

    finally:
        p.teardown()
        engine.close()


def cmd_status(args):
    db = Database()
    counts = db.count_by_category()
    total = db.total_components()

    print("\n=== IC Database Status ===")
    for slug in all_category_slugs():
        name = CATEGORIES[slug].name
        cnt = counts.get(slug, 0)
        print(f"  {name:<25} {cnt:>8}")
    print(f"  {'TOTAL':<25} {total:>8}")
    db.close()


def cmd_categories(args):
    print("\n=== IC Categories ===")
    for slug in all_category_slugs():
        cat = CATEGORIES[slug]
        print(f"  {slug:<20} {cat.name:<20} ({cat.description})")


def cmd_search(args):
    db = Database()
    spec_filters = {}
    if args.spec:
        for s in args.spec:
            if "=" in s:
                k, v = s.split("=", 1)
                spec_filters[k.strip()] = v.strip()

    results = db.search(
        category=args.category,
        keyword=args.keyword,
        manufacturer=args.manufacturer,
        spec_filters=spec_filters if spec_filters else None,
        limit=args.limit,
    )

    if not results:
        print("No results found.")
        return

    print(f"\n=== Search Results ({len(results)} found) ===")
    print(f"  {'MPN':<30} {'Manufacturer':<20} {'Category':<15} {'Stock':>8} {'Price':>10}")
    print("  " + "-" * 85)
    for r in results:
        print(f"  {r.get('manufacturer_part_number',''):<30} "
              f"{r.get('manufacturer',''):<20} "
              f"{r.get('category',''):<15} "
              f"{r.get('stock', 0):>8} "
              f"${r.get('unit_price', 0):>9.4f}")
    db.close()


def cmd_import_csv(args):
    from plugins.csv_import import CSVImportPlugin
    engine = IngestionEngine()
    plugin = CSVImportPlugin(directory=args.directory)
    plugin.setup()
    engine.register_plugin(plugin)
    count = engine.scrape_category(args.category, plugin_name="csv_import")
    print(f"Imported {count} components for {args.category}.")
    engine.close()


def cmd_compare(args):
    db = Database()
    r1 = db.search(keyword=args.mpn1, limit=1)
    r2 = db.search(keyword=args.mpn2, limit=1)

    if not r1:
        print(f"Not found: {args.mpn1}")
        return
    if not r2:
        print(f"Not found: {args.mpn2}")
        return

    c1, c2 = r1[0], r2[0]
    specs1 = db.get_specifications(c1["id"])
    specs2 = db.get_specifications(c2["id"])
    all_names = sorted(set(list(specs1.keys()) + list(specs2.keys())))

    print(f"\n{'Parameter':<40} {args.mpn1:<30} {args.mpn2:<30}")
    print("-" * 100)
    for field in ["manufacturer", "description", "category", "package", "mounting_type", "stock", "unit_price"]:
        print(f"  {field:<38} {str(c1.get(field, '')):<30} {str(c2.get(field, '')):<30}")
    print("-" * 100)
    for name in all_names:
        v1 = specs1.get(name, "-")
        v2 = specs2.get(name, "-")
        print(f"  {name:<38} {v1:<30} {v2:<30}")
    db.close()


def main():
    parser = argparse.ArgumentParser(description="IC Database Ingestion Engine")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    sub = parser.add_subparsers(dest="command")

    # scrape
    sp = sub.add_parser("scrape", help="Scrape IC data from DigiKey")
    sp.add_argument("--all", action="store_true", help="Scrape all 11 categories")
    sp.add_argument("-c", "--category", nargs="+", help="Category slug(s)")
    sp.add_argument("-p", "--plugin", default="digikey_playwright",
                    choices=["digikey_playwright", "digikey_curl"])
    sp.add_argument("-m", "--max-pages", type=int, default=None)

    # status
    sub.add_parser("status", help="Show database statistics")

    # categories
    sub.add_parser("categories", help="List all IC categories")

    # search
    sp = sub.add_parser("search", help="Search the database")
    sp.add_argument("-c", "--category", default=None)
    sp.add_argument("-k", "--keyword", default=None)
    sp.add_argument("-m", "--manufacturer", default=None)
    sp.add_argument("-s", "--spec", nargs="*", default=[])
    sp.add_argument("-l", "--limit", type=int, default=25)

    # import-csv
    sp = sub.add_parser("import-csv", help="Import from CSV files")
    sp.add_argument("-c", "--category", required=True)
    sp.add_argument("-d", "--directory", default="imports")

    # compare
    sp = sub.add_parser("compare", help="Compare two components")
    sp.add_argument("mpn1", help="First MPN")
    sp.add_argument("mpn2", help="Second MPN")

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.command == "scrape":
        cmd_scrape(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "categories":
        cmd_categories(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "import-csv":
        cmd_import_csv(args)
    elif args.command == "compare":
        cmd_compare(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
