"""
Deterministic checks on an extracted Invoice.

The model tells us how sure it is. This file doesn't care about feelings - it
does arithmetic. The two together are what makes flagging trustworthy:

  - Model confidence catches things Python cannot see (blurred text, ambiguous
    layout, "is that a 3 or an 8").
  - Python catches things the model is unreliable at (does this actually add
    up, is this date real, is a required field missing).

Neither alone is enough. A model may spot a bad subtotal nine times in ten;
Decimal arithmetic spots it ten times in ten, every time, for nothing.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from schema import Invoice

# Below this, we want a human to look regardless of what the arithmetic says.
CONFIDENCE_THRESHOLD = 0.85

# Money tolerance. Real invoices round; we allow a piastre either way.
TOLERANCE = Decimal("0.02")

REQUIRED = ("supplier_name", "invoice_number", "invoice_date", "total")

DATE_FORMATS = ("%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d", "%d-%m-%Y",
                "%d.%m.%Y", "%d %b %Y", "%d %B %Y")


@dataclass
class Flag:
    """One reason a human should look at this document."""

    severity: str  # "block" sends it to review; "warn" is noted but passes
    field: str
    message: str


def money(raw: str) -> Decimal | None:
    """Parse a money string to Decimal, or None if it isn't a number.

    We use Decimal, never float. 0.1 + 0.2 != 0.3 in binary floating point,
    and an accountant will find the one cent you lost.
    """
    if not raw or not raw.strip():
        return None
    cleaned = "".join(c for c in raw if c.isdigit() or c in ".-")
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def parse_date(raw: str) -> date | None:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def validate(inv: Invoice, today: date | None = None) -> list[Flag]:
    """Run every check. Returns the reasons this document needs a human."""
    today = today or date.today()
    flags: list[Flag] = []

    # 1. Required fields are actually present.
    for name in REQUIRED:
        if not getattr(inv, name).value.strip():
            flags.append(Flag("block", name, "Required field is empty"))

    # 2. Anything the model itself was unsure about.
    for name in ("supplier_name", "invoice_number", "invoice_date",
                 "currency", "subtotal", "tax", "total"):
        field = getattr(inv, name)
        if field.confidence < CONFIDENCE_THRESHOLD:
            flags.append(Flag(
                "block", name,
                f"Low confidence ({field.confidence:.2f}) - model read "
                f"{field.evidence[:60]!r}"
            ))

    # 3. Do the line items add up to the stated subtotal?
    subtotal = money(inv.subtotal.value)
    if inv.line_items and subtotal is not None:
        line_sum = Decimal("0")
        unparseable = []
        for item in inv.line_items:
            amount = money(item.amount)
            if amount is None:
                unparseable.append(item.description[:30])
            else:
                line_sum += amount
        if unparseable:
            flags.append(Flag("warn", "line_items",
                              f"Could not read amount for: {', '.join(unparseable)}"))
        elif abs(line_sum - subtotal) > TOLERANCE:
            flags.append(Flag(
                "block", "subtotal",
                f"Line items sum to {line_sum} but subtotal reads {subtotal} "
                f"(difference {line_sum - subtotal})"
            ))

    # 4. Does subtotal + tax equal the total?
    tax, total = money(inv.tax.value), money(inv.total.value)
    if subtotal is not None and total is not None:
        if tax is None:
            flags.append(Flag("block", "tax",
                              "Tax is missing, so the total cannot be checked"))
        elif abs(subtotal + tax - total) > TOLERANCE:
            flags.append(Flag(
                "block", "total",
                f"{subtotal} + {tax} = {subtotal + tax}, but total reads {total}"
            ))

    # 5. Is the date real, and plausible?
    raw_date = inv.invoice_date.value.strip()
    if raw_date:
        parsed = parse_date(raw_date)
        if parsed is None:
            flags.append(Flag("block", "invoice_date",
                              f"Could not parse {raw_date!r} as a date"))
        elif parsed > today:
            flags.append(Flag("warn", "invoice_date",
                              f"Date {parsed} is in the future"))
        elif parsed.year < 2000:
            flags.append(Flag("warn", "invoice_date",
                              f"Date {parsed} looks implausibly old"))

    # 6. The model raised something in prose.
    if inv.document_notes.strip():
        flags.append(Flag("warn", "document_notes", inv.document_notes.strip()))

    return flags


def needs_review(flags: list[Flag]) -> bool:
    return any(f.severity == "block" for f in flags)
