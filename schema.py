"""
The shape of what we pull out of a document.

Two design decisions worth understanding, because they are the difference
between a demo and something a business will actually run on:

1. Every extracted value is a STRING, even amounts and dates.
   The model is good at reading. It is not the right place to do arithmetic
   or date parsing. We take the raw text it saw, then parse and check it
   ourselves in Python where the behaviour is deterministic and testable.

2. Every field carries `confidence` and `evidence` alongside the value.
   `evidence` is the exact snippet the model read it from. When a human
   reviews a flagged row, they see the value AND where it came from, so
   checking takes three seconds instead of reopening the PDF.
"""

from pydantic import BaseModel, Field as PydField


class Field(BaseModel):
    """One extracted value, with the model's own certainty and its source text."""

    value: str = PydField(
        description="The extracted value exactly as written in the document. "
                    "Empty string if the document does not contain it."
    )
    confidence: float = PydField(
        description="How certain you are, from 0.0 to 1.0. Be honest and "
                    "be harsh: use below 0.7 if the text is blurred, ambiguous, "
                    "cut off, or you had to infer it rather than read it."
    )
    evidence: str = PydField(
        description="The exact text from the document you read this value from. "
                    "Empty string if the field was not found."
    )


class LineItem(BaseModel):
    """A single row from the invoice's item table."""

    description: str
    quantity: str
    unit_price: str
    amount: str


class Invoice(BaseModel):
    """Everything we want from one invoice or receipt."""

    supplier_name: Field
    invoice_number: Field
    invoice_date: Field
    currency: Field
    subtotal: Field
    tax: Field
    total: Field

    line_items: list[LineItem]

    document_notes: str = PydField(
        description="Anything a human reviewer should know: the scan is skewed, "
                    "a corner is cut off, there are two totals, the document is "
                    "handwritten, it is not an invoice at all. Empty string if clean."
    )
