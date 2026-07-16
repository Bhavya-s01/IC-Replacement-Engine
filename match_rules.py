"""
match_rules.py — Complete category-specific matching rules.

Every electrical-spec filter from the FPM replaceability matrix is
encoded as a SpecRule with weight, match_type, tolerance, and
required/optional status.

Reference: rigidflexpcb.org methodology for finding equivalent ICs [1].
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class SpecRule:
    """How to compare one specification."""
    spec_name: str
    weight: float = 1.0
    match_type: str = "exact"
    # "exact", "range_covers", "meets_or_exceeds", "contains", "numeric_close"
    tolerance_pct: float = 10.0
    required: bool = False
    aliases: List[str] = field(default_factory=list)


@dataclass
class CategoryRules:
    """Complete matching ruleset for one IC category."""
    category_slug: str
    rules: List[SpecRule]
    package_weight: float = 8.0
    mount_weight: float = 5.0
    temp_weight: float = 4.0
    lifecycle_weight: float = 3.0
    stock_weight: float = 0.0
    price_weight: float = 0.0


# ═══════════════════════════════════════════════════════
# DEFAULT (used when category is unknown)
# ═══════════════════════════════════════════════════════
DEFAULT_RULES = CategoryRules(
    category_slug="default",
    rules=[
        SpecRule("Voltage - Supply", weight=8, match_type="range_covers", required=True,
                 aliases=["Voltage - Supply (V)", "Supply Voltage"]),
    ]
)


# ═══════════════════════════════════════════════════════
# POWER IC — DC-DC converters, LDOs, MOSFET drivers
#
# Filters [1]:
#   Input-voltage range, Output-voltage and tolerance,
#   Max output current, Efficiency, Switching frequency,
#   Output ripple/noise, Thermal junction / Pd,
#   Enable/shutdown thresholds
# ═══════════════════════════════════════════════════════
DCDC_RULES = CategoryRules(
    category_slug="dcdc_converter",
    rules=[
        SpecRule("Voltage - Input (Min)", weight=8, match_type="numeric_close", tolerance_pct=15,
                 aliases=["Voltage - Input"]),
        SpecRule("Voltage - Input (Max)", weight=8, match_type="meets_or_exceeds"),
        SpecRule("Voltage - Output (Min/Fixed)", weight=10, match_type="numeric_close",
                 tolerance_pct=5, required=True,
                 aliases=["Voltage - Output", "Output Voltage"]),
        SpecRule("Voltage - Output (Max)", weight=7, match_type="meets_or_exceeds"),
        SpecRule("Current - Output", weight=9, match_type="meets_or_exceeds", required=True,
                 aliases=["Current - Output (Max)"]),
        SpecRule("Switching Frequency", weight=5, match_type="numeric_close", tolerance_pct=30,
                 aliases=["Frequency - Switching"]),
        SpecRule("Topology", weight=7, match_type="exact"),
        SpecRule("Efficiency", weight=5, match_type="meets_or_exceeds"),
        SpecRule("Number of Outputs", weight=6, match_type="exact"),
        SpecRule("Output Configuration", weight=5, match_type="exact"),
        SpecRule("Voltage - Ripple", weight=4, match_type="numeric_close", tolerance_pct=30,
                 aliases=["Output Ripple", "Ripple"]),
        SpecRule("Power Dissipation", weight=4, match_type="meets_or_exceeds",
                 aliases=["Power (Max)", "Pd"]),
        SpecRule("Shutdown Voltage", weight=3, match_type="numeric_close", tolerance_pct=20,
                 aliases=["Enable Voltage", "Enable/Shutdown"]),
    ],
    package_weight=8, temp_weight=5,
)

LDO_RULES = CategoryRules(
    category_slug="ldo_ic",
    rules=[
        SpecRule("Voltage - Output (Min/Fixed)", weight=10, match_type="numeric_close",
                 tolerance_pct=3, required=True,
                 aliases=["Voltage - Output", "Output Voltage"]),
        SpecRule("Voltage - Input (Max)", weight=8, match_type="meets_or_exceeds"),
        SpecRule("Voltage - Input (Min)", weight=7, match_type="numeric_close", tolerance_pct=15),
        SpecRule("Current - Output", weight=9, match_type="meets_or_exceeds", required=True,
                 aliases=["Current - Output (Max)"]),
        SpecRule("Voltage Dropout (Max)", weight=7, match_type="numeric_close", tolerance_pct=30,
                 aliases=["Dropout Voltage"]),
        SpecRule("Current - Quiescent (Iq)", weight=5, match_type="numeric_close", tolerance_pct=50,
                 aliases=["Quiescent Current"]),
        SpecRule("Output Type", weight=6, match_type="exact"),
        SpecRule("Output Configuration", weight=5, match_type="exact"),
        SpecRule("Number of Regulators", weight=6, match_type="exact"),
        SpecRule("PSRR", weight=4, match_type="meets_or_exceeds",
                 aliases=["Power Supply Rejection Ratio"]),
        SpecRule("Efficiency", weight=4, match_type="meets_or_exceeds"),
        SpecRule("Power Dissipation", weight=4, match_type="meets_or_exceeds",
                 aliases=["Thermal Rating", "Power (Max)"]),
        SpecRule("Shutdown Voltage", weight=3, match_type="numeric_close", tolerance_pct=20,
                 aliases=["Enable Voltage"]),
    ],
    package_weight=8, temp_weight=5,
)

GATE_DRIVER_RULES = CategoryRules(
    category_slug="gate_driver",
    rules=[
        SpecRule("Voltage - Supply", weight=9, match_type="range_covers", required=True,
                 aliases=["Voltage - Supply (V)"]),
        SpecRule("Current - Peak Output", weight=8, match_type="meets_or_exceeds",
                 aliases=["Current - Output"]),
        SpecRule("Gate Type", weight=7, match_type="exact"),
        SpecRule("Configuration", weight=7, match_type="exact"),
        SpecRule("Number of Drivers", weight=6, match_type="exact"),
        SpecRule("Input Type", weight=5, match_type="exact"),
        SpecRule("Rise / Fall Time", weight=5, match_type="numeric_close", tolerance_pct=30,
                 aliases=["Rise Time", "Fall Time"]),
        SpecRule("Power Dissipation", weight=4, match_type="meets_or_exceeds"),
    ],
    package_weight=8,
)


# ═══════════════════════════════════════════════════════
# AUDIO IC — DAC/ADC, amplifiers, codecs
#
# Filters [1]:
#   Supply voltage and range, Supply current,
#   Output swing / head-room, THD+N, Audio bandwidth,
#   Input impedance / bias current, Power-down current,
#   Clock type & frequency
# ═══════════════════════════════════════════════════════
AUDIO_RULES = CategoryRules(
    category_slug="audio_ic",
    rules=[
        SpecRule("Voltage - Supply", weight=8, match_type="range_covers", required=True,
                 aliases=["Voltage - Supply (V)", "Supply Voltage", "VDD"]),
        SpecRule("Current - Supply", weight=5, match_type="numeric_close", tolerance_pct=30,
                 aliases=["Supply Current", "Current - Quiescent"]),
        SpecRule("Output Power", weight=7, match_type="meets_or_exceeds",
                 aliases=["Output Swing", "Vout-peak"]),
        SpecRule("THD + Noise", weight=7, match_type="numeric_close", tolerance_pct=50,
                 aliases=["THD+N", "Distortion"]),
        SpecRule("Number of Channels", weight=8, match_type="exact"),
        SpecRule("Type", weight=8, match_type="contains"),
        SpecRule("S/N Ratio", weight=5, match_type="meets_or_exceeds",
                 aliases=["SNR", "Signal-to-Noise"]),
        SpecRule("Sample Rate", weight=5, match_type="meets_or_exceeds",
                 aliases=["Bandwidth", "Audio Bandwidth"]),
        SpecRule("Resolution (Bits)", weight=5, match_type="meets_or_exceeds",
                 aliases=["Bits"]),
        SpecRule("Interface", weight=5, match_type="contains"),
        SpecRule("Input Impedance", weight=3, match_type="numeric_close", tolerance_pct=30),
        SpecRule("Current - Power Down", weight=3, match_type="numeric_close", tolerance_pct=50,
                 aliases=["Power-Down Current", "Shutdown Current"]),
        SpecRule("Clock Frequency", weight=4, match_type="numeric_close", tolerance_pct=20,
                 aliases=["Clock Type"]),
    ],
    package_weight=7, temp_weight=4,
)


# ═══════════════════════════════════════════════════════
# USB IC — USB-C/3.x PHYs, hubs, charging controllers
#
# Filters [1]:
#   VBUS voltage range, I-source/sink limits,
#   Data-rate support, VBUS detection thresholds,
#   PD profile options, ESD rating, Clock/ref frequency
# ═══════════════════════════════════════════════════════
USB_RULES = CategoryRules(
    category_slug="usb_ic",
    rules=[
        SpecRule("Protocol", weight=10, match_type="contains", required=True,
                 aliases=["USB Standard"]),
        SpecRule("Voltage - Supply", weight=7, match_type="range_covers",
                 aliases=["VBUS Voltage", "Voltage - VBUS"]),
        SpecRule("Data Rate", weight=9, match_type="meets_or_exceeds",
                 aliases=["Speed"]),
        SpecRule("Number of Ports", weight=7, match_type="exact"),
        SpecRule("Current - Output", weight=6, match_type="meets_or_exceeds",
                 aliases=["Current - Source", "Current - Sink", "I-source"]),
        SpecRule("Features", weight=5, match_type="contains"),
        SpecRule("ESD Rating", weight=4, match_type="meets_or_exceeds",
                 aliases=["ESD Protection"]),
        SpecRule("Clock Frequency", weight=4, match_type="numeric_close", tolerance_pct=10,
                 aliases=["Reference Frequency"]),
        SpecRule("Power Delivery", weight=5, match_type="contains",
                 aliases=["PD Profile", "USB PD"]),
    ],
    package_weight=7,
)


# ═══════════════════════════════════════════════════════
# SCALAR / CLOCK IC — PLL, timing generators
#
# Filters [1]:
#   Input ref frequency range, Output frequency & jitter,
#   Loop bandwidth / lock-time, Supply voltage & current,
#   Output drive strength, Spread-spectrum percentage
# ═══════════════════════════════════════════════════════
CLOCK_TIMING_RULES = CategoryRules(
    category_slug="clock_timing",
    rules=[
        SpecRule("Frequency", weight=9, match_type="numeric_close", tolerance_pct=5,
                 aliases=["Frequency - Output", "Output Frequency"]),
        SpecRule("Frequency - Input", weight=7, match_type="range_covers",
                 aliases=["Input Frequency", "Reference Frequency"]),
        SpecRule("Type", weight=7, match_type="contains"),
        SpecRule("Voltage - Supply", weight=7, match_type="range_covers"),
        SpecRule("Current - Supply", weight=4, match_type="numeric_close", tolerance_pct=30),
        SpecRule("Number of Outputs", weight=6, match_type="exact"),
        SpecRule("Output Type", weight=6, match_type="exact",
                 aliases=["Output Drive"]),
        SpecRule("Jitter", weight=6, match_type="numeric_close", tolerance_pct=30,
                 aliases=["Phase Jitter", "Jitter (RMS)"]),
        SpecRule("Spread Spectrum", weight=4, match_type="contains",
                 aliases=["Spread-Spectrum"]),
        SpecRule("Lock Time", weight=3, match_type="numeric_close", tolerance_pct=50),
    ],
    package_weight=7,
)


# ═══════════════════════════════════════════════════════
# SENSOR IC — ambient-light, temperature, proximity
#
# Filters [1]:
#   Supply voltage range, Operating current,
#   Measurement range, Output type, Temp coefficient,
#   PSRR
# ═══════════════════════════════════════════════════════
AMBIENT_LIGHT_RULES = CategoryRules(
    category_slug="ambient_light",
    rules=[
        SpecRule("Sensor Type", weight=8, match_type="contains"),
        SpecRule("Voltage - Supply", weight=7, match_type="range_covers"),
        SpecRule("Current - Supply", weight=5, match_type="numeric_close", tolerance_pct=30,
                 aliases=["Operating Current"]),
        SpecRule("Sensing Range", weight=6, match_type="contains",
                 aliases=["Measurement Range"]),
        SpecRule("Interface", weight=7, match_type="exact",
                 aliases=["Output Type"]),
        SpecRule("Accuracy", weight=5, match_type="numeric_close", tolerance_pct=30,
                 aliases=["Temperature Coefficient"]),
        SpecRule("Resolution", weight=5, match_type="meets_or_exceeds"),
        SpecRule("PSRR", weight=3, match_type="meets_or_exceeds",
                 aliases=["Supply Noise Rejection"]),
    ],
)

TEMP_SENSOR_RULES = CategoryRules(
    category_slug="temp_sensor",
    rules=[
        SpecRule("Sensor Type", weight=7, match_type="contains"),
        SpecRule("Voltage - Supply", weight=7, match_type="range_covers"),
        SpecRule("Current - Supply", weight=4, match_type="numeric_close", tolerance_pct=30,
                 aliases=["Operating Current"]),
        SpecRule("Sensing Range", weight=6, match_type="range_covers",
                 aliases=["Measurement Range", "Temperature Range"]),
        SpecRule("Accuracy", weight=8, match_type="numeric_close", tolerance_pct=30),
        SpecRule("Resolution", weight=6, match_type="meets_or_exceeds"),
        SpecRule("Interface", weight=7, match_type="exact",
                 aliases=["Output Type"]),
        SpecRule("Temperature Coefficient", weight=4, match_type="numeric_close", tolerance_pct=30),
    ],
)

HALL_SENSOR_RULES = CategoryRules(
    category_slug="hall_sensor",
    rules=[
        SpecRule("Sensor Type", weight=8, match_type="contains"),
        SpecRule("Voltage - Supply", weight=7, match_type="range_covers"),
        SpecRule("Output Type", weight=7, match_type="exact"),
        SpecRule("Sensitivity", weight=6, match_type="numeric_close", tolerance_pct=20),
        SpecRule("Operating Point", weight=5, match_type="numeric_close", tolerance_pct=20),
        SpecRule("Current - Supply", weight=4, match_type="numeric_close", tolerance_pct=30),
    ],
)


# ═══════════════════════════════════════════════════════
# MEMORY IC — SPI-Flash, EEPROM, SRAM
#
# Filters [1]:
#   Supply voltage and range, Operating current,
#   Read/write speed, Endurance/retention,
#   Package voltage-rating
# ═══════════════════════════════════════════════════════
FLASH_RULES = CategoryRules(
    category_slug="flash_memory",
    rules=[
        SpecRule("Memory Size", weight=10, match_type="exact", required=True),
        SpecRule("Memory Interface", weight=9, match_type="exact", required=True,
                 aliases=["Memory Type", "Interface"]),
        SpecRule("Voltage - Supply", weight=8, match_type="range_covers"),
        SpecRule("Clock Frequency", weight=6, match_type="meets_or_exceeds",
                 aliases=["Read Speed", "Speed"]),
        SpecRule("Write Endurance", weight=5, match_type="meets_or_exceeds",
                 aliases=["Endurance"]),
        SpecRule("Data Retention", weight=4, match_type="meets_or_exceeds",
                 aliases=["Retention"]),
        SpecRule("Current - Supply", weight=4, match_type="numeric_close", tolerance_pct=30,
                 aliases=["Operating Current"]),
    ],
    package_weight=9,
)

EEPROM_RULES = CategoryRules(
    category_slug="eeprom",
    rules=[
        SpecRule("Memory Size", weight=10, match_type="exact", required=True),
        SpecRule("Memory Interface", weight=9, match_type="exact", required=True,
                 aliases=["Interface"]),
        SpecRule("Voltage - Supply", weight=8, match_type="range_covers"),
        SpecRule("Clock Frequency", weight=5, match_type="meets_or_exceeds",
                 aliases=["Speed"]),
        SpecRule("Write Cycle Time", weight=4, match_type="numeric_close", tolerance_pct=50),
        SpecRule("Write Endurance", weight=5, match_type="meets_or_exceeds",
                 aliases=["Endurance"]),
        SpecRule("Data Retention", weight=4, match_type="meets_or_exceeds"),
        SpecRule("Current - Supply", weight=4, match_type="numeric_close", tolerance_pct=30),
    ],
    package_weight=9,
)

FRAM_MRAM_SRAM_RULES = CategoryRules(
    category_slug="fram_mram_sram",
    rules=[
        SpecRule("Memory Size", weight=10, match_type="exact", required=True),
        SpecRule("Memory Type", weight=9, match_type="exact", required=True),
        SpecRule("Memory Interface", weight=8, match_type="exact", required=True,
                 aliases=["Interface"]),
        SpecRule("Voltage - Supply", weight=7, match_type="range_covers"),
        SpecRule("Clock Frequency", weight=5, match_type="meets_or_exceeds"),
        SpecRule("Write Endurance", weight=5, match_type="meets_or_exceeds"),
        SpecRule("Current - Supply", weight=4, match_type="numeric_close", tolerance_pct=30),
    ],
)


# ═══════════════════════════════════════════════════════
# MUX / SWITCH IC — video-path multiplexers, level shifters
#
# Filters [1]:
#   Supply voltages, On-resistance / leakage,
#   Signal-voltage swing, Propagation delay / bandwidth,
#   Enable-pin thresholds, ESD rating
# ═══════════════════════════════════════════════════════
LOGIC_MUX_RULES = CategoryRules(
    category_slug="logic_mux",
    rules=[
        SpecRule("Voltage - Supply", weight=8, match_type="range_covers"),
        SpecRule("Logic Type", weight=8, match_type="contains"),
        SpecRule("Number of Circuits", weight=7, match_type="exact"),
        SpecRule("On-State Resistance (Max)", weight=6, match_type="numeric_close", tolerance_pct=30,
                 aliases=["On-Resistance", "RON"]),
        SpecRule("Propagation Delay", weight=5, match_type="numeric_close", tolerance_pct=30,
                 aliases=["Delay"]),
        SpecRule("Bandwidth", weight=5, match_type="meets_or_exceeds"),
        SpecRule("Voltage - Supply (Vcc/Vdd)", weight=6, match_type="range_covers",
                 aliases=["Signal Voltage"]),
        SpecRule("Current - Leakage", weight=3, match_type="numeric_close", tolerance_pct=50),
        SpecRule("ESD Rating", weight=3, match_type="meets_or_exceeds"),
    ],
)


# ═══════════════════════════════════════════════════════
# PROTECTION IC — TVS, OVP, over-current
#
# Filters [1]:
#   Standby voltage / clamping voltage,
#   Breakdown voltage, Peak pulse current,
#   Power dissipation, Operating temperature
# ═══════════════════════════════════════════════════════
PROTECTION_RULES = CategoryRules(
    category_slug="protection_ic",
    rules=[
        SpecRule("Voltage - Clamping", weight=9, match_type="numeric_close", tolerance_pct=10,
                 aliases=["Clamping Voltage", "VC"]),
        SpecRule("Voltage - Breakdown", weight=9, match_type="numeric_close", tolerance_pct=10,
                 aliases=["Breakdown Voltage", "VBR"]),
        SpecRule("Voltage - Reverse Standoff", weight=8, match_type="meets_or_exceeds",
                 aliases=["Standby Voltage", "VWR", "VRWM"]),
        SpecRule("Current - Peak Pulse", weight=7, match_type="meets_or_exceeds",
                 aliases=["Peak Pulse Current", "IPP"]),
        SpecRule("Power - Peak Pulse", weight=6, match_type="meets_or_exceeds",
                 aliases=["Power Dissipation", "Peak Power"]),
        SpecRule("Type", weight=7, match_type="contains"),
        SpecRule("Number of Circuits", weight=6, match_type="exact"),
        SpecRule("Capacitance", weight=4, match_type="numeric_close", tolerance_pct=30),
    ],
)


# ═══════════════════════════════════════════════════════
# RETIMER / RE-DRIVER IC
#
# Filters [1]:
#   Supply voltage & current, Data-rate (Gbps),
#   Jitter & eye-width, Equalization settings,
#   Power-down current, Voltage-tolerance on diff pairs
# ═══════════════════════════════════════════════════════
RETIMER_RULES = CategoryRules(
    category_slug="retimer_ic",
    rules=[
        SpecRule("Protocol", weight=10, match_type="contains", required=True),
        SpecRule("Data Rate", weight=9, match_type="meets_or_exceeds",
                 aliases=["Speed", "Bandwidth"]),
        SpecRule("Voltage - Supply", weight=6, match_type="range_covers"),
        SpecRule("Current - Supply", weight=4, match_type="numeric_close", tolerance_pct=30),
        SpecRule("Number of Channels", weight=7, match_type="exact",
                 aliases=["Number of Lanes"]),
        SpecRule("Type", weight=5, match_type="contains"),
        SpecRule("Jitter", weight=6, match_type="numeric_close", tolerance_pct=30,
                 aliases=["Output Jitter"]),
        SpecRule("Equalization", weight=4, match_type="contains"),
        SpecRule("Current - Power Down", weight=3, match_type="numeric_close", tolerance_pct=50,
                 aliases=["Shutdown Current"]),
    ],
)


# ═══════════════════════════════════════════════════════
# MCU / SoC IC — panel-control processors
#
# Filters [1]:
#   Core supply voltage & I/O supply rails,
#   Max supply current, Operating temp range,
#   Clock source & frequency, Wake-up/sleep current,
#   Flash/ROM interface voltage levels
# ═══════════════════════════════════════════════════════
MCU_RULES = CategoryRules(
    category_slug="mcu_soc",
    rules=[
        SpecRule("Core Processor", weight=9, match_type="contains", required=True),
        SpecRule("Speed", weight=7, match_type="meets_or_exceeds",
                 aliases=["Clock Frequency", "Clock Speed"]),
        SpecRule("Program Memory Size", weight=8, match_type="meets_or_exceeds",
                 aliases=["Flash Size"]),
        SpecRule("RAM Size", weight=7, match_type="meets_or_exceeds"),
        SpecRule("Number of I/O", weight=6, match_type="meets_or_exceeds",
                 aliases=["GPIO"]),
        SpecRule("Voltage - Supply", weight=6, match_type="range_covers",
                 aliases=["Voltage - Supply (Vcc/Vdd)"]),
        SpecRule("Connectivity", weight=5, match_type="contains"),
        SpecRule("Peripherals", weight=4, match_type="contains"),
        SpecRule("Current - Supply", weight=4, match_type="numeric_close", tolerance_pct=30,
                 aliases=["Max Supply Current"]),
        SpecRule("Current - Sleep", weight=3, match_type="numeric_close", tolerance_pct=50,
                 aliases=["Wake-up Current", "Standby Current"]),
    ],
)


# ═══════════════════════════════════════════════════════
# REMAINING CATEGORIES
# ═══════════════════════════════════════════════════════
BATTERY_RULES = CategoryRules(
    category_slug="battery_management",
    rules=[
        SpecRule("Battery Chemistry", weight=10, match_type="exact", required=True),
        SpecRule("Number of Cells", weight=9, match_type="exact"),
        SpecRule("Current - Charging", weight=8, match_type="meets_or_exceeds"),
        SpecRule("Voltage - Supply", weight=7, match_type="range_covers"),
        SpecRule("Interface", weight=5, match_type="contains"),
        SpecRule("Function", weight=6, match_type="contains"),
    ],
)

POWER_SEQUENCER_RULES = CategoryRules(
    category_slug="power_sequencer",
    rules=[
        SpecRule("Voltage - Threshold", weight=9, match_type="numeric_close", tolerance_pct=5),
        SpecRule("Number of Voltages Monitored", weight=7, match_type="exact"),
        SpecRule("Output Type", weight=6, match_type="exact"),
        SpecRule("Voltage - Supply", weight=8, match_type="range_covers"),
        SpecRule("Reset", weight=5, match_type="exact"),
    ],
)

VIDEO_INTERFACE_RULES = CategoryRules(
    category_slug="video_interface",
    rules=[
        SpecRule("Protocol", weight=10, match_type="contains", required=True),
        SpecRule("Data Rate", weight=8, match_type="meets_or_exceeds"),
        SpecRule("Number of Channels", weight=7, match_type="exact"),
        SpecRule("Voltage - Supply", weight=6, match_type="range_covers"),
        SpecRule("Resolution", weight=5, match_type="contains"),
    ],
)

SERIAL_INTERFACE_RULES = CategoryRules(
    category_slug="serial_interface",
    rules=[
        SpecRule("Protocol", weight=10, match_type="contains", required=True),
        SpecRule("Data Rate", weight=7, match_type="meets_or_exceeds"),
        SpecRule("Number of Channels", weight=6, match_type="exact"),
        SpecRule("Voltage - Supply", weight=6, match_type="range_covers"),
        SpecRule("Features", weight=4, match_type="contains"),
    ],
)

DISPLAY_DRIVER_RULES = CategoryRules(
    category_slug="display_driver",
    rules=[
        SpecRule("Topology", weight=8, match_type="exact"),
        SpecRule("Current - Output", weight=9, match_type="meets_or_exceeds"),
        SpecRule("Voltage - Input", weight=7, match_type="range_covers"),
        SpecRule("Number of Outputs", weight=7, match_type="exact"),
        SpecRule("Dimming", weight=5, match_type="contains"),
        SpecRule("Output Configuration", weight=5, match_type="exact"),
    ],
)

TCON_RULES = CategoryRules(
    category_slug="tcon_video",
    rules=[
        SpecRule("Type", weight=8, match_type="contains"),
        SpecRule("Interface", weight=7, match_type="contains"),
        SpecRule("Resolution", weight=6, match_type="contains"),
        SpecRule("Voltage - Supply", weight=5, match_type="range_covers"),
    ],
)

OPTO_RULES = CategoryRules(
    category_slug="opto_ic",
    rules=[
        SpecRule("Output Type", weight=8, match_type="exact"),
        SpecRule("Number of Channels", weight=7, match_type="exact"),
        SpecRule("Voltage - Isolation", weight=8, match_type="meets_or_exceeds"),
        SpecRule("Current Transfer Ratio (CTR)", weight=6, match_type="numeric_close",
                 tolerance_pct=30, aliases=["CTR"]),
        SpecRule("Turn On / Turn Off Time", weight=4, match_type="numeric_close", tolerance_pct=30),
        SpecRule("Voltage - Forward (Vf)", weight=5, match_type="numeric_close", tolerance_pct=15),
        SpecRule("Current - Input (If)", weight=5, match_type="numeric_close", tolerance_pct=20),
    ],
)


# ═══════════════════════════════════════════════════════
# MASTER REGISTRY
# ═══════════════════════════════════════════════════════
RULES: Dict[str, CategoryRules] = {
    "dcdc_converter":      DCDC_RULES,
    "ldo_ic":              LDO_RULES,
    "gate_driver":         GATE_DRIVER_RULES,
    "power_sequencer":     POWER_SEQUENCER_RULES,
    "battery_management":  BATTERY_RULES,
    "usb_ic":              USB_RULES,
    "video_interface":     VIDEO_INTERFACE_RULES,
    "serial_interface":    SERIAL_INTERFACE_RULES,
    "display_driver":      DISPLAY_DRIVER_RULES,
    "tcon_video":          TCON_RULES,
    "flash_memory":        FLASH_RULES,
    "eeprom":              EEPROM_RULES,
    "fram_mram_sram":      FRAM_MRAM_SRAM_RULES,
    "audio_ic":            AUDIO_RULES,
    "ambient_light":       AMBIENT_LIGHT_RULES,
    "temp_sensor":         TEMP_SENSOR_RULES,
    "hall_sensor":         HALL_SENSOR_RULES,
    "protection_ic":       PROTECTION_RULES,
    "clock_timing":        CLOCK_TIMING_RULES,
    "logic_mux":           LOGIC_MUX_RULES,
    "mcu_soc":             MCU_RULES,
    "retimer_ic":          RETIMER_RULES,
    "opto_ic":             OPTO_RULES,
}


def get_rules(category_slug):
    """Return the matching rules for a category, or defaults."""
    return RULES.get(category_slug, DEFAULT_RULES)