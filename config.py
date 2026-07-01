"""
config.py - Central configuration for the IC Database Engine.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import os

DB_PATH = os.environ.get("IC_DB_PATH", "ic_database.db")

REQUEST_DELAY_SECONDS = 2.0
PAGE_LOAD_TIMEOUT_MS  = 60_000
MAX_RETRIES           = 3
RESULTS_PER_PAGE      = 100
HEADLESS_MODE         = False
EDGE_CHANNEL          = "msedge"
DOWNLOAD_DIR          = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")

DIGIKEY_BASE       = "https://www.digikey.com"
DIGIKEY_IC_LANDING = f"{DIGIKEY_BASE}/en/products/category/integrated-circuits-ics/32"


@dataclass
class ICCategory:
    name: str
    slug: str
    digikey_subcategory_slugs: List[str]
    search_keywords: List[str]
    key_specifications: List[str]
    description: str = ""


CATEGORIES: Dict[str, ICCategory] = {

    "power_ic": ICCategory(
        name="Power IC",
        slug="power_ic",
        digikey_subcategory_slugs=[
            "pmic-voltage-regulators-linear",
            "pmic-voltage-regulators-dc-dc-switching-regulators",
            "pmic-voltage-regulators-dc-dc-switching-controllers",
            "pmic-voltage-regulators-dc-dc-converters",
            "pmic-full-half-bridge-drivers",
            "pmic-gate-drivers",
            "pmic-battery-management",
            "pmic-power-distribution-switches",
            "pmic-voltage-reference",
            "pmic-ac-dc-converters-offline-switchers",
            "pmic-led-drivers",
            "pmic-hot-swap-controllers",
            "pmic-motor-drivers-controllers",
            "pmic-or-controllers-ideal-diodes",
            "pmic-supervisors",
            "pmic-current-regulation-management",
            "pmic-power-management-specialized",
        ],
        search_keywords=[
            "voltage regulator", "LDO", "DC-DC converter",
            "buck converter", "boost converter", "PMIC",
            "gate driver", "LED driver", "battery charger",
        ],
        key_specifications=[
            "Output Voltage", "Input Voltage", "Output Current",
            "Dropout Voltage", "Quiescent Current", "Switching Frequency",
            "Efficiency", "Topology", "Number of Outputs",
            "Voltage - Input (Min)", "Voltage - Input (Max)",
            "Voltage - Output (Min/Fixed)", "Voltage - Output (Max)",
            "Current - Output", "Current - Quiescent (Iq)",
        ],
        description="Linear regulators, DC-DC converters, PMICs, gate drivers, LED drivers",
    ),

    "memory_ic": ICCategory(
        name="Memory IC",
        slug="memory_ic",
        digikey_subcategory_slugs=["memory", "sram", "dram", "fifo", "memory-configuration-proms-for-fpgas"],
        search_keywords=["SRAM", "DRAM", "SDRAM", "DDR memory", "FIFO memory"],
        key_specifications=["Memory Size", "Memory Type", "Memory Interface", "Clock Frequency", "Access Time", "Voltage - Supply", "Operating Temperature", "Write Endurance"],
        description="SRAM, DRAM, SDRAM, FIFO, and other volatile memory",
    ),

    "flash_ic": ICCategory(
        name="Flash IC",
        slug="flash_ic",
        digikey_subcategory_slugs=["nor-flash", "nand-flash", "eeprom", "flash"],
        search_keywords=["NOR flash", "NAND flash", "SPI flash", "EEPROM", "serial flash", "parallel flash"],
        key_specifications=["Memory Size", "Memory Interface", "Clock Frequency", "Write Cycle Time", "Write Endurance", "Data Retention", "Voltage - Supply", "Operating Temperature"],
        description="NOR flash, NAND flash, EEPROM, serial/parallel flash",
    ),

    "scalar_ic": ICCategory(
        name="Scalar IC",
        slug="scalar_ic",
        digikey_subcategory_slugs=["microcontrollers", "microprocessors", "digital-signal-processors-dsp", "fpga", "cpld", "system-on-chip-soc"],
        search_keywords=["microcontroller", "MCU", "ARM Cortex", "RISC-V", "DSP", "FPGA", "SoC"],
        key_specifications=["Core Processor", "Core Size", "Speed", "Program Memory Size", "RAM Size", "Number of I/O", "Peripherals", "Connectivity", "Voltage - Supply", "Operating Temperature"],
        description="Microcontrollers, microprocessors, DSPs, FPGAs",
    ),

    "audio_ic": ICCategory(
        name="Audio IC",
        slug="audio_ic",
        digikey_subcategory_slugs=["audio-special-purpose", "audio-amplifiers"],
        search_keywords=["audio codec", "audio amplifier", "DAC audio", "ADC audio", "class D amplifier", "audio DSP", "I2S"],
        key_specifications=["Type", "Output Type", "Output Power", "S/N Ratio", "THD + Noise", "Sample Rate", "Resolution (Bits)", "Number of Channels", "Interface", "Voltage - Supply"],
        description="Audio codecs, amplifiers, DACs, ADCs, Class-D drivers",
    ),

    "usb_ic": ICCategory(
        name="USB IC",
        slug="usb_ic",
        digikey_subcategory_slugs=["usb-interface-ics", "interface-controllers", "interface-specialized"],
        search_keywords=["USB controller", "USB hub", "USB switch", "USB Type-C", "USB PD", "USB transceiver", "USB bridge"],
        key_specifications=["Protocol", "USB Standard", "Data Rate", "Number of Ports", "Features", "Voltage - Supply", "Operating Temperature"],
        description="USB controllers, hubs, bridges, Type-C PD controllers",
    ),

    "sensor_ic": ICCategory(
        name="Sensor IC",
        slug="sensor_ic",
        digikey_subcategory_slugs=["temperature-sensors-analog-and-digital-output", "pressure-sensors-transducers", "magnetic-sensors-linear-compasses", "magnetic-sensors-hall-effect-switches", "accelerometers", "gyroscopes", "inertial-measurement-units-imus", "humidity-moisture-sensors", "ambient-light-sensors", "current-sensors", "image-sensors-camera", "proximity-sensors"],
        search_keywords=["temperature sensor", "accelerometer", "gyroscope", "IMU", "pressure sensor", "humidity sensor", "hall effect", "current sensor", "ambient light sensor"],
        key_specifications=["Sensor Type", "Sensing Range", "Sensitivity", "Accuracy", "Resolution", "Interface", "Output Type", "Voltage - Supply", "Operating Temperature", "Response Time"],
        description="Temperature, pressure, IMU, hall, current, light sensors",
    ),

    "protection_ic": ICCategory(
        name="Protection IC",
        slug="protection_ic",
        digikey_subcategory_slugs=["esd-suppressors-tvs", "esd-protection-diodes", "pmic-voltage-supervisors", "pmic-thermal-management", "over-voltage-protection"],
        search_keywords=["ESD protection", "TVS diode", "overvoltage protection", "voltage supervisor", "eFuse", "load switch protection"],
        key_specifications=["Type", "Voltage - Clamping", "Voltage - Breakdown", "Voltage - Reverse Standoff", "Current - Peak Pulse", "Number of Circuits", "Capacitance", "Voltage - Supply", "Operating Temperature"],
        description="ESD protection, TVS, voltage supervisors, eFuses",
    ),

    "mux_logic_ic": ICCategory(
        name="MUX/Logic IC",
        slug="mux_logic_ic",
        digikey_subcategory_slugs=["logic-buffers-drivers-receivers-transceivers", "logic-gates-and-inverters", "logic-flip-flops", "logic-shift-registers", "logic-counters-dividers", "logic-comparators", "logic-multiplexers", "logic-signal-switches-multiplexers-decoders", "logic-level-translators-shifters", "logic-latches"],
        search_keywords=["multiplexer", "logic gate", "buffer driver", "level shifter", "bus switch", "decoder", "shift register", "flip flop"],
        key_specifications=["Logic Type", "Number of Circuits", "Number of Inputs", "Number of Outputs", "Voltage - Supply", "Logic Level", "Propagation Delay", "Output Type", "Current - Output High/Low", "Operating Temperature"],
        description="Multiplexers, logic gates, buffers, level shifters, decoders",
    ),

    "ethernet_ic": ICCategory(
        name="Ethernet IC",
        slug="ethernet_ic",
        digikey_subcategory_slugs=["ethernet-ics", "interface-ethernet-controllers"],
        search_keywords=["Ethernet PHY", "Ethernet controller", "Ethernet switch", "Ethernet transceiver", "Ethernet MAC"],
        key_specifications=["Protocol", "Data Rate", "Number of Ports", "Interface", "Standards", "Features", "Voltage - Supply", "Operating Temperature"],
        description="Ethernet PHYs, MACs, controllers, switches",
    ),

    "opto_ic": ICCategory(
        name="Opto IC",
        slug="opto_ic",
        digikey_subcategory_slugs=["optoisolators-transistor-photovoltaic-output", "optoisolators-triac-scr-output", "optoisolators-logic-output", "optoisolators-gate-driver-output"],
        search_keywords=["optocoupler", "optoisolator", "photo coupler", "optical isolator", "gate driver opto"],
        key_specifications=["Output Type", "Number of Channels", "Current Transfer Ratio (CTR)", "Voltage - Isolation", "Voltage - Forward (Vf)", "Current - Input (If)", "Voltage - Output (Max)", "Current - Output / Channel", "Turn On / Turn Off Time", "Operating Temperature"],
        description="Optocouplers, optoisolators (transistor, triac, logic, gate driver output)",
    ),
}


def get_category(slug):
    return CATEGORIES.get(slug)


def all_category_slugs():
    return sorted(CATEGORIES.keys())
