"""
import_template.py — Import all 4 ODM Golden Templates into ic_database.db.

Creates:
  supply_chain table — operational/supply chain data
  datasheet_queue table — parts needing datasheets

Column names matched to actual template files:
  Foxconn, Qisda, BOEVT, TPV

Run: python import_template.py
"""

import sqlite3
import os
import re
import logging

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)-7s | %(message)s")
log = logging.getLogger("import_template")

try:
    import pandas as pd
    PANDAS_OK = True
except ImportError:
    PANDAS_OK = False

DB_PATH = "ic_database.db"

# Map template MPN Category to your config.py category slugs
CATEGORY_MAP = {
    "AUDIO AMPLIFIER": "audio_ic",
    "AUDIO CODEC": "audio_ic",
    "AUDIO IC": "audio_ic",
    "BUCK CONVERTOR": "dcdc_converter",
    "DC-DC CONVERTOR": "dcdc_converter",
    "DC-DC CONVERTER": "dcdc_converter",
    "DC/DC": "dcdc_converter",
    "LDO": "ldo_ic",
    "LINEAR REGULATOR": "ldo_ic",
    "PWM CONTROLLER": "dcdc_converter",
    "PWM CONTROLLER (VCORE/MEMORY/GPU)": "dcdc_converter",
    "LOGIC IC": "logic_mux",
    "MUX": "logic_mux",
    "LEVEL SHIFTER": "logic_mux",
    "MCU": "mcu_soc",
    "MICROCONTROLLER": "mcu_soc",
    "EEPROM": "eeprom",
    "FLASH": "flash_memory",
    "FLASH MEMORY": "flash_memory",
    "SRAM": "fram_mram_sram",
    "FRAM": "fram_mram_sram",
    "USB": "usb_ic",
    "USB IC": "usb_ic",
    "GATE DRIVER": "gate_driver",
    "MOSFET DRIVER": "gate_driver",
    "CLOCK": "clock_timing",
    "CLOCK IC": "clock_timing",
    "PLL": "clock_timing",
    "TIMING": "clock_timing",
    "PROTECTION": "protection_ic",
    "TVS": "protection_ic",
    "ESD": "protection_ic",
    "TEMP SENSOR": "temp_sensor",
    "TEMPERATURE SENSOR": "temp_sensor",
    "HALL": "hall_sensor",
    "RETIMER": "retimer_ic",
    "REDRIVER": "retimer_ic",
    "DISPLAY DRIVER": "display_driver",
    "LED DRIVER": "display_driver",
    "BACKLIGHT": "display_driver",
    "TCON": "tcon_video",
    "VIDEO": "video_interface",
    "HDMI": "video_interface",
    "DP": "video_interface",
    "SERIAL": "serial_interface",
    "OPTO": "opto_ic",
    "OPTOCOUPLER": "opto_ic",
    "BATTERY": "battery_management",
    "CHARGER": "battery_management",
    "POWER SEQUENCER": "power_sequencer",
    "SUPERVISOR": "power_sequencer",
    "AMBIENT LIGHT": "ambient_light",
    "SENSOR": "ambient_light",
    "IC": "unknown",
    "OTHERS": "unknown",
    # Unmapped categories from TPV/Foxconn/Qisda/BOEVT templates
    "SCALAR IC": "tcon_video",
    "SCALER IC": "tcon_video",
    "SCALER": "tcon_video",
    "POWER MANAGEMENT IC": "dcdc_converter",
    "POWER MANAGEMENT": "dcdc_converter",
    "POWER DISTRIBUTION SWITCHES": "protection_ic",
    "POWER DISTRIBUTION SWITCH": "protection_ic",
    "DRIVER IC": "gate_driver",
    "LOAD SWICTH": "protection_ic",
    "LOAD SWITCH": "protection_ic",
    "SWITCHING REGULATORS": "dcdc_converter",
    "SWITCHING REGULATOR": "dcdc_converter",
    "LAN CONTROLLER": "serial_interface",
    "LAN": "serial_interface",
    "ETHERNET": "serial_interface",
    "TYPE C LOAD SWITCH": "usb_ic",
    "TYPE-C LOAD SWITCH": "usb_ic",
    "POWER DELIVERY CONTROLLER": "usb_ic",
    "POWER DELIVERY CONTROLLER (PD CONTROLLER)": "usb_ic",
    "PD CONTROLLER": "usb_ic",
    "CAMERA CONTROLLER": "video_interface",
    "BUS SWITCH": "logic_mux",
}


