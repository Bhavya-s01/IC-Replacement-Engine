"""config.py - Categories and settings for monitor IC scraping."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import os

DB_PATH = os.environ.get("IC_DB_PATH", "ic_database.db")

REQUEST_DELAY_SECONDS = 1.0
PAGE_LOAD_TIMEOUT_MS  = 60_000
MAX_RETRIES           = 3
RESULTS_PER_PAGE      = 100
HEADLESS_MODE         = True
EDGE_CHANNEL          = "msedge"
DOWNLOAD_DIR          = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")

DIGIKEY_BASE       = "https://www.digikey.com"
DIGIKEY_IC_LANDING = DIGIKEY_BASE + "/en/products/category/integrated-circuits-ics/32"


@dataclass
class ICCategory:
    name: str
    slug: str
    digikey_subcategory_slugs: List[str]
    search_keywords: List[str]
    key_specifications: List[str]
    description: str = ""


CATEGORIES: Dict[str, ICCategory] = {

    # ── 1. POWER MANAGEMENT ICs ──
    "dcdc_converter": ICCategory(
        name="DC-DC Converter",
        slug="dcdc_converter",
        digikey_subcategory_slugs=["pmic-voltage-regulators-dc-dc-switching-regulators",
                                   "pmic-voltage-regulators-dc-dc-switching-controllers",
                                   "pmic-voltage-regulators-dc-dc-converters"],
        search_keywords=["DC DC converter", "buck converter", "boost converter", "buck-boost"],
        key_specifications=["Topology", "Voltage - Input (Min)", "Voltage - Input (Max)",
                           "Voltage - Output (Min/Fixed)", "Voltage - Output (Max)",
                           "Current - Output", "Switching Frequency", "Efficiency"],
        description="DC-DC buck, boost, buck-boost switching regulators and controllers",
    ),

    "ldo_ic": ICCategory(
        name="LDO Regulator",
        slug="ldo_ic",
        digikey_subcategory_slugs=["pmic-voltage-regulators-linear"],
        search_keywords=["LDO regulator", "linear voltage regulator", "low dropout"],
        key_specifications=["Output Configuration", "Output Type", "Number of Regulators",
                           "Voltage - Input (Max)", "Voltage - Output (Min/Fixed)",
                           "Voltage Dropout (Max)", "Current - Output", "Current - Quiescent (Iq)", "PSRR"],
        description="Linear low-dropout voltage regulators",
    ),

    "gate_driver": ICCategory(
        name="Gate Driver",
        slug="gate_driver",
        digikey_subcategory_slugs=["pmic-gate-drivers"],
        search_keywords=["gate driver IC", "MOSFET driver", "half bridge driver"],
        key_specifications=["Configuration", "Gate Type", "Number of Drivers",
                           "Voltage - Supply", "Current - Peak Output",
                           "Rise / Fall Time", "Input Type"],
        description="Power MOSFET and IGBT gate driver ICs",
    ),

    "power_sequencer": ICCategory(
        name="Power Sequencer",
        slug="power_sequencer",
        digikey_subcategory_slugs=["pmic-supervisors", "pmic-power-management-specialized"],
        search_keywords=["power sequencer IC", "voltage supervisor", "power management"],
        key_specifications=["Number of Voltages Monitored", "Output Type", "Reset",
                           "Voltage - Threshold", "Voltage - Supply"],
        description="Power sequencing ICs and voltage supervisors",
    ),

    "battery_management": ICCategory(
        name="Battery Management",
        slug="battery_management",
        digikey_subcategory_slugs=["pmic-battery-management"],
        search_keywords=["battery charger IC", "battery management IC", "BMS IC"],
        key_specifications=["Battery Chemistry", "Function", "Number of Cells",
                           "Current - Charging", "Voltage - Supply",
                           "Interface", "Operating Temperature"],
        description="Battery charger and management ICs",
    ),

    # ── 2. INTERFACE ICs ──
    "usb_ic": ICCategory(
        name="USB IC",
        slug="usb_ic",
        digikey_subcategory_slugs=["interface-controllers", "interface-specialized"],
        search_keywords=["USB Type-C controller", "USB PD controller", "USB PHY",
                         "USB 3.0 hub IC", "USB mux"],
        key_specifications=["Protocol", "USB Standard", "Data Rate",
                           "Number of Ports", "Features", "Voltage - Supply"],
        description="USB Type-C, PD controllers, USB PHYs, hubs",
    ),

    "video_interface": ICCategory(
        name="Video Interface",
        slug="video_interface",
        digikey_subcategory_slugs=["interface-specialized", "interface-controllers"],
        search_keywords=["HDMI transceiver", "DisplayPort transceiver", "LVDS driver",
                         "eDP driver", "MIPI DSI bridge", "DVI transceiver"],
        key_specifications=["Protocol", "Data Rate", "Number of Channels",
                           "Resolution", "Interface", "Voltage - Supply"],
        description="HDMI, DisplayPort, LVDS, eDP, MIPI-DSI transceivers and bridges",
    ),

    "serial_interface": ICCategory(
        name="Serial Interface",
        slug="serial_interface",
        digikey_subcategory_slugs=["interface-uart", "interface-i2c", "interface-spi"],
        search_keywords=["UART controller IC", "SPI controller IC", "I2C controller IC",
                         "I2C expander", "SPI bridge"],
        key_specifications=["Protocol", "Data Rate", "Number of Channels",
                           "Voltage - Supply", "Features"],
        description="UART, SPI, I2C controller and bridge ICs",
    ),

    # ── 3. VIDEO & DISPLAY CONTROLLERS ──
    "display_driver": ICCategory(
        name="Display Driver",
        slug="display_driver",
        digikey_subcategory_slugs=["pmic-led-drivers"],
        search_keywords=["LCD driver IC", "LED driver IC", "LED backlight driver",
                         "OLED driver IC", "backlight controller"],
        key_specifications=["Topology", "Output Configuration", "Voltage - Input",
                           "Current - Output", "Dimming", "Number of Outputs"],
        description="LCD/LED/OLED driver ICs, backlight controllers",
    ),

    "tcon_video": ICCategory(
        name="TCON / Video Processor",
        slug="tcon_video",
        digikey_subcategory_slugs=["video-ics"],
        search_keywords=["timing controller IC", "TCON IC", "video scaler IC",
                         "video processor IC", "display controller"],
        key_specifications=["Type", "Interface", "Resolution",
                           "Number of Inputs", "Number of Outputs", "Voltage - Supply"],
        description="Timing controllers, video processors, display controller ASICs",
    ),

    # ── 4. MEMORY ──
    "flash_memory": ICCategory(
        name="Flash Memory",
        slug="flash_memory",
        digikey_subcategory_slugs=["memory"],
        search_keywords=["NOR flash IC", "serial flash IC", "SPI flash",
                         "parallel NOR flash"],
        key_specifications=["Memory Size", "Memory Type", "Memory Interface",
                           "Clock Frequency", "Write Endurance", "Data Retention",
                           "Voltage - Supply", "Operating Temperature"],
        description="Serial NOR Flash, Parallel NOR Flash",
    ),

    "eeprom": ICCategory(
        name="EEPROM",
        slug="eeprom",
        digikey_subcategory_slugs=["memory"],
        search_keywords=["EEPROM IC", "serial EEPROM", "I2C EEPROM", "SPI EEPROM"],
        key_specifications=["Memory Size", "Memory Interface", "Clock Frequency",
                           "Write Cycle Time", "Write Endurance",
                           "Voltage - Supply", "Operating Temperature"],
        description="EEPROM memory ICs",
    ),

    "fram_mram_sram": ICCategory(
        name="FRAM / MRAM / SRAM",
        slug="fram_mram_sram",
        digikey_subcategory_slugs=["memory"],
        search_keywords=["FRAM IC", "MRAM IC", "serial SRAM", "SRAM IC",
                         "ferroelectric RAM", "magnetoresistive RAM"],
        key_specifications=["Memory Size", "Memory Type", "Memory Interface",
                           "Clock Frequency", "Write Endurance",
                           "Voltage - Supply", "Operating Temperature"],
        description="FRAM, MRAM, Serial SRAM",
    ),

    # ── 5. AUDIO CODECS & AMPLIFIERS ──
    "audio_ic": ICCategory(
        name="Audio IC",
        slug="audio_ic",
        digikey_subcategory_slugs=["audio-special-purpose", "audio-amplifiers"],
        search_keywords=["audio codec IC", "audio DAC", "audio amplifier IC",
                         "class D amplifier", "audio DSP"],
        key_specifications=["Type", "Output Type", "Output Power", "S/N Ratio",
                           "THD + Noise", "Sample Rate", "Resolution (Bits)",
                           "Number of Channels", "Voltage - Supply"],
        description="Audio DACs, codecs, amplifiers, Class-D drivers, audio DSPs",
    ),

    # ── 6. SENSORS ──
    "ambient_light": ICCategory(
        name="Ambient Light Sensor",
        slug="ambient_light",
        digikey_subcategory_slugs=["ambient-light-sensors", "proximity-sensors"],
        search_keywords=["ambient light sensor IC", "ALS IC", "proximity sensor IC",
                         "light sensor"],
        key_specifications=["Sensor Type", "Sensing Range", "Interface",
                           "Voltage - Supply", "Operating Temperature"],
        description="Ambient light sensors and proximity sensors",
    ),

    "temp_sensor": ICCategory(
        name="Temperature Sensor",
        slug="temp_sensor",
        digikey_subcategory_slugs=["temperature-sensors-analog-and-digital-output"],
        search_keywords=["temperature sensor IC", "digital temperature sensor",
                         "thermal sensor IC"],
        key_specifications=["Sensor Type", "Sensing Range", "Accuracy",
                           "Resolution", "Interface", "Voltage - Supply"],
        description="Temperature sensor ICs",
    ),

    "hall_sensor": ICCategory(
        name="Hall Effect Sensor",
        slug="hall_sensor",
        digikey_subcategory_slugs=["magnetic-sensors-hall-effect-switches",
                                   "magnetic-sensors-linear-compasses"],
        search_keywords=["hall effect sensor", "hall switch IC", "magnetic sensor IC"],
        key_specifications=["Sensor Type", "Output Type", "Sensitivity",
                           "Operating Point", "Voltage - Supply"],
        description="Hall-effect switches and linear magnetic sensors",
    ),

    # ── 7. PROTECTION DEVICES ──
    "protection_ic": ICCategory(
        name="Protection IC",
        slug="protection_ic",
        digikey_subcategory_slugs=["esd-suppressors-tvs", "esd-protection-diodes",
                                   "pmic-current-regulation-management"],
        search_keywords=["TVS diode", "ESD protection IC", "overvoltage protection",
                         "current limiter IC", "eFuse IC"],
        key_specifications=["Type", "Voltage - Clamping", "Voltage - Breakdown",
                           "Voltage - Reverse Standoff", "Current - Peak Pulse",
                           "Number of Circuits", "Capacitance"],
        description="TVS/ESD diodes, overvoltage protectors, current limiters, eFuses",
    ),

    # ── 8. LOGIC & TIMING ──
    "clock_timing": ICCategory(
        name="Clock & Timing",
        slug="clock_timing",
        digikey_subcategory_slugs=["clock-timing-programmable-timers-oscillators",
                                   "clock-timing-clock-generators-plls-frequency-synthesizers"],
        search_keywords=["PLL IC", "clock generator IC", "oscillator IC",
                         "frequency synthesizer", "clock buffer"],
        key_specifications=["Type", "Frequency", "Number of Outputs",
                           "Output Type", "Voltage - Supply"],
        description="PLLs, clock generators, oscillators, frequency synthesizers",
    ),

    "logic_mux": ICCategory(
        name="Logic / MUX / Level Shifter",
        slug="logic_mux",
        digikey_subcategory_slugs=["logic-buffers-drivers-receivers-transceivers",
                                   "logic-signal-switches-multiplexers-decoders",
                                   "logic-translators-level-shifters"],
        search_keywords=["level shifter IC", "analog multiplexer", "bus switch IC",
                         "logic buffer", "signal switch"],
        key_specifications=["Logic Type", "Number of Circuits", "Voltage - Supply",
                           "Propagation Delay", "On-State Resistance"],
        description="Level shifters, multiplexers, buffers, analog switches",
    ),

    # ── 9. MCU / SoC ──
    "mcu_soc": ICCategory(
        name="MCU / SoC",
        slug="mcu_soc",
        digikey_subcategory_slugs=["embedded-microcontrollers"],
        search_keywords=["ARM Cortex-M microcontroller", "RISC-V MCU",
                         "embedded MCU", "microcontroller IC"],
        key_specifications=["Core Processor", "Core Size", "Speed",
                           "Program Memory Size", "RAM Size", "Number of I/O",
                           "Peripherals", "Connectivity", "Voltage - Supply"],
        description="Embedded microcontrollers (ARM Cortex-M, RISC-V) and SoCs",
    ),

    # ── 10. RETIMERS & RE-DRIVERS ──
    "retimer_ic": ICCategory(
        name="Retimer / Redriver",
        slug="retimer_ic",
        digikey_subcategory_slugs=["signal-buffers-repeaters-splitters"],
        search_keywords=["HDMI retimer", "DisplayPort retimer", "USB redriver",
                         "PCIe retimer", "signal repeater IC"],
        key_specifications=["Type", "Protocol", "Data Rate",
                           "Number of Channels", "Voltage - Supply"],
        description="HDMI/DP retimers, USB re-drivers, PCIe repeaters",
    ),

    # ── 11. OPTOELECTRONICS ──
    "opto_ic": ICCategory(
        name="Opto IC",
        slug="opto_ic",
        digikey_subcategory_slugs=["optoisolators-transistor-photovoltaic-output",
                                   "optoisolators-triac-scr-output",
                                   "optoisolators-logic-output"],
        search_keywords=["optocoupler", "optoisolator", "IR receiver",
                         "photo diode", "phototransistor"],
        key_specifications=["Output Type", "Number of Channels",
                           "Current Transfer Ratio (CTR)", "Voltage - Isolation",
                           "Turn On / Turn Off Time"],
        description="Optocouplers, IR receivers, photo-diodes",
    ),
}


def get_category(slug):
    return CATEGORIES.get(slug)

def all_category_slugs():
    return sorted(CATEGORIES.keys())
