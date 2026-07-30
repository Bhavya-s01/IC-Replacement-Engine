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
    lifecycle_weight: float = 0.0
    stock_weight: float = 0.0
    price_weight: float = 0.0


DEFAULT_RULES = CategoryRules(
    category_slug="default",
    rules=[SpecRule("Voltage - Supply", weight=8, match_type="range_covers", required=False,
                    aliases=["Voltage - Supply (V)", "Supply Voltage"])],
)

RULES: Dict[str, CategoryRules] = {

    "dcdc_converter": CategoryRules("dcdc_converter", rules=[
        SpecRule("Voltage - Input (Min)", weight=8, match_type="numeric_close", tolerance_pct=15, aliases=["Voltage - Input"], required=False),
        SpecRule("Voltage - Input (Max)", weight=8, match_type="meets_or_exceeds", required=False),
        SpecRule("Voltage - Output (Min/Fixed)", weight=10, match_type="numeric_close", tolerance_pct=5, required=True, aliases=["Voltage - Output", "Output Voltage"]),
        SpecRule("Voltage - Output (Max)", weight=7, match_type="meets_or_exceeds", required=True),
        SpecRule("Current - Output", weight=9, match_type="meets_or_exceeds", required=True, aliases=["Current - Output (Max)"]),
        SpecRule("Switching Frequency", weight=5, match_type="numeric_close", tolerance_pct=30, aliases=["Frequency - Switching"], required=False),
        SpecRule("Topology", weight=7, match_type="exact", required=False),
        SpecRule("Efficiency", weight=5, match_type="meets_or_exceeds", required=False),
        SpecRule("Number of Outputs", weight=6, match_type="exact", required=False),
        SpecRule("Output Configuration", weight=5, match_type="exact", required=False),
        SpecRule("Output Ripple", weight=4, match_type="numeric_close", tolerance_pct=30, aliases=["Voltage - Ripple", "Ripple"], required=False),
        SpecRule("Thermal Resistance JA", weight=3, match_type="numeric_close", tolerance_pct=30, required=False),
        SpecRule("Enable Threshold", weight=3, match_type="numeric_close", tolerance_pct=20, aliases=["Shutdown Voltage", "Enable Voltage"], required=False),
    ]),

    "ldo_ic": CategoryRules("ldo_ic", rules=[
        SpecRule("Voltage - Output (Min/Fixed)", weight=10, match_type="numeric_close", tolerance_pct=3, required=True, aliases=["Voltage - Output", "Output Voltage"]),
        SpecRule("Voltage - Input (Max)", weight=8, match_type="meets_or_exceeds", required=False),
        SpecRule("Voltage - Input (Min)", weight=7, match_type="numeric_close", tolerance_pct=15, required=False),
        SpecRule("Current - Output", weight=9, match_type="meets_or_exceeds", required=True, aliases=["Current - Output (Max)"]),
        SpecRule("Voltage Dropout (Max)", weight=7, match_type="numeric_close", tolerance_pct=30, aliases=["Dropout Voltage"], required=False),
        SpecRule("Current - Quiescent (Iq)", weight=5, match_type="numeric_close", tolerance_pct=50, aliases=["Quiescent Current"], required=False),
        SpecRule("Output Type", weight=6, match_type="exact", required=False),
        SpecRule("Output Configuration", weight=5, match_type="exact", required=False),
        SpecRule("Number of Regulators", weight=6, match_type="exact", required=False),
        SpecRule("PSRR", weight=4, match_type="meets_or_exceeds", aliases=["Power Supply Rejection Ratio"], required=False),
        SpecRule("Output Noise", weight=3, match_type="numeric_close", tolerance_pct=50, aliases=["Output Noise RMS"], required=False),
        SpecRule("Load Regulation", weight=3, match_type="numeric_close", tolerance_pct=30, required=False),
        SpecRule("Line Regulation", weight=3, match_type="numeric_close", tolerance_pct=30, required=False),
    ]),

    "gate_driver": CategoryRules("gate_driver", rules=[
        SpecRule("Voltage - Supply", weight=9, match_type="range_covers", required=False),
        SpecRule("Current - Peak Output", weight=8, match_type="meets_or_exceeds", aliases=["Current - Output"], required=True),
        SpecRule("Gate Type", weight=7, match_type="exact", required=False),
        SpecRule("Configuration", weight=7, match_type="exact", required=False),
        SpecRule("Number of Drivers", weight=6, match_type="exact", required=False),
        SpecRule("Input Type", weight=5, match_type="exact", required=False),
        SpecRule("Rise / Fall Time", weight=5, match_type="numeric_close", tolerance_pct=30, required=False),
        SpecRule("Propagation Delay", weight=4, match_type="numeric_close", tolerance_pct=30, required=False),
    ]),

    "power_sequencer": CategoryRules("power_sequencer", rules=[
        SpecRule("Voltage - Threshold", weight=9, match_type="numeric_close", tolerance_pct=5, required=False),
        SpecRule("Number of Voltages Monitored", weight=7, match_type="exact", required=False),
        SpecRule("Output Type", weight=6, match_type="exact", required=False),
        SpecRule("Voltage - Supply", weight=8, match_type="range_covers", required=False),
        SpecRule("Reset", weight=5, match_type="exact", required=False),
    ]),

    "battery_management": CategoryRules("battery_management", rules=[
        SpecRule("Battery Chemistry", weight=10, match_type="exact", required=False),
        SpecRule("Number of Cells", weight=9, match_type="exact", required=False),
        SpecRule("Current - Charging", weight=8, match_type="meets_or_exceeds", required=False),
        SpecRule("Voltage - Supply", weight=7, match_type="range_covers", required=False),
        SpecRule("Interface", weight=5, match_type="contains", required=False),
        SpecRule("Function", weight=6, match_type="contains", required=False),
    ]),

    "usb_ic": CategoryRules("usb_ic", rules=[
        SpecRule("Protocol", weight=10, match_type="contains", required=False, aliases=["USB Standard"]),
        SpecRule("Voltage - Supply", weight=7, match_type="range_covers", aliases=["VBUS Voltage"], required=False),
        SpecRule("Data Rate", weight=9, match_type="meets_or_exceeds", aliases=["Speed"], required=False),
        SpecRule("Number of Ports", weight=7, match_type="exact", required=False),
        SpecRule("Current - Output", weight=6, match_type="meets_or_exceeds", required=True),
        SpecRule("Features", weight=5, match_type="contains", required=False),
        SpecRule("ESD Rating", weight=4, match_type="meets_or_exceeds", required=False),
        SpecRule("Clock Frequency", weight=4, match_type="numeric_close", tolerance_pct=10, aliases=["Reference Frequency"], required=False),
        SpecRule("Power Delivery", weight=5, match_type="contains", aliases=["PD Profile", "USB PD"], required=False),
    ]),

    "video_interface": CategoryRules("video_interface", rules=[
        SpecRule("Protocol", weight=10, match_type="contains", required=False),
        SpecRule("Data Rate", weight=8, match_type="meets_or_exceeds", required=False),
        SpecRule("Number of Channels", weight=7, match_type="exact", required=False),
        SpecRule("Voltage - Supply", weight=6, match_type="range_covers", required=False),
        SpecRule("Resolution", weight=5, match_type="contains", required=False),
    ]),

    "serial_interface": CategoryRules("serial_interface", rules=[
        SpecRule("Protocol", weight=10, match_type="contains", required=False),
        SpecRule("Data Rate", weight=7, match_type="meets_or_exceeds", required=False),
        SpecRule("Number of Channels", weight=6, match_type="exact", required=False),
        SpecRule("Voltage - Supply", weight=6, match_type="range_covers", required=False),
    ]),

    "display_driver": CategoryRules("display_driver", rules=[
        SpecRule("Topology", weight=8, match_type="exact", required=False),
        SpecRule("Current - Output", weight=9, match_type="meets_or_exceeds", required=True),
        SpecRule("Voltage - Input", weight=7, match_type="range_covers", required=False),
        SpecRule("Number of Outputs", weight=7, match_type="exact", required=False),
        SpecRule("Dimming", weight=5, match_type="contains", required=False),
        SpecRule("Output Configuration", weight=5, match_type="exact", required=False),
    ]),

    "tcon_video": CategoryRules("tcon_video", rules=[
        SpecRule("Type", weight=8, match_type="contains", required=False),
        SpecRule("Interface", weight=7, match_type="contains", required=False),
        SpecRule("Resolution", weight=6, match_type="contains", required=False),
        SpecRule("Voltage - Supply", weight=5, match_type="range_covers", required=False),
    ]),

    "flash_memory": CategoryRules("flash_memory", rules=[
        SpecRule("Memory Size", weight=10, match_type="exact", required=False),
        SpecRule("Memory Interface", weight=9, match_type="exact", required=False, aliases=["Memory Type", "Interface"]),
        SpecRule("Voltage - Supply", weight=8, match_type="range_covers", required=False),
        SpecRule("Clock Frequency", weight=6, match_type="meets_or_exceeds", aliases=["Speed"], required=False),
        SpecRule("Write Endurance", weight=5, match_type="meets_or_exceeds", required=False),
        SpecRule("Data Retention", weight=4, match_type="meets_or_exceeds", required=False),
        SpecRule("Standby Current", weight=3, match_type="numeric_close", tolerance_pct=50, required=False),
    ]),

    "eeprom": CategoryRules("eeprom", rules=[
        SpecRule("Memory Size", weight=10, match_type="exact", required=False),
        SpecRule("Memory Interface", weight=9, match_type="exact", required=False, aliases=["Interface"]),
        SpecRule("Voltage - Supply", weight=8, match_type="range_covers", required=False),
        SpecRule("Clock Frequency", weight=5, match_type="meets_or_exceeds", required=False),
        SpecRule("Write Cycle Time", weight=4, match_type="numeric_close", tolerance_pct=50, required=False),
        SpecRule("Write Endurance", weight=5, match_type="meets_or_exceeds", required=False),
    ]),

    "fram_mram_sram": CategoryRules("fram_mram_sram", rules=[
        SpecRule("Memory Size", weight=10, match_type="exact", required=False),
        SpecRule("Memory Type", weight=9, match_type="exact", required=False),
        SpecRule("Memory Interface", weight=8, match_type="exact", required=False),
        SpecRule("Voltage - Supply", weight=7, match_type="range_covers", required=False),
    ]),

    "audio_ic": CategoryRules("audio_ic", rules=[
        SpecRule("Voltage - Supply", weight=8, match_type="range_covers", required=False, aliases=["VDD"]),
        SpecRule("Current - Supply", weight=5, match_type="numeric_close", tolerance_pct=30, required=False),
        SpecRule("Output Power", weight=7, match_type="meets_or_exceeds", required=False),
        SpecRule("THD + Noise", weight=7, match_type="numeric_close", tolerance_pct=50, aliases=["THD+N"], required=False),
        SpecRule("Number of Channels", weight=8, match_type="exact", required=False),
        SpecRule("Type", weight=8, match_type="contains", required=False),
        SpecRule("S/N Ratio", weight=5, match_type="meets_or_exceeds", aliases=["SNR"], required=False),
        SpecRule("Sample Rate", weight=5, match_type="meets_or_exceeds", aliases=["Bandwidth"], required=False),
        SpecRule("Interface", weight=5, match_type="contains", required=False),
        SpecRule("PSRR", weight=4, match_type="meets_or_exceeds", required=False),
        SpecRule("Power Down Current", weight=3, match_type="numeric_close", tolerance_pct=50, aliases=["Shutdown Current"], required=False),
    ]),

    "ambient_light": CategoryRules("ambient_light", rules=[
        SpecRule("Sensor Type", weight=8, match_type="contains", required=False),
        SpecRule("Voltage - Supply", weight=7, match_type="range_covers", required=False),
        SpecRule("Sensing Range", weight=6, match_type="contains", required=False),
        SpecRule("Interface", weight=7, match_type="exact", aliases=["Output Type"], required=False),
        SpecRule("Resolution", weight=5, match_type="meets_or_exceeds", required=False),
        SpecRule("PSRR", weight=3, match_type="meets_or_exceeds", required=False),
    ]),

    "temp_sensor": CategoryRules("temp_sensor", rules=[
        SpecRule("Sensor Type", weight=7, match_type="contains", required=False),
        SpecRule("Voltage - Supply", weight=7, match_type="range_covers", required=False),
        SpecRule("Sensing Range", weight=6, match_type="range_covers", required=False),
        SpecRule("Accuracy", weight=8, match_type="numeric_close", tolerance_pct=30, required=False),
        SpecRule("Resolution", weight=6, match_type="meets_or_exceeds", required=False),
        SpecRule("Interface", weight=7, match_type="exact", required=False),
    ]),

    "hall_sensor": CategoryRules("hall_sensor", rules=[
        SpecRule("Sensor Type", weight=8, match_type="contains", required=False),
        SpecRule("Voltage - Supply", weight=7, match_type="range_covers", required=False),
        SpecRule("Output Type", weight=7, match_type="exact", required=False),
        SpecRule("Sensitivity", weight=6, match_type="numeric_close", tolerance_pct=20, required=False),
    ]),

    "protection_ic": CategoryRules("protection_ic", rules=[
        SpecRule("Voltage - Clamping", weight=9, match_type="numeric_close", tolerance_pct=10, aliases=["Clamping Voltage"], required=False),
        SpecRule("Voltage - Breakdown", weight=9, match_type="numeric_close", tolerance_pct=10, required=False),
        SpecRule("Voltage - Reverse Standoff", weight=8, match_type="meets_or_exceeds", aliases=["VRWM"], required=False),
        SpecRule("Current - Peak Pulse", weight=7, match_type="meets_or_exceeds", aliases=["IPP"], required=False),
        SpecRule("Power - Peak Pulse", weight=6, match_type="meets_or_exceeds", required=False),
        SpecRule("Type", weight=7, match_type="contains", required=False),
        SpecRule("Number of Circuits", weight=6, match_type="exact", required=False),
        SpecRule("Response Time", weight=4, match_type="numeric_close", tolerance_pct=30, required=False),
    ]),

    "clock_timing": CategoryRules("clock_timing", rules=[
        SpecRule("Frequency", weight=9, match_type="numeric_close", tolerance_pct=5, aliases=["Output Frequency"], required=False),
        SpecRule("Type", weight=7, match_type="contains", required=False),
        SpecRule("Voltage - Supply", weight=7, match_type="range_covers", required=False),
        SpecRule("Number of Outputs", weight=6, match_type="exact", required=False),
        SpecRule("Output Type", weight=6, match_type="exact", required=False),
        SpecRule("Jitter RMS", weight=6, match_type="numeric_close", tolerance_pct=30, aliases=["Jitter"], required=False),
        SpecRule("Spread Spectrum", weight=4, match_type="contains", required=False),
    ]),

    "logic_mux": CategoryRules("logic_mux", rules=[
        SpecRule("Voltage - Supply", weight=8, match_type="range_covers", required=False),
        SpecRule("Logic Type", weight=8, match_type="contains", required=False),
        SpecRule("Number of Circuits", weight=7, match_type="exact", required=False),
        SpecRule("On-State Resistance (Max)", weight=6, match_type="numeric_close", tolerance_pct=30, aliases=["On-Resistance", "RON"], required=False),
        SpecRule("Propagation Delay", weight=5, match_type="numeric_close", tolerance_pct=30, required=False),
        SpecRule("Bandwidth", weight=5, match_type="meets_or_exceeds", required=False),
        SpecRule("Crosstalk", weight=4, match_type="numeric_close", tolerance_pct=30, required=False),
    ]),

    "mcu_soc": CategoryRules("mcu_soc", rules=[
        SpecRule("Core Processor", weight=9, match_type="contains", required=False),
        SpecRule("Speed", weight=7, match_type="meets_or_exceeds", aliases=["Clock Frequency"], required=False),
        SpecRule("Program Memory Size", weight=8, match_type="meets_or_exceeds", aliases=["Flash Size"], required=False),
        SpecRule("RAM Size", weight=7, match_type="meets_or_exceeds", required=False),
        SpecRule("Number of I/O", weight=6, match_type="meets_or_exceeds", required=False),
        SpecRule("Voltage - Supply", weight=6, match_type="range_covers", required=False),
        SpecRule("Connectivity", weight=5, match_type="contains", required=False),
        SpecRule("Peripherals", weight=4, match_type="contains", required=False),
        SpecRule("Sleep Current", weight=3, match_type="numeric_close", tolerance_pct=50, aliases=["Standby Current"], required=False),
    ]),

    "retimer_ic": CategoryRules("retimer_ic", rules=[
        SpecRule("Protocol", weight=10, match_type="contains", required=False),
        SpecRule("Data Rate", weight=9, match_type="meets_or_exceeds", aliases=["Speed"], required=False),
        SpecRule("Voltage - Supply", weight=6, match_type="range_covers", required=False),
        SpecRule("Number of Channels", weight=7, match_type="exact", required=False),
        SpecRule("Type", weight=5, match_type="contains", required=False),
        SpecRule("Output Jitter", weight=6, match_type="numeric_close", tolerance_pct=30, aliases=["Jitter"], required=False),
        SpecRule("Return Loss", weight=4, match_type="numeric_close", tolerance_pct=30, required=False),
    ]),

    "opto_ic": CategoryRules("opto_ic", rules=[
        SpecRule("Output Type", weight=8, match_type="exact", required=False),
        SpecRule("Number of Channels", weight=7, match_type="exact", required=False),
        SpecRule("Voltage - Isolation", weight=8, match_type="meets_or_exceeds", required=False),
        SpecRule("Current Transfer Ratio (CTR)", weight=6, match_type="numeric_close", tolerance_pct=30, required=False),
        SpecRule("Turn On / Turn Off Time", weight=4, match_type="numeric_close", tolerance_pct=30, required=False),
        SpecRule("Voltage - Forward (Vf)", weight=5, match_type="numeric_close", tolerance_pct=15, required=False),
    ]),
}


def get_rules(category_slug):
    return RULES.get(category_slug, DEFAULT_RULES)