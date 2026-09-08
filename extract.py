"""
One document in, one structured Invoice out.

Run it directly to test a single file:
    python extract.py samples/some-invoice.pdf
"""

import base64
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from schema import Invoice

load_dotenv()

MODEL = "claude-opus-5"

# Input pricing, US dollars per million tokens, so we can show what a run costs.
PRICE_IN, PRICE_OUT = 5.00, 25.00

MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

# The system prompt is where most of the quality lives. Notice what it does:
# it tells the model to READ rather than INFER, and it makes low confidence
# an acceptable answer. A model that is rewarded for always being sure will
# always be sure, and then the confidence score is worthless to you.
SYSTEM = """You extract structured data from invoices and receipts.

Rules:
- Transcribe exactly what is printed. Never reformat, round, or tidy a value.
- Never infer a value that is not visible. If it is missing, return an empty
  string with confidence 0.0 rather than a plausible guess.
- Report confidence honestly. Blurred text, ambiguous layouts, cut-off edges
  and handwriting all mean confidence below 0.7. A low score is useful to us;
  a wrong value presented confidently is expensive.
- Keep the document's own currency symbols and decimal separators in `evidence`,
  but put a plain number in `value` (e.g. "1234.56", not "EGP 1,234.56").
- If the file is not an invoice or receipt at all, say so in document_notes."""


def load_document_block(path: Path) -> dict:
    """Turn a local file into the content block the API expects.

    PDFs go in as a `document` block; images as an `image` block. Getting this
    wrong is the most common first error: the block type must match the file.
    """
    suffix = path.suffix.lower()
    if suffix not in MEDIA_TYPES:
        raise ValueError(
            f"{path.name}: unsupported file type '{suffix}'. "
            f"Supported: {', '.join(sorted(MEDIA_TYPES))}"
        )

    media_type = MEDIA_TYPES[suffix]
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    block_type = "document" if suffix == ".pdf" else "image"

    return {
        "type": block_type,
        "source": {"type": "base64", "media_type": media_type, "data": data},
    }


def build_client() -> anthropic.Anthropic:
    """Create the API client.

    Anthropic API keys come in two flavours. A key created inside a workspace
    carries that workspace with it and just works. An org-level key does not,
    and every request has to name the workspace in a header - otherwise the API
    returns 400 "not scoped to a workspace". We support both: set
    ANTHROPIC_WORKSPACE_ID in .env and we pass the header for you.
    """
    workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID", "").strip()
    if workspace_id:
        return anthropic.Anthropic(
            default_headers={"anthropic-workspace-id": workspace_id}
        )
    return anthropic.Anthropic()


def extract(path: Path, client: anthropic.Anthropic | None = None) -> tuple[Invoice, float]:
    """Extract one document. Returns the parsed Invoice and what the call cost."""
    client = client or build_client()

    response = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        messages=[
            {
                "role": "user",
                "content": [
                    load_document_block(path),
                    {
                        "type": "text",
                        "text": "Extract every field from this document. "
                                "Read carefully and rate your confidence honestly.",
                    },
                ],
            }
        ],
        output_format=Invoice,
    )

    usage = response.usage
    cost = (usage.input_tokens * PRICE_IN + usage.output_tokens * PRICE_OUT) / 1_000_000

    # parsed_output is a real, validated Invoice object - not a dict, not a
    # string you have to json.loads and pray over.
    return response.parsed_output, cost


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python extract.py <path-to-document>", file=sys.stderr)
        return 1

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set. Put it in a .env file next to this "
              "script:\n\n    ANTHROPIC_API_KEY=sk-ant-...\n", file=sys.stderr)
        return 1

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"No such file: {path}", file=sys.stderr)
        return 1

    print(f"Reading {path.name} ...\n")
    try:
        invoice, cost = extract(path)
    except anthropic.AuthenticationError:
        print("Your API key was rejected. Check ANTHROPIC_API_KEY in .env.",
              file=sys.stderr)
        return 1
    except anthropic.RateLimitError:
        print("Rate limited. Wait a moment and try again.", file=sys.stderr)
        return 1
    except anthropic.BadRequestError as err:
        if "workspace" in str(err).lower():
            print(
                "Your API key is an org-level key, so it needs a workspace ID.\n\n"
                "Either:\n"
                "  A) Create a workspace-scoped key at\n"
                "     https://console.anthropic.com/settings/keys\n"
                "     (choose a workspace when creating it), or\n"
                "  B) Add this line to your .env file:\n"
                "     ANTHROPIC_WORKSPACE_ID=wrkspc_...\n"
                "     Find it at https://console.anthropic.com/settings/workspaces",
                file=sys.stderr,
            )
        else:
            print(f"The API rejected the request: {err}", file=sys.stderr)
        return 1
    except anthropic.APIConnectionError:
        print("Could not reach the API. Check your internet connection.",
              file=sys.stderr)
        return 1

    for name in ("supplier_name", "invoice_number", "invoice_date",
                 "currency", "subtotal", "tax", "total"):
        field = getattr(invoice, name)
        marker = "  " if field.confidence >= 0.85 else "??"
        print(f"{marker} {name:<16} {field.value or '(empty)':<28} "
              f"conf {field.confidence:.2f}   from: {field.evidence[:40]!r}")

    print(f"\n   {len(invoice.line_items)} line item(s)")
    for item in invoice.line_items:
        print(f"     - {item.description[:40]:<42} {item.quantity:>6} x "
              f"{item.unit_price:>10} = {item.amount:>10}")

    if invoice.document_notes:
        print(f"\n   Notes: {invoice.document_notes}")

    print(f"\n   Cost: ${cost:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
