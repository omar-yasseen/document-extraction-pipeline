"""
Generates a deliberately messy invoice image so you always have something to
smoke-test with. It is skewed, noisy, slightly blurred, and contains three
traps on purpose:

  1. The tax line is smudged out    -> should come back low-confidence or empty
  2. The line items do NOT sum to the subtotal -> our validator must catch it
  3. Two different totals appear    -> the model should flag it in notes

A clean synthetic invoice proves nothing. This one exercises the parts that
matter. A phone photo of a real receipt is still a better test - use both.

    python make_test_doc.py
"""

import random
from PIL import Image, ImageDraw, ImageFilter, ImageFont

random.seed(7)
W, H = 1240, 1754  # A4 at 150 dpi


def font(size: int, bold: bool = False):
    for name in (("arialbd.ttf", "calibrib.ttf") if bold else ("arial.ttf", "calibri.ttf")):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


img = Image.new("RGB", (W, H), (252, 251, 247))
d = ImageDraw.Draw(img)

d.text((70, 70), "NILE OFFICE SUPPLIES", font=font(38, True), fill=(20, 20, 20))
d.text((70, 118), "14 Sharia Ramses, Cairo 11511, Egypt", font=font(20), fill=(70, 70, 70))
d.text((70, 144), "Tax Reg. 402-889-137   |   +20 2 2574 8890", font=font(20), fill=(70, 70, 70))

d.text((860, 74), "INVOICE", font=font(34, True), fill=(20, 20, 20))
d.text((860, 122), "No.  INV-2026-0847", font=font(21), fill=(30, 30, 30))
d.text((860, 150), "Date  04/09/2026", font=font(21), fill=(30, 30, 30))
d.line([(70, 200), (1170, 200)], fill=(120, 120, 120), width=2)

d.text((70, 226), "BILL TO", font=font(17, True), fill=(110, 110, 110))
d.text((70, 252), "Delta Marketing LLC", font=font(23), fill=(20, 20, 20))
d.text((70, 282), "8 街 El-Thawra, Heliopolis, Cairo", font=font(20), fill=(60, 60, 60))

y = 360
d.rectangle([(70, y), (1170, y + 40)], fill=(232, 232, 228))
for label, x in (("DESCRIPTION", 84), ("QTY", 700), ("UNIT", 830), ("AMOUNT", 1010)):
    d.text((x, y + 11), label, font=font(18, True), fill=(40, 40, 40))

rows = [
    ("A4 Copy Paper, 80gsm (box of 5 reams)", "12", "445.00", "5,340.00"),
    ("HP 305A Toner Cartridge, black", "3", "2,180.00", "6,540.00"),
    ("Stapler, heavy duty 100-sheet", "6", "310.00", "1,860.00"),
    ("Whiteboard markers, assorted (pk 12)", "20", "96.50", "1,930.00"),
    ("Delivery & handling", "1", "250.00", "250.00"),
]
y += 40
for i, (desc, qty, unit, amt) in enumerate(rows):
    if i % 2:
        d.rectangle([(70, y), (1170, y + 38)], fill=(246, 246, 243))
    d.text((84, y + 9), desc, font=font(20), fill=(25, 25, 25))
    d.text((700, y + 9), qty, font=font(20), fill=(25, 25, 25))
    d.text((830, y + 9), unit, font=font(20), fill=(25, 25, 25))
    d.text((1010, y + 9), amt, font=font(20), fill=(25, 25, 25))
    y += 38

y += 30
d.line([(700, y), (1170, y)], fill=(120, 120, 120), width=1)
y += 16

# Trap 2: the rows above total 15,920.00, but the printed subtotal says 15,290.00
d.text((760, y), "Subtotal", font=font(21), fill=(40, 40, 40))
d.text((1010, y), "15,290.00", font=font(21), fill=(25, 25, 25))
y += 34

# Trap 1: the tax figure is smudged
d.text((760, y), "VAT 14%", font=font(21), fill=(40, 40, 40))
d.text((1010, y), "2,140.60", font=font(21), fill=(25, 25, 25))
smudge = img.crop((1000, y - 4, 1170, y + 30)).filter(ImageFilter.GaussianBlur(4.2))
img.paste(smudge, (1000, y - 4))
d = ImageDraw.Draw(img)
y += 44

d.text((760, y), "TOTAL  EGP", font=font(25, True), fill=(20, 20, 20))
d.text((1000, y), "17,430.60", font=font(25, True), fill=(20, 20, 20))

# Trap 3: a second, contradictory total further down
d.text((70, y + 120), "Amount due on delivery:  EGP 17,340.60", font=font(20), fill=(90, 90, 90))
d.text((70, y + 160), "Payment terms: net 30 days. Late payment 2% monthly.",
       font=font(19), fill=(110, 110, 110))
d.text((70, H - 120), "Thank you for your business.", font=font(19), fill=(130, 130, 130))

# Make it look photographed rather than exported.
img = img.rotate(-1.4, expand=True, fillcolor=(252, 251, 247))
img = img.filter(ImageFilter.GaussianBlur(0.6))
px = img.load()
for _ in range(28000):
    x, yy = random.randrange(img.width), random.randrange(img.height)
    v = random.randint(-26, 26)
    r, g, b = px[x, yy]
    px[x, yy] = (max(0, min(255, r + v)), max(0, min(255, g + v)), max(0, min(255, b + v)))

shade = Image.linear_gradient("L").resize(img.size).rotate(28, fillcolor=128)
img = Image.composite(img, Image.new("RGB", img.size, (214, 212, 205)), shade.point(lambda p: 255 - p // 3))

out = "samples/messy-invoice.png"
img.save(out, quality=88)
print(f"wrote {out}  ({img.width}x{img.height})")
print("traps: smudged VAT | line items sum to 15,920.00 not 15,290.00 | two totals")
