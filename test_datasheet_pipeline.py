"""Test suite for datasheet validation, download normalization, and queue integrity."""

import os
import tempfile
import unittest
import fitz

from finder_extras.llm_parser import _is_valid_datasheet, download_pdf


class TestDatasheetValidation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_pdf(self, filename, text):
        path = os.path.join(self.temp_dir.name, filename)
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), text)
        doc.save(path)
        doc.close()
        return path

    def test_valid_datasheet(self):
        text = (
            "LM1117 800mA Low-Dropout Linear Regulator\n"
            "Ordering Information: LM1117DTX-3.3, LM1117DTX-5.0\n"
            "Absolute Maximum Ratings:\n"
            "Input Voltage: 20V\n"
            "Operating Temperature: -40 to 125 C\n"
            "Electrical Characteristics:\n"
            "Dropout Voltage: 1.2V at 800mA\n"
            "Quiescent Current: 5mA\n"
            "Output Voltage: 3.3V\n"
            "Pin Configuration and Functions: Pin 1 ADJ/GND, Pin 2 VOUT, Pin 3 VIN\n"
            "Typical Application Circuit and Block Diagram\n"
        ) * 5  # Ensure sufficient text length >= 500
        path = self._create_pdf("lm1117.pdf", text)
        self.assertTrue(_is_valid_datasheet(path, "LM1117DTX-3.3"))

    def test_empty_text_pdf_rejected(self):
        path = self._create_pdf("empty.pdf", "")
        self.assertFalse(_is_valid_datasheet(path, "LM1117"))

    def test_short_text_pdf_rejected(self):
        path = self._create_pdf("short.pdf", "Short text only without enough info")
        self.assertFalse(_is_valid_datasheet(path, "LM1117"))

    def test_wrong_mpn_pdf_rejected(self):
        text = (
            "TLV62569 High Efficiency Synchronous Step-Down Converter\n"
            "Absolute Maximum Ratings: Input Voltage 6V\n"
            "Electrical Characteristics: Output Current 2A\n"
            "Pin Configuration: Pin 1 VIN, Pin 2 SW, Pin 3 GND\n"
            "Typical Application Circuit and Block Diagram\n"
        ) * 5
        path = self._create_pdf("tlv62569.pdf", text)
        # Calling with a completely different part number:
        self.assertFalse(_is_valid_datasheet(path, "AP2112K-3.3TRG1"))

    def test_compliance_only_pdf_rejected(self):
        text = (
            "Environmental Compliance Statement\n"
            "Material Declaration Certificate for LM1117\n"
            "RoHS Declaration and REACH Declaration\n"
            "Conflict Minerals Free\n"
            "This product complies with European Union Directive 2011/65/EU\n"
        ) * 10
        path = self._create_pdf("compliance.pdf", text)
        self.assertFalse(_is_valid_datasheet(path, "LM1117"))

    def test_non_pdf_file_rejected(self):
        path = os.path.join(self.temp_dir.name, "fake.pdf")
        with open(path, "w", encoding="utf-8") as f:
            f.write("<html><body>Not a PDF</body></html>")
        self.assertFalse(_is_valid_datasheet(path, "LM1117"))


class TestUrlNormalization(unittest.TestCase):
    def test_protocol_relative_url(self):
        path, ftype = download_pdf("//invalid-domain-xyz-1234.com/test.pdf", "TEST_PART")
        self.assertIsNone(path)
        self.assertIsNone(ftype)

    def test_malformed_digikey_url_handling(self):
        # Malformed prefix gets corrected before requesting
        path, ftype = download_pdf(
            "https://www.digikey.com//invalid-domain-xyz-1234.com/test.pdf", "TEST_PART"
        )
        self.assertIsNone(path)
        self.assertIsNone(ftype)


if __name__ == "__main__":
    unittest.main()

