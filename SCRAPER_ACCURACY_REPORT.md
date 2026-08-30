# Scraper and Datasheet Pipeline Status

## Purpose

This document records verified behaviour and known limitations. It does not
claim end-to-end accuracy rates because the project does not yet have a
labelled benchmark set or automated evaluation.

## Verified local state

The database status command currently reports:

| Metric | Observed value |
|---|---:|
| Components | 33,988 |
| Components with datasheet URL | 24,966 |
| Components with package information | 32,247 |
| Real specification rows | 278,141 |
| Components marked LLM-enriched | 1 |
| Pending datasheet-queue entries | 94 |

These counts describe data coverage, not correctness. A datasheet URL, parsed
text, or stored spec is not proof that the value is correct for the part.

## Pipeline behaviour

1. The DigiKey Playwright plugin collects catalogue rows and available
   parametric fields.
2. Datasheet download code checks for a PDF signature and rejects obvious
   non-datasheet documents when text can be extracted.
3. PyMuPDF extracts selectable PDF text. Image-only or encrypted PDFs may not
   yield usable text because OCR is not included.
4. `LLMDatasheetParser` sends selected text to NVIDIA NIM using
   `meta/llama-3.1-8b-instruct`, validates recognised match-rule fields, and
   uses the deterministic parser to fill missing fields.

## Validation safeguards

- Only fields recognised by the category's `match_rules` are accepted from the
  LLM.
- Numeric values are converted into the unit used by the relevant sanity
  bounds before range checking. For example, `160 mV` is validated as 160 mV
  for `Dropout Voltage (Max)`.
- Values outside configured bounds, such as `999 dB` PSRR, are rejected.
- A valid unit conversion is not a guarantee of correctness; values still need
  comparison with the source datasheet for measured accuracy.

## Known limitations

- No OCR for scanned datasheets.
- No benchmark dataset, ground-truth comparison, or automated accuracy metric.
- LLM extraction requires a configured `NVIDIA_API_KEY` and network access.
- DigiKey page structure may change and requires periodic scraper regression
  checks.
- A matching score indicates rule-based electrical similarity; it is not a
  certification of pin compatibility, qualification, or availability.

## Recommended next steps

1. Create a labelled set of parts with manually verified spec values.
2. Add tests for unit conversion, canonical spec-name mapping, and parsing of
   representative PDFs.
3. Record per-part source and confidence for LLM and regex-extracted values.
4. Add OCR only after measuring how many queued documents are image-only.
