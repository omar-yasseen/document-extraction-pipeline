"""
Generates a small batch of test invoices - most clean, some broken - so the
straight-through rate means something and the review queue has variety.

    python make_test_docs.py

A demo where every document fails is as useless as one where none do. You need
both paths visible, and you need the failures to fail for *different* reasons.
"""

import random
from decimal import Decimal
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1240, 1754


def font(size, bold=False):
    for name in (("arialbd.ttf", "calibrib.ttf") if bold else ("arial.ttf", "calibri.ttf")):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def render(out, supplier, addr, number, datestr, items, *, subtotal=None,
           blur_tax=False, total_override=None, second_total=False,
           skew=0.0, noise=0, blur=0.0, hide_number=False):
    """Draw one invoice. Pass overrides to break it in a specific way."""
    line_sum = sum(Decimal(a.replace(",", "")) for _, _, _, a in items)
    sub = Decimal(subtotal) if subtotal else line_sum
    tax = (sub * Decimal("0.14")).quantize(Decimal("0.01"))
    total = Decimal(total_override) if total_override else sub + tax

    def m(v):
        return f"{v:,.2f}"

    img = Image.new("RGB", (W, H), (253, 252, 250))
    d = ImageDraw.Draw(img)

    d.text((70, 70), supplier, font=font(36, True), fill=(20, 20, 20))
    d.text((70, 116), addr, font=font(20), fill=(70, 70, 70))
    d.text((860, 74), "INVOICE", font=font(32, True), fill=(20, 20, 20))
    if not hide_number:
        d.text((860, 122), f"No.  {number}", font=font(21), fill=(30, 30, 30))
    d.text((860, 150), f"Date  {datestr}", font=font(21), fill=(30, 30, 30))
    d.line([(70, 200), (1170, 200)], fill=(120, 120, 120), width=2)

    d.text((70, 226), "BILL TO", font=font(17, True), fill=(110, 110, 110))
    d.text((70, 252), "Delta Marketing LLC", font=font(23), fill=(20, 20, 20))
    d.text((70, 282), "8 El-Thawra St, Heliopolis, Cairo", font=font(20), fill=(60, 60, 60))

    y = 360
    d.rectangle([(70, y), (1170, y + 40)], fill=(233, 233, 229))
    for label, x in (("DESCRIPTION", 84), ("QTY", 700), ("UNIT", 830), ("AMOUNT", 1010)):
        d.text((x, y + 11), label, font=font(18, True), fill=(40, 40, 40))
    y += 40
    for i, (desc, qty, unit, amt) in enumerate(items):
        if i % 2:
            d.rectangle([(70, y), (1170, y + 38)], fill=(247, 247, 244))
        for text, x in ((desc, 84), (qty, 700), (unit, 830), (amt, 1010)):
            d.text((x, y + 9), text, font=font(20), fill=(25, 25, 25))
        y += 38

    y += 30
    d.line([(700, y), (1170, y)], fill=(120, 120, 120), width=1)
    y += 16
    d.text((760, y), "Subtotal", font=font(21), fill=(40, 40, 40))
    d.text((1010, y), m(sub), font=font(21), fill=(25, 25, 25))
    y += 34
    d.text((760, y), "VAT 14%", font=font(21), fill=(40, 40, 40))
    d.text((1010, y), m(tax), font=font(21), fill=(25, 25, 25))
    if blur_tax:
        patch = img.crop((1000, y - 4, 1170, y + 30)).filter(ImageFilter.GaussianBlur(4.2))
        img.paste(patch, (1000, y - 4))
        d = ImageDraw.Draw(img)
    y += 44
    d.text((760, y), "TOTAL  EGP", font=font(25, True), fill=(20, 20, 20))
    d.text((1000, y), m(total), font=font(25, True), fill=(20, 20, 20))

    if second_total:
        d.text((70, y + 120), f"Amount due on delivery:  EGP {m(total - Decimal('90'))}",
               font=font(20), fill=(90, 90, 90))
    d.text((70, y + 160), "Payment terms: net 30 days.", font=font(19), fill=(110, 110, 110))

    if skew:
        img = img.rotate(skew, expand=True, fillcolor=(253, 252, 250))
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    if noise:
        px = img.load()
        for _ in range(noise):
            x, yy = random.randrange(img.width), random.randrange(img.height)
            v = random.randint(-24, 24)
            r, g, b = px[x, yy]
            px[x, yy] = (max(0, min(255, r + v)), max(0, min(255, g + v)), max(0, min(255, b + v)))

    img.save(f"samples/{out}.png")
    status = "CLEAN" if not (blur_tax or subtotal or total_override or hide_number) else "BROKEN"
    print(f"  {status:6} samples/{out}.png   sub {m(sub)}  tax {m(tax)}  total {m(total)}")


random.seed(11)
print("Generating batch...\n")

render("clean-01", "Cairo Paper Co", "22 Talaat Harb, Downtown Cairo",
       "CP-4417", "12/08/2026",
       [("A4 Copy Paper, 80gsm (box)", "2", "1,200.00", "2,400.00"),
        ("Box files, foolscap", "1", "850.00", "850.00"),
        ("Highlighters (pk 6)", "3", "140.00", "420.00")],
       skew=-0.4, noise=6000)

render("clean-02", "Alexandria Tech Trading", "9 Sharia Fouad, Alexandria",
       "ATT-2026-118", "28/07/2026",
       [("USB-C dock, 8-port", "5", "99.50", "497.50"),
        ("27in monitor, 1440p", "2", "1,250.00", "2,500.00")],
       skew=0.7, noise=9000, blur=0.4)

render("clean-03", "Giza Print House", "51 Pyramids Rd, Giza",
       "GPH-0993", "03/09/2026",
       [("Business cards, 500pc", "10", "45.00", "450.00"),
        ("Roll-up banner 85x200", "4", "320.00", "1,280.00"),
        ("Lamination, A3", "1", "75.00", "75.00")],
       noise=4000)

render("clean-04", "Maadi Facility Services", "3 Road 9, Maadi, Cairo",
       "MFS-7712", "19/08/2026",
       [("Monthly cleaning contract", "1", "6,400.00", "6,400.00"),
        ("Consumables restock", "2", "375.00", "750.00")],
       skew=-1.1, noise=11000, blur=0.5)

render("broken-missing-number", "Heliopolis Hardware", "77 Merghany St, Cairo",
       "HH-0041", "22/08/2026",
       [("Cordless drill 18V", "1", "3,200.00", "3,200.00"),
        ("Drill bit set, 40pc", "2", "410.00", "820.00")],
       hide_number=True, noise=7000)

render("broken-bad-total", "Nasr City Electric", "18 Abbas El-Akkad, Cairo",
       "NCE-5520", "30/08/2026",
       [("Cable, 2.5mm (100m)", "4", "780.00", "3,120.00"),
        ("Circuit breakers, 32A", "8", "110.00", "880.00")],
       total_override="4650.00", skew=0.5, noise=6000)

print("\nDone. Existing samples/messy-invoice.png is unchanged.")
