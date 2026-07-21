"""
match_rules.py — Full category-specific matching rules.
Every spec filter from the FPM replaceability matrix is encoded here.
Stock and price weights are 0 (purely technical comparison).
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class SpecRule:
    spec_name: str
    weight: float = 1.0
    match_type: str = "exact"
    tolerance_pct: float = 10.0
    required: bool = False
    aliases: List[str] = field(default_factory=list)


@dataclass
class CategoryRules:
    category_slug: str
    rules: List[SpecRule]
    package_weight: float = 8.0
    mount_weight: float = 5.0
    temp_weight: float = 4.0
    lifecycle_weight: float = 3.0
    stock_weight: float = 0.0
    price_weight: float = 0.0


DEFAULT_RULES = CategoryRules(
    category_slug="default",
    rules=[SpecRule("Voltage - Supply", weight=8, match_type="range_covers", required=True,
                    aliases=["Voltage - Supply (V)", "Supply Voltage"])],
)

RULES: Dict[str, CategoryRules] = {

    "dcdc_converter": CategoryRules("dcdc_converter", rules=[
        SpecRule("Voltage - Input (Min)", weight=8, match_type="numeric_close", tolerance_pct=15, aliases=["Voltage - Input"]),
        SpecRule("Voltage - Input (Max)", weight=8, match_type="meets_or_exceeds"),
        SpecRule("Voltage - Output (Min/Fixed)", weight=10, match_type="numeric_close", tolerance_pct=5, required=True, aliases=["Voltage - Output", "Output Voltage"]),
        SpecRule("Voltage - Output (Max)", weight=7, match_type="meets_or_exceeds"),
        SpecRule("Current - Output", weight=9, match_type="meets_or_exceeds", required=True, aliases=["Current - Output (Max)"]),
        SpecRule("Switching Frequency", weight=5, match_type="numeric_close", tolerance_pct=30, aliases=["Frequency - Switching"]),
        SpecRule("Topology", weight=7, match_type="exact"),
        SpecRule("Efficiency", weight=5, match_type="meets_or_exceeds"),
        SpecRule("Number of Outputs", weight=6, match_type="exact"),
        SpecRule("Output Configuration", weight=5, match_type="exact"),
        SpecRule("Output Ripple", weight=4, match_type="numeric_close", tolerance_pct=30, aliases=["Voltage - Ripple", "Ripple"]),
        SpecRule("Thermal Resistance JA", weight=3, match_type="numeric_close", tolerance_pct=30),
        SpecRule("Enable Threshold", weight=3, match_type="numeric_close", tolerance_pct=20, aliases=["Shutdown Voltage", "Enable Voltage"]),
    ]),

    "ldo_ic": CategoryRules("ldo_ic", rules=[
        SpecRule("Voltage - Output (Min/Fixed)", weight=10, match_type="numeric_close", tolerance_pct=3, required=True, aliases=["Voltage - Output", "Output Voltage"]),
        SpecRule("Voltage - Input (Max)", weight=8, match_type="meets_or_exceeds"),
        SpecRule("Voltage - Input (Min)", weight=7, match_type="numeric_close", tolerance_pct=15),
        SpecRule("Current - Output", weight=9, match_type="meets_or_exceeds", required=True, aliases=["Current - Output (Max)"]),
        SpecRule("Voltage Dropout (Max)", weight=7, match_type="numeric_close", tolerance_pct=30, aliases=["Dropout Voltage"]),
        SpecRule("Current - Quiescent (Iq)", weight=5, match_type="numeric_close", tolerance_pct=50, aliases=["Quiescent Current"]),
        SpecRule("Output Type", weight=6, match_type="exact"),
        SpecRule("Output Configuration", weight=5, match_type="exact"),
        SpecRule("Number of Regulators", weight=6, match_type="exact"),
        SpecRule("PSRR", weight=4, match_type="meets_or_exceeds", aliases=["Power Supply Rejection Ratio"]),
        SpecRule("Output Noise", weight=3, match_type="numeric_close", tolerance_pct=50, aliases=["Output Noise RMS"]),
        SpecRule("Load Regulation", weight=3, match_type="numeric_close", tolerance_pct=30),
        SpecRule("Line Regulation", weight=3, match_type="numeric_close", tolerance_pct=30),
    ]),

    "gate_driver": CategoryRules("gate_driver", rules=[
        SpecRule("Voltage - Supply", weight=9, match_type="range_covers", required=True),
        SpecRule("Current - Peak Output", weight=8, match_type="meets_or_exceeds", aliases=["Current - Output"]),
        SpecRule("Gate Type", weight=7, match_type="exact"),
        SpecRule("Configuration", weight=7, match_type="exact"),
        SpecRule("Number of Drivers", weight=6, match_type="exact"),
        SpecRule("Input Type", weight=5, match_type="exact"),
        SpecRule("Rise / Fall Time", weight=5, match_type="numeric_close", tolerance_pct=30),
        SpecRule("Propagation Delay", weight=4, match_type="numeric_close", tolerance_pct=30),
    ]),

    "power_sequencer": CategoryRules("power_sequencer", rules=[
        SpecRule("Voltage - Threshold", weight=9, match_type="numeric_close", tolerance_pct=5),
        SpecRule("Number of Voltages Monitored", weight=7, match_type="exact"),
        SpecRule("Output Type", weight=6, match_type="exact"),
        SpecRule("Voltage - Supply", weight=8, match_type="range_covers"),
        SpecRule("Reset", weight=5, match_type="exact"),
    ]),

    "battery_management": CategoryRules("battery_management", rules=[
        SpecRule("Battery Chemistry", weight=10, match_type="exact", required=True),
        SpecRule("Number of Cells", weight=9, match_type="exact"),
        SpecRule("Current - Charging", weight=8, match_type="meets_or_exceeds"),
        SpecRule("Voltage - Supply", weight=7, match_type="range_covers"),
        SpecRule("Interface", weight=5, match_type="contains"),
        SpecRule("Function", weight=6, match_type="contains"),
    ]),

    "usb_ic": CategoryRules("usb_ic", rules=[
        SpecRule("Protocol", weight=10, match_type="contains", required=True, aliases=["USB Standard"]),
        SpecRule("Voltage - Supply", weight=7, match_type="range_covers", aliases=["VBUS Voltage"]),
        SpecRule("Data Rate", weight=9, match_type="meets_or_exceeds", aliases=["Speed"]),
        SpecRule("Number of Ports", weight=7, match_type="exact"),
        SpecRule("Current - Output", weight=6, match_type="meets_or_exceeds"),
        SpecRule("Features", weight=5, match_type="contains"),
        SpecRule("ESD Rating", weight=4, match_type="meets_or_exceeds"),
        SpecRule("Clock Frequency", weight=4, match_type="numeric_close", tolerance_pct=10, aliases=["Reference Frequency"]),
        SpecRule("Power Delivery", weight=5, match_type="contains", aliases=["PD Profile", "USB PD"]),
    ]),

    "video_interface": CategoryRules("video_interface", rules=[
        SpecRule("Protocol", weight=10, match_type="contains", required=True),
        SpecRule("Data Rate", weight=8, match_type="meets_or_exceeds"),
        SpecRule("Number of Channels", weight=7, match_type="exact"),
        SpecRule("Voltage - Supply", weight=6, match_type="range_covers"),
        SpecRule("Resolution", weight=5, match_type="contains"),
    ]),

    "serial_interface": CategoryRules("serial_interface", rules=[
        SpecRule("Protocol", weight=10, match_type="contains", required=True),
        SpecRule("Data Rate", weight=7, match_type="meets_or_exceeds"),
        SpecRule("Number of Channels", weight=6, match_type="exact"),
        SpecRule("Voltage - Supply", weight=6, match_type="range_covers"),
    ]),

    "display_driver": CategoryRules("display_driver", rules=[
        SpecRule("Topology", weight=8, match_type="exact"),
        SpecRule("Current - Output", weight=9, match_type="meets_or_exceeds"),
        SpecRule("Voltage - Input", weight=7, match_type="range_covers"),
        SpecRule("Number of Outputs", weight=7, match_type="exact"),
        SpecRule("Dimming", weight=5, match_type="contains"),
        SpecRule("Output Configuration", weight=5, match_type="exact"),
    ]),

    "tcon_video": CategoryRules("tcon_video", rules=[
        SpecRule("Type", weight=8, match_type="contains"),
        SpecRule("Interface", weight=7, match_type="contains"),
        SpecRule("Resolution", weight=6, match_type="contains"),
        SpecRule("Voltage - Supply", weight=5, match_type="range_covers"),
    ]),

    "flash_memory": CategoryRules("flash_memory", rules=[
        SpecRule("Memory Size", weight=10, match_type="exact", required=True),
        SpecRule("Memory Interface", weight=9, match_type="exact", required=True, aliases=["Memory Type", "Interface"]),
        SpecRule("Voltage - Supply", weight=8, match_type="range_covers"),
        SpecRule("Clock Frequency", weight=6, match_type="meets_or_exceeds", aliases=["Speed"]),
        SpecRule("Write Endurance", weight=5, match_type="meets_or_exceeds"),
        SpecRule("Data Retention", weight=4, match_type="meets_or_exceeds"),
        SpecRule("Standby Current", weight=3, match_type="numeric_close", tolerance_pct=50),
    ]),

    "eeprom": CategoryRules("eeprom", rules=[
        SpecRule("Memory Size", weight=10, match_type="exact", required=True),
        SpecRule("Memory Interface", weight=9, match_type="exact", required=True, aliases=["Interface"]),
        SpecRule("Voltage - Supply", weight=8, match_type="range_covers"),
        SpecRule("Clock Frequency", weight=5, match_type="meets_or_exceeds"),
        SpecRule("Write Cycle Time", weight=4, match_type="numeric_close", tolerance_pct=50),
        SpecRule("Write Endurance", weight=5, match_type="meets_or_exceeds"),
    ]),

    "fram_mram_sram": CategoryRules("fram_mram_sram", rules=[
        SpecRule("Memory Size", weight=10, match_type="exact", required=True),
        SpecRule("Memory Type", weight=9, match_type="exact", required=True),
        SpecRule("Memory Interface", weight=8, match_type="exact", required=True),
        SpecRule("Voltage - Supply", weight=7, match_type="range_covers"),
    ]),

    "audio_ic": CategoryRules("audio_ic", rules=[
        SpecRule("Voltage - Supply", weight=8, match_type="range_covers", required=True, aliases=["VDD"]),
        SpecRule("Current - Supply", weight=5, match_type="numeric_close", tolerance_pct=30),
        SpecRule("Output Power", weight=7, match_type="meets_or_exceeds"),
        SpecRule("THD + Noise", weight=7, match_type="numeric_close", tolerance_pct=50, aliases=["THD+N"]),
        SpecRule("Number of Channels", weight=8, match_type="exact"),
        SpecRule("Type", weight=8, match_type="contains"),
        SpecRule("S/N Ratio", weight=5, match_type="meets_or_exceeds", aliases=["SNR"]),
        SpecRule("Sample Rate", weight=5, match_type="meets_or_exceeds", aliases=["Bandwidth"]),
        SpecRule("Interface", weight=5, match_type="contains"),
        SpecRule("PSRR", weight=4, match_type="meets_or_exceeds"),
        SpecRule("Power Down Current", weight=3, match_type="numeric_close", tolerance_pct=50, aliases=["Shutdown Current"]),
    ]),

    "ambient_light": CategoryRules("ambient_light", rules=[
        SpecRule("Sensor Type", weight=8, match_type="contains"),
        SpecRule("Voltage - Supply", weight=7, match_type="range_covers"),
        SpecRule("Sensing Range", weight=6, match_type="contains"),
        SpecRule("Interface", weight=7, match_type="exact", aliases=["Output Type"]),
        SpecRule("Resolution", weight=5, match_type="meets_or_exceeds"),
        SpecRule("PSRR", weight=3, match_type="meets_or_exceeds"),
    ]),

    "temp_sensor": CategoryRules("temp_sensor", rules=[
        SpecRule("Sensor Type", weight=7, match_type="contains"),
        SpecRule("Voltage - Supply", weight=7, match_type="range_covers"),
        SpecRule("Sensing Range", weight=6, match_type="range_covers"),
        SpecRule("Accuracy", weight=8, match_type="numeric_close", tolerance_pct=30),
        SpecRule("Resolution", weight=6, match_type="meets_or_exceeds"),
        SpecRule("Interface", weight=7, match_type="exact"),
    ]),

    "hall_sensor": CategoryRules("hall_sensor", rules=[
        SpecRule("Sensor Type", weight=8, match_type="contains"),
        SpecRule("Voltage - Supply", weight=7, match_type="range_covers"),
        SpecRule("Output Type", weight=7, match_type="exact"),
        SpecRule("Sensitivity", weight=6, match_type="numeric_close", tolerance_pct=20),
    ]),

    "protection_ic": CategoryRules("protection_ic", rules=[
        SpecRule("Voltage - Clamping", weight=9, match_type="numeric_close", tolerance_pct=10, aliases=["Clamping Voltage"]),
        SpecRule("Voltage - Breakdown", weight=9, match_type="numeric_close", tolerance_pct=10),
        SpecRule("Voltage - Reverse Standoff", weight=8, match_type="meets_or_exceeds", aliases=["VRWM"]),
        SpecRule("Current - Peak Pulse", weight=7, match_type="meets_or_exceeds", aliases=["IPP"]),
        SpecRule("Power - Peak Pulse", weight=6, match_type="meets_or_exceeds"),
        SpecRule("Type", weight=7, match_type="contains"),
        SpecRule("Number of Circuits", weight=6, match_type="exact"),
        SpecRule("Response Time", weight=4, match_type="numeric_close", tolerance_pct=30),
    ]),

    "clock_timing": CategoryRules("clock_timing", rules=[
        SpecRule("Frequency", weight=9, match_type="numeric_close", tolerance_pct=5, aliases=["Output Frequency"]),
        SpecRule("Type", weight=7, match_type="contains"),
        SpecRule("Voltage - Supply", weight=7, match_type="range_covers"),
        SpecRule("Number of Outputs", weight=6, match_type="exact"),
        SpecRule("Output Type", weight=6, match_type="exact"),
        SpecRule("Jitter RMS", weight=6, match_type="numeric_close", tolerance_pct=30, aliases=["Jitter"]),
        SpecRule("Spread Spectrum", weight=4, match_type="contains"),
    ]),

    "logic_mux": CategoryRules("logic_mux", rules=[
        SpecRule("Voltage - Supply", weight=8, match_type="range_covers"),
        SpecRule("Logic Type", weight=8, match_type="contains"),
        SpecRule("Number of Circuits", weight=7, match_type="exact"),
        SpecRule("On-State Resistance (Max)", weight=6, match_type="numeric_close", tolerance_pct=30, aliases=["On-Resistance", "RON"]),
        SpecRule("Propagation Delay", weight=5, match_type="numeric_close", tolerance_pct=30),
        SpecRule("Bandwidth", weight=5, match_type="meets_or_exceeds"),
        SpecRule("Crosstalk", weight=4, match_type="numeric_close", tolerance_pct=30),
    ]),

    "mcu_soc": CategoryRules("mcu_soc", rules=[
        SpecRule("Core Processor", weight=9, match_type="contains", required=True),
        SpecRule("Speed", weight=7, match_type="meets_or_exceeds", aliases=["Clock Frequency"]),
        SpecRule("Program Memory Size", weight=8, match_type="meets_or_exceeds", aliases=["Flash Size"]),
        SpecRule("RAM Size", weight=7, match_type="meets_or_exceeds"),
        SpecRule("Number of I/O", weight=6, match_type="meets_or_exceeds"),
        SpecRule("Voltage - Supply", weight=6, match_type="range_covers"),
        SpecRule("Connectivity", weight=5, match_type="contains"),
        SpecRule("Peripherals", weight=4, match_type="contains"),
        SpecRule("Sleep Current", weight=3, match_type="numeric_close", tolerance_pct=50, aliases=["Standby Current"]),
    ]),

    "retimer_ic": CategoryRules("retimer_ic", rules=[
        SpecRule("Protocol", weight=10, match_type="contains", required=True),
        SpecRule("Data Rate", weight=9, match_type="meets_or_exceeds", aliases=["Speed"]),
        SpecRule("Voltage - Supply", weight=6, match_type="range_covers"),
        SpecRule("Number of Channels", weight=7, match_type="exact"),
        SpecRule("Type", weight=5, match_type="contains"),
        SpecRule("Output Jitter", weight=6, match_type="numeric_close", tolerance_pct=30, aliases=["Jitter"]),
        SpecRule("Return Loss", weight=4, match_type="numeric_close", tolerance_pct=30),
    ]),

    "opto_ic": CategoryRules("opto_ic", rules=[
        SpecRule("Output Type", weight=8, match_type="exact"),
        SpecRule("Number of Channels", weight=7, match_type="exact"),
        SpecRule("Voltage - Isolation", weight=8, match_type="meets_or_exceeds"),
        SpecRule("Current Transfer Ratio (CTR)", weight=6, match_type="numeric_close", tolerance_pct=30),
        SpecRule("Turn On / Turn Off Time", weight=4, match_type="numeric_close", tolerance_pct=30),
        SpecRule("Voltage - Forward (Vf)", weight=5, match_type="numeric_close", tolerance_pct=15),
    ]),
}


def get_rules(category_slug):
    return RULES.get(category_slug, DEFAULT_RULES)