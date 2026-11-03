"""Re-assign components to the right category from their DigiKey description.

The scraper stored whatever a category page returned, so many parts sit in the
wrong category (connectors under opto_ic, counters under gate_driver, ...).
Rules are checked in order; first match wins. Parts matching nothing keep their
category only if it is TRUSTED (its scrape was clean), else go to 'other'.

Run:  python reclassify.py          (dry run: before -> after matrix)
      python reclassify.py --apply
"""
import re
import sqlite3
import sys
from collections import Counter

DB_PATH = "ic_database.db"

TRUSTED = {"ldo_ic", "eeprom", "flash_memory", "fram_mram_sram", "mcu_soc", "temp_sensor",
           "protection_ic", "ambient_light"}

RULES = [  # (category, regex on UPPER-CASE description)
    ("other", r"\bCONN\b|CONNECTOR|HOUSING|RECEPTACLE|\bPLUG\b|\bKIT\b|COMPLETE SET|VIBRATION|PIEZO|ACCEL|"
              r"TRANSMITTER|MULTIPLIER|\bIC AMP\b|AMPLIFIER|TELECOM|SLIC\b|\bMULT\b|COMPARATOR|\bTS (?:RA|ST|PLUG)"),
    ("audio_ic", r"CODEC|AUDIO|STEREO|VOICEBAND|\bHDA\b|HEADPHONE|CLASS.?D|NOISE CANCEL"),
    ("mcu_soc", r"\bMCU\b|MICROCONTROLLER|\bARM\b"),  # before memory: MCU descriptions mention FLASH
    ("fram_mram_sram", r"\bFRAM\b|\bMRAM\b|SRAM|PSRAM"),
    ("eeprom", r"EEPROM"),
    ("flash_memory", r"FLASH|EPROM|DRAM|\bRAM\b"),
    ("gate_driver", r"GATE DRIVER|MOSFET DRIVER|IGBT DRIVER|HALF.?BRIDGE DRIVER"),
    ("protection_ic", r"\bTVS\b|\bESD\b|HOT.?SWAP|E-?FUSE|SURGE|OVERVOLTAGE|CURRENT LIMIT"),
    ("battery_management", r"BATT|CHARGER|LOAD SWITCH|PROFET|\bIPD\b|HIGH.?SIDE|POWER SWITCH|\bPWR SW"),
    ("power_sequencer", r"SEQUENCER|SUPERVIS|RESET|WATCHDOG|VOLTAGE MON"),
    ("retimer_ic", r"RETIMER|REDRIVER|REPEATER"),
    ("usb_ic", r"\bUSB\b|\bHUB\b|TYPE-?C"),
    ("video_interface", r"HDMI|DISPLAYPORT|LVDS|\bDVI\b|MIPI|SERIALIZER|DESERIALIZER|SERDES|SER/DESER|\bSER\b|\bDES\b|VIDEO"),
    ("serial_interface", r"UART|\bSPI\b|I2C|\bCAN\b|ETHERNET|\bBRIDGE\b|RS-?(?:232|485|422)|\bPC\b|\bMAC\b|MANAGED SWITCH"),
    ("display_driver", r"LED DRIVER|BACKLIGHT|\bLCD\b|\bOLED\b|DISPLAY DRIVER"),
    ("tcon_video", r"\bTCON\b|TIMING CONTROLLER|SCALER|VIDEO PROC"),
    ("clock_timing", r"CLOCK|OSCILLATOR|\bPLL\b|TIMER|SYNTHESIZER|JITTER"),
    ("hall_sensor", r"\bHALL\b|MAGNETIC"),
    ("ambient_light", r"LIGHT|COLOR SENSOR|PROXIMITY"),
    ("temp_sensor", r"TEMP|THERMAL"),
    ("opto_ic", r"OPTOCOUPLER|PHOTOCOUPLER|OPTOISOLATOR|ISOLATOR|PHOTO"),
    ("ldo_ic", r"LINEAR|\bLIN\b|\bLDO\b"),
    ("dcdc_converter", r"BUCK|BOOST|SWITCHING|DC.?DC|CONVERTER|\bPMIC\b|SW REG|^IC REG\b"),
    ("logic_mux", r"TRANSLAT|LEVEL|MUX|ANALOG SWITCH|BUS SWITCH|BUFFER|TRANSCEIVER|SHIFT|SHFT|\bSR\b|\bREG\b|REGISTER|CODEC"),
]
COMPILED = [(cat, re.compile(rx)) for cat, rx in RULES]


def classify(desc, current):
    d = (desc or "").upper()
    for cat, rx in COMPILED:
        if rx.search(d):
            return cat
    if d.startswith("IC REG"):  # bare "IC REG ...": LDO if scraped as one, else a switching regulator
        return "ldo_ic" if current == "ldo_ic" else "dcdc_converter"
    return current if current in TRUSTED else "other"


def main(apply):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT id, description, category FROM components").fetchall()
    moves = Counter()
    updates = []
    for cid, desc, cur in rows:
        new = classify(desc, cur)
        moves[(cur, new)] += 1
        if new != cur:
            updates.append((new, cid))
    print(f"{len(updates)} of {len(rows)} components change category")
    for (cur, new), n in sorted(moves.items(), key=lambda kv: -kv[1])[:40]:
        print(f"  {n:5d}  {cur} -> {new}")
    print("after:", dict(Counter(new for (_, new), n in moves.items() for _ in range(n)).most_common()))
    if apply:
        conn.executemany("UPDATE components SET category=? WHERE id=?", updates)
        conn.commit()
    conn.close()


if __name__ == "__main__":
    main("--apply" in sys.argv)
