"""
export_csv.py - Export database to CSV files for Excel.
Run: python export_csv.py
"""

import sqlite3
import csv
import os

DB = "ic_database.db"
OUT_DIR = "exports"
os.makedirs(OUT_DIR, exist_ok=True)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

# Get all components
components = conn.execute("""
    SELECT id, manufacturer_part_number, manufacturer, description,
           category, subcategory, stock, unit_price, package,
           mounting_type, lifecycle_status, datasheet_url, product_url,
           source, scraped_at
    FROM components
    ORDER BY category, manufacturer_part_number
""").fetchall()

if not components:
    print("No data in database yet. Run the scraper first.")
    exit()

# Get all unique spec names
spec_names = conn.execute("""
    SELECT DISTINCT spec_name FROM specifications ORDER BY spec_name
""").fetchall()
spec_names = [r[0] for r in spec_names]

print(f"Found {len(components)} components with {len(spec_names)} spec columns")

# Build CSV with all specs as columns
csv_path = os.path.join(OUT_DIR, "all_components.csv")

with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
    # Headers
    base_headers = [
        "MPN", "Manufacturer", "Description", "Category", "Subcategory",
        "Stock", "Unit Price", "Package", "Mounting Type", "Status",
        "Datasheet URL", "Product URL"
    ]
    all_headers = base_headers + spec_names
    writer = csv.writer(f)
    writer.writerow(all_headers)

    for comp in components:
        comp_id = comp["id"]

        # Get specs for this component
        specs = conn.execute(
            "SELECT spec_name, spec_value FROM specifications WHERE component_id=?",
            (comp_id,)
        ).fetchall()
        spec_dict = {r[0]: r[1] for r in specs}

        row = [
            comp["manufacturer_part_number"],
            comp["manufacturer"],
            comp["description"],
            comp["category"],
            comp["subcategory"],
            comp["stock"],
            comp["unit_price"],
            comp["package"],
            comp["mounting_type"],
            comp["lifecycle_status"],
            comp["datasheet_url"],
            comp["product_url"],
        ]

        # Add spec values in order
        for sname in spec_names:
            row.append(spec_dict.get(sname, ""))

        writer.writerow(row)

print(f"Exported to: {csv_path}")

# Also export per-category files
categories = conn.execute("SELECT DISTINCT category FROM components").fetchall()
for cat_row in categories:
    cat = cat_row[0]
    if not cat:
        continue

    cat_components = conn.execute(
        "SELECT id, manufacturer_part_number, manufacturer, description, "
        "subcategory, stock, unit_price, package, mounting_type, lifecycle_status, "
        "datasheet_url, product_url FROM components WHERE category=? "
        "ORDER BY manufacturer_part_number",
        (cat,)
    ).fetchall()

    cat_path = os.path.join(OUT_DIR, f"{cat}.csv")
    with open(cat_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)

        # Get spec names for this category only
        cat_specs = conn.execute("""
            SELECT DISTINCT s.spec_name FROM specifications s
            JOIN components c ON s.component_id = c.id
            WHERE c.category = ?
            ORDER BY s.spec_name
        """, (cat,)).fetchall()
        cat_spec_names = [r[0] for r in cat_specs]

        headers = [
            "MPN", "Manufacturer", "Description", "Subcategory",
            "Stock", "Unit Price", "Package", "Mounting Type", "Status",
            "Datasheet URL", "Product URL"
        ] + cat_spec_names
        writer.writerow(headers)

        for comp in cat_components:
            specs = conn.execute(
                "SELECT spec_name, spec_value FROM specifications WHERE component_id=?",
                (comp["id"],)
            ).fetchall()
            spec_dict = {r[0]: r[1] for r in specs}

            row = [
                comp["manufacturer_part_number"],
                comp["manufacturer"],
                comp["description"],
                comp["subcategory"],
                comp["stock"],
                comp["unit_price"],
                comp["package"],
                comp["mounting_type"],
                comp["lifecycle_status"],
                comp["datasheet_url"],
                comp["product_url"],
            ]
            for sname in cat_spec_names:
                row.append(spec_dict.get(sname, ""))

            writer.writerow(row)

    print(f"Exported {len(cat_components)} parts to: {cat_path}")

conn.close()
print("\nDone! Open the CSV files in Excel.")