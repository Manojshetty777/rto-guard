"""Builds docs/business_memo.pdf (2 pages). Run: python scripts/make_memo.py"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
D = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("F", D + "DejaVuSans.ttf")); pdfmetrics.registerFont(TTFont("FB", D + "DejaVuSans-Bold.ttf"))
pdfmetrics.registerFontFamily("F", normal="F", bold="FB", italic="F", boldItalic="FB")
B = ParagraphStyle("b", fontName="F", fontSize=8.6, leading=11.6, spaceAfter=3)
H = ParagraphStyle("h", parent=B, fontName="FB", fontSize=10.2, spaceBefore=7, spaceAfter=3, textColor=colors.HexColor("#1b2a6b"))
T = ParagraphStyle("t", parent=B, fontName="FB", fontSize=14, leading=17, spaceAfter=1)
L = ParagraphStyle("l", parent=B, leftIndent=9, bulletIndent=0, spaceAfter=2)
def P(t): return Paragraph(t, B)
def bl(items): return [Paragraph(i, L, bulletText="•") for i in items]
R = "\u20b9"
s = [Paragraph("COD orders: what the data says and what I recommend", T),
 P("To: Founder &nbsp;|&nbsp; From: Manoj Shiva &nbsp;|&nbsp; 31 Oct 2026 &nbsp;|&nbsp; Based on 1,984 clean COD orders (Apr–Sep 2026)"),
 Paragraph("The short version", H),
 P(f"Every RTO costs us <b>{R}169</b> (shipping both ways, packing, damaged stock). But a delivered {R}649 order earns <b>{R}312</b> after shipping and packing. "
   f"So cancelling only pays when an order is more than ~65% likely to come back, and almost none are. The money is in (1) stopping unusable orders, (2) a WhatsApp confirmation for the ~14% of orders that bounce half the time, and (3) a small prepaid discount for the middle. "
   f"Replaying September, this would have added about <b>{R}5.7k on 329 sample orders (≈ {R}28k a month at ~1,650 COD orders)</b>, versus <b>–{R}10.8k</b> if we auto-cancelled everything above 40% risk. "
   f"The size of the gain rests on assumptions about how customers react, covered in section 4.")]
s += [Paragraph("1. What surprised me", H)] + bl([
 f"<b>Cancelling risky orders loses money.</b> In September, cancelling every order at 40%+ risk would have cancelled 53 orders, saved {R}4.9k of RTO cost, and thrown away {R}15.8k of margin on orders that would have been delivered. Net: –{R}10.8k. At 30%+ it is –{R}24.6k.",
 "<b>Bad data, not new customers, is the real problem.</b> Unusable addresses (“xyz”, “.”, “call me”, city name only) and fake names (“Test Order”, “asdf”) are 9.5% of orders and come back <b>60%</b> of the time: 20% of all RTOs. First-time buyers do come back more (30.3% vs 23.0% for repeat) but once I set aside junk orders and the six worst cities, it is 22% vs 15%.",
 "<b>Six cities drive the rest.</b> Gorakhpur 62%, Bareilly 61%, Darbhanga 59%, Sagar 49%, Patna 48%, Kota 41%: 16% of orders but 29% of RTOs. Metros are 18–25%. “Stop COD in bad pincodes” can't work: 1,066 pincodes for ~2,000 orders, median one order each, none with ten. City is the smallest unit with enough data.",
 "<b>Hinglish addresses are not a red flag.</b> Landmark-only addresses (“Big Bazaar ke paas”) look worse overall (31%), but that is mostly because they cluster in the risky cities: 24% vs 19% for fully structured addresses in ordinary cities, 51% vs 49% in the risky ones. We use AI to understand these addresses, not to punish them.",
 "<b>Repeat refusers are the clearest signal.</b> Customers who refused two earlier orders: 76% RTO (34 orders). One earlier refusal: 35%.",
 "<b>The file has problems:</b> 30 duplicate rows, three " + R + "0 orders, one still in transit, 17 invalid phone numbers (47% RTO), and an average order of " + R + "921, not " + R + "649."])
s += [Paragraph("2. Recommended rules, applied to September (329 COD orders)", H)]
rows = [["Risk of coming back", "Action", "Orders", "Share", "Actually came back"],
 ["Under 20%", "Ship as-is", "90", "27%", "7.8%"],
 ["20–40%", f"Prepaid offer ({R}30–60 off)", "186", "57%", "26.9%"],
 ["40–68%", "WhatsApp confirmation first", "46", "14%", "50.0%"],
 ["68%+, bad phone, junk address + fake name, 2+ earlier refusals", "Hold / cancel", "7", "2%", "85.7%"]]
C = ParagraphStyle("c", parent=B, fontSize=8, leading=9.6, spaceAfter=0)
CB = ParagraphStyle("cb", parent=C, fontName="FB")
rows = [[Paragraph(c, CB if i == 0 else C) for c in r] for i, r in enumerate(rows)]
t = Table(rows, colWidths=[64*mm, 45*mm, 18*mm, 14*mm, 36*mm])
t.setStyle(TableStyle([("FONT", (0,0), (-1,-1), "F", 8), ("FONT", (0,0), (-1,0), "FB", 8), ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#e8ebfa")),
  ("GRID", (0,0), (-1,-1), .4, colors.HexColor("#c8c8c8")), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("TOPPADDING", (0,0), (-1,-1), 2), ("BOTTOMPADDING", (0,0), (-1,-1), 2)]))
s += [t, Spacer(1, 3), P(f"The buckets separate cleanly: the ship group returns 7.8% of orders, the confirm group 50%. Estimated money effect: RTO costs avoided {R}5.5k + sales recovered from would-be refusers {R}6.1k – margin lost on genuine orders {R}3.5k – discounts and messages {R}2.5k = <b>{R}5.7k</b>, against a September RTO bill of {R}14.6k. "
 f"The prepaid discount is half of break-even: about {R}40 on a {R}649 order at 30% risk (6%), {R}60 at 40% (9%); full maths in <i>scripts/discount_math.py</i>. All thresholds are in one settings file anyone can edit.")]
s += [Paragraph("3. Operations vs. Marketing, in rupees", H)] + bl([
 f"<b>Operations gets</b> the bulk of the avoidable loss: junk and fake orders are held (7 in September, 86% of which came back), and the half-risky group has to confirm before we spend {R}130 on shipping.",
 f"<b>Marketing gets</b> real protection: only 4 of 241 first orders were held in September; the other 203 risky first orders were confirmed or offered a discount, never cancelled. The {R}300 ad spend is already gone either way, so it is no reason to ship a bad order. What matters is the customer's future value, which I assume is {R}100 per first order (to be measured). A wrongly cancelled first order costs ~{R}412; a true RTO costs {R}169, so we should only cancel when we are very sure.",
 "<b>The trade-off is one dial.</b> Making confirmation stricter or looser (30% to 50%) moves the September result only between {R}5.1k and {R}6.5k, so the choice is about customer friction, not money. A dashboard alarm fires if more than 8% of a day's orders are held.".replace("{R}", R)])
s += [Paragraph("4. What could go wrong, and how we'd notice", H)] + bl([
 f"<b>Customers may not react as I assumed</b> (reply rates, prepaid take-up). If customers respond 30% less, the net falls to ~{R}0.7k. If would-be refusers never convert, about –{R}1.2k (≈ –{R}6k a month). <i>Watch:</i> WhatsApp reply rate, RTO rate within the confirm group, prepaid share. Measure these in week one.",
 "<b>We lose genuine customers quietly.</b> <i>Watch:</i> orders cancelled for silence, customers replying “YES” after cancellation, and the hold-share alarm.",
 "<b>The model is small and will drift</b> (1,984 orders; out-of-time AUC 0.74). <i>Watch:</i> predicted vs actual RTO per bucket each week; retrain monthly.",
 "<b>AI address checks can be wrong.</b> I tested the pipeline with the rule-based fallback; the Claude-powered check is built but not yet validated on this data. Spot-check 50 judgements before relying on it. If the AI is down, orders still flow.",
 "<b>City as a signal can be unfair to honest customers in smaller cities.</b> That is why those orders get confirmation or a discount, not cancellation."])
s += [Paragraph("5. If I had two more weeks", H)] + bl([
 "<b>Prove it with a holdout:</b> leave 10% of orders untouched to measure the real effect of each intervention, and test three discount levels to replace my assumed take-up.",
 "Connect real WhatsApp, Shopify and payment links; build the human call queue for first orders.",
 "Check courier serviceability by pincode through the couriers' own APIs (Xpressbees returns 31% vs Delhivery 26%, which needs a controlled test), and add address verification and auto-correction.",
 "Retrain monthly and alert on drift; validate the AI address judge against a hand-labelled sample."])
SimpleDocTemplate("docs/business_memo.pdf", pagesize=A4, leftMargin=16*mm, rightMargin=16*mm, topMargin=13*mm, bottomMargin=12*mm,
                  title="COD orders memo", author="Manoj Shiva").build(s)
print("wrote docs/business_memo.pdf")
