# LLM Datasheet Parser

The parser uses NVIDIA NIM's OpenAI-compatible endpoint with the default model
`meta/llama-3.1-8b-instruct`. Configure `NVIDIA_API_KEY` in `.env`; the parser
does not use Groq or Gemini fallbacks.

## Extraction flow

1. Read selectable text from the datasheet PDF or supported HTML source.
2. Select the text sections most likely to contain electrical data.
3. Ask NVIDIA NIM for JSON containing only category-relevant specs and pins.
4. Map returned names to the canonical fields in `match_rules.py`.
5. Validate numeric values in their rule-specific units.
6. Fill missing recognised fields with the deterministic parser when possible.

## Validation examples

- `Dropout Voltage (Max): 160 mV` is accepted and checked as millivolts.
- `PSRR: 999 dB` is rejected as outside the configured range.
- Unknown spec names are not stored as LLM-extracted match fields.

## Limits

The project has no labelled benchmark set, so no extraction-accuracy percentage
is claimed. Scanned and encrypted PDFs need additional OCR or handling before
they can be reliably enriched.