def map_category(template_category):
    if not template_category:
        return "unknown"
    upper = template_category.strip().upper()
    if upper in CATEGORY_MAP:
        return CATEGORY_MAP[upper]
    for key, slug in CATEGORY_MAP.items():
        if key in upper or upper in key:
            return slug
    return "unknown"


def safe_int(val):
    if val is None:
        return None
    s = str(val).strip()
    if s in ("", "nan", "N/A", "Not Available", "Not Available  - Confidential", " "):
        return None
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def safe_str(val):
    if val is None:
        return None
    s = str(val).strip()
    if s in ("", "nan", "N/A", "Not Available", "Not Available  - Confidential", " "):
        return None
    return s


def create_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS supply_chain (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mpn TEXT NOT NULL,
            category_slug TEXT,
            parts_description TEXT,
            pin_count INTEGER,
            mpn_category TEXT,
            component_uniqueness TEXT,
            component_sourcing TEXT,
            package_type TEXT,
            manufacturing_model TEXT,
            dual_fab_plan TEXT,
            supplier_name TEXT,
            mpn_coo TEXT,

            fab1_supplier TEXT,
            fab1_country TEXT,
            fab1_city TEXT,
            fab2_supplier TEXT,
            fab2_country TEXT,
            fab2_city TEXT,
            fab3_supplier TEXT,
            fab3_country TEXT,
            fab3_city TEXT,

            assy1_supplier TEXT,
            assy1_country TEXT,
            assy1_city TEXT,
            assy2_supplier TEXT,
            assy2_country TEXT,
            assy2_city TEXT,

            test1_supplier TEXT,
            test1_country TEXT,
            test1_city TEXT,

            wafer_node_nm INTEGER,
            wafer_size_inch INTEGER,

            lead_time_days INTEGER,
            moq INTEGER,
            cancellation_window INTEGER,
            po_term TEXT,

            p2p_supplier TEXT,
            p2p_mpn TEXT,
            non_p2p_supplier TEXT,
            non_p2p_mpn TEXT,

            priority TEXT,
            scrm_status TEXT,
            em_dm TEXT,
            odm_code TEXT,
            odm_name TEXT,
            commodity TEXT,
            template_date TEXT,
            source_file TEXT,

            UNIQUE(mpn, odm_code)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS datasheet_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mpn TEXT NOT NULL UNIQUE,
            category_slug TEXT,
            pin_count INTEGER,
            package_type TEXT,
            source TEXT DEFAULT 'template',
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_sc_mpn ON supply_chain(mpn)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sc_cat ON supply_chain(category_slug)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sc_sourcing ON supply_chain(component_sourcing)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sc_odm ON supply_chain(odm_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dq_status ON datasheet_queue(status)")

    conn.commit()
    log.info("Created supply_chain and datasheet_queue tables")


def import_template(conn, filepath, template_date=None):
    if not PANDAS_OK:
        log.error("pandas required. Run: python -m pip install pandas openpyxl")
        return 0, 0

    if not os.path.exists(filepath):
        log.error("File not found: %s", filepath)
        return 0, 0

    if not template_date:
        m = re.search(r"(\d{8})", os.path.basename(filepath))
        if m:
            d = m.group(1)
            template_date = "{}-{}-{}".format(d[:4], d[4:6], d[6:8])
        else:
            template_date = "unknown"

    try:
        df = pd.read_excel(filepath, sheet_name=0, header=0)
    except Exception as e:
        log.error("Could not read %s: %s", filepath, e)
        return 0, 0

    log.info("Read %d rows, %d columns from %s",
             len(df), len(df.columns), os.path.basename(filepath))

    # Build case-insensitive column lookup
    col_lookup = {}
    for col in df.columns:
        col_lookup[str(col).strip().upper()] = col

    def get(row, *names):
        for name in names:
            key = name.strip().upper()
            if key in col_lookup:
                val = row.get(col_lookup[key])
                if pd.notna(val):
                    s = str(val).strip()
                    if s and s != "nan":
                        return s
        return None

    # Check which MPNs already exist in components table
    existing_mpns = set()
    try:
        rows = conn.execute(
            "SELECT manufacturer_part_number FROM components"
        ).fetchall()
        existing_mpns = {r[0] for r in rows}
    except Exception:
        pass

    imported = 0
    queued = 0
    skipped = 0

    for _, row in df.iterrows():
        mpn = get(row, "MPN")
        if not mpn or len(mpn) < 2:
            skipped += 1
            continue

        mpn_category = get(row, "MPN Category")
        category_slug = map_category(mpn_category)
        pin_count = safe_int(get(row, "Pin Count"))
        package_type = safe_str(get(row, "Package Type"))
        odm_code = get(row, "ODM Code") or "UNKNOWN"
        odm_name = get(row, "ODM Name") or ""

        try:
            conn.execute("""
                INSERT OR REPLACE INTO supply_chain (
                    mpn, category_slug, parts_description,
                    pin_count, mpn_category,
                    component_uniqueness, component_sourcing,
                    package_type, manufacturing_model, dual_fab_plan,
                    supplier_name, mpn_coo,
                    fab1_supplier, fab1_country, fab1_city,
                    fab2_supplier, fab2_country, fab2_city,
                    fab3_supplier, fab3_country, fab3_city,
                    assy1_supplier, assy1_country, assy1_city,
                    assy2_supplier, assy2_country, assy2_city,
                    test1_supplier, test1_country, test1_city,
                    wafer_node_nm, wafer_size_inch,
                    lead_time_days, moq, cancellation_window, po_term,
                    p2p_supplier, p2p_mpn,
                    non_p2p_supplier, non_p2p_mpn,
                    priority, scrm_status, em_dm,
                    odm_code, odm_name, commodity,
                    template_date, source_file
                ) VALUES (
                    ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                    ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                    ?,?,?,?,?,?
                )
            """, (
                mpn,
                category_slug,
                safe_str(get(row, "Parts Description")),
                pin_count,
                mpn_category,
                safe_str(get(row, "Component Uniqueness")),
                safe_str(get(row, "Component Sourcing")),
                package_type,
                safe_str(get(row, "Manufacturing Model")),
                safe_str(get(row, "Dual Fab Plan")),
                safe_str(get(row, "Supplier Name")),
                safe_str(get(row, "MPN COO")),
                # Fab sites
                safe_str(get(row, "1st Wafer Fab Supplier Name")),
                safe_str(get(row, "1st Wafer Fab Location (Country)")),
                safe_str(get(row, "1st Wafer Fab Location (State/Province,")),
                safe_str(get(row, "2nd Wafer Fab Supplier Name")),
                safe_str(get(row, "2nd Wafer Fab Location (Country)")),
                safe_str(get(row, "2nd Wafer Fab Location (State/Province,")),
                safe_str(get(row, "3rd Wafer Fab Supplier Name")),
                safe_str(get(row, "3rd Wafer Fab Location (Country)")),
                safe_str(get(row, "3rd Wafer Fab Location (State/Province,")),
                # Assembly sites
                safe_str(get(row, "1st Assembly Site Supplier Name")),
                safe_str(get(row, "1st Assembly Site Location (Country)")),
                safe_str(get(row, "1st Assembly Site Location (State/Provin")),
                safe_str(get(row, "2nd Assembly Site Supplier Name")),
                safe_str(get(row, "2nd Assembly Site Location (Country)")),
                safe_str(get(row, "2nd Assembly Site Location (State/Provin")),
                # Testing sites
                safe_str(get(row, "1st Testing Site Supplier Name")),
                safe_str(get(row, "1st Testing Site Location (Country)")),
                safe_str(get(row, "1st Testing Site Location (State/Provinc")),
                # Wafer info
                safe_int(get(row, "Wafer Node (nm)")),
                safe_int(get(row, "Wafer Size (Inch)")),
                # Procurement
                safe_int(get(row, "Lead Time")),
                safe_int(get(row, "MOQ")),
                safe_int(get(row, "Cancellation Window")),
                safe_str(get(row, "PO Term")),
                # P2P solutions
                safe_str(get(row, "Alternative P2P Solution Supplier")),
                safe_str(get(row, "Alternative P2P Solution MPN")),
                safe_str(get(row, "Alternative Non P2P Solution Supplier")),
                safe_str(get(row, "Alternative Non P2P Solution MPN")),
                # Metadata
                safe_str(get(row, "Priority")),
                safe_str(get(row, "SCRM Status")),
                safe_str(get(row, "EM/DM")),
                odm_code,
                odm_name,
                safe_str(get(row, "Commodity")),
                template_date,
                os.path.basename(filepath),
            ))
            imported += 1
        except Exception as e:
            log.debug("Error importing %s: %s", mpn, e)
            skipped += 1
            continue

        # Queue parts not in scraped database for datasheet lookup
        if mpn not in existing_mpns:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO datasheet_queue
                    (mpn, category_slug, pin_count, package_type)
                    VALUES (?, ?, ?, ?)
                """, (mpn, category_slug, pin_count, package_type))
                queued += 1
            except Exception:
                pass

        # Also queue P2P solution MPN
        p2p_mpn = safe_str(get(row, "Alternative P2P Solution MPN"))
        if p2p_mpn and p2p_mpn not in existing_mpns:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO datasheet_queue
                    (mpn, category_slug, pin_count, package_type, source)
                    VALUES (?, ?, ?, ?, 'p2p_solution')
                """, (p2p_mpn, category_slug, None, None))
            except Exception:
                pass

    conn.commit()
    log.info("Imported %d, queued %d for datasheet, skipped %d",
             imported, queued, skipped)
    return imported, queued


def show_stats(conn):
    total = conn.execute("SELECT COUNT(*) FROM supply_chain").fetchone()[0]
    print("\n=== SUPPLY CHAIN DATABASE ===")
    print("Total entries: {}".format(total))

    print("\nBy ODM:")
    rows = conn.execute(
        "SELECT odm_name, COUNT(*) as cnt FROM supply_chain "
        "GROUP BY odm_name ORDER BY cnt DESC"
    ).fetchall()
    for r in rows:
        print("  {:<35} {}".format(r[0] or "Unknown", r[1]))

    print("\nBy category:")
    rows = conn.execute(
        "SELECT category_slug, COUNT(*) as cnt FROM supply_chain "
        "GROUP BY category_slug ORDER BY cnt DESC"
    ).fetchall()
    for r in rows:
        print("  {:<25} {}".format(r[0], r[1]))

    print("\nBy sourcing type:")
    rows = conn.execute(
        "SELECT component_sourcing, COUNT(*) as cnt FROM supply_chain "
        "WHERE component_sourcing IS NOT NULL "
        "GROUP BY component_sourcing ORDER BY cnt DESC"
    ).fetchall()
    for r in rows:
        print("  {:<30} {}".format(r[0], r[1]))

    # P2P solutions
    p2p = conn.execute(
        "SELECT COUNT(*) FROM supply_chain WHERE p2p_mpn IS NOT NULL"
    ).fetchone()[0]
    print("\nParts with P2P solutions: {}".format(p2p))

    # Overlap with scraped database
    overlap = conn.execute("""
        SELECT COUNT(DISTINCT sc.mpn) FROM supply_chain sc
        INNER JOIN components c ON c.manufacturer_part_number = sc.mpn
    """).fetchone()[0]
    print("Overlap with scraped DB: {} parts".format(overlap))

    # Parts needing datasheets
    pending = conn.execute(
        "SELECT COUNT(*) FROM datasheet_queue WHERE status = 'pending'"
    ).fetchone()[0]
    print("Parts needing datasheets: {}".format(pending))
    print("")


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    create_tables(conn)

    template_files = []
    for folder in [".", "templates"]:
        if os.path.isdir(folder):
            for f in os.listdir(folder):
                if f.endswith((".xlsx", ".xls")) and not f.startswith("~"):
                    template_files.append(os.path.join(folder, f))

    if not template_files:
        print("No .xlsx files found in current directory or templates/ folder")
    else:
        for f in sorted(template_files):
            print("\nImporting: {}".format(os.path.basename(f)))
            import_template(conn, f)

    show_stats(conn)
    conn.close()