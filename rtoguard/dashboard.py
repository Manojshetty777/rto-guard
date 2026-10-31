"""One-screen morning dashboard for the founder. Numbers are ESTIMATES from model risk (outcomes
are unknown on the morning after an order), clearly labelled; for past days we also show what really happened."""
import pandas as pd
from html import escape
from . import data, impact
from .engine import Engine, NAMES, SHIP, NUDGE, CONFIRM, HOLD

CSS = """
:root{--bg:#f7f6f2;--card:#fff;--ink:#1d1d1b;--mute:#6b6a65;--line:#e4e2da;--good:#1b7f4b;--bad:#b3261e;--accent:#3b5bdb}
@media(prefers-color-scheme:dark){:root{--bg:#161614;--card:#201f1d;--ink:#f1efe9;--mute:#a09e97;--line:#34322e;--good:#4cc38a;--bad:#ff8a80;--accent:#8ea2ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1000px;margin:0 auto;padding:20px 16px 40px}h1{font-size:20px;margin:0}.sub{color:var(--mute);margin:2px 0 18px}
.grid{display:grid;gap:12px}.g4{grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.k{font-size:12px;color:var(--mute);text-transform:uppercase;letter-spacing:.04em}.v{font-size:30px;font-weight:650;margin-top:2px}.s{font-size:13px;color:var(--mute)}
.good{color:var(--good)}.bad{color:var(--bad)}h2{font-size:15px;margin:22px 0 8px}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--mute);font-weight:500}
.alert{background:#fff3cd;color:#664d03;border-radius:10px;padding:10px 14px;margin-bottom:12px}.note{font-size:12.5px;color:var(--mute);margin-top:14px}
.pill{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;border:1px solid var(--line)}
"""

def rs(x): return ("-" if x < 0 else "") + "\u20b9" + f"{abs(round(x)):,}"

def day_report(engine: Engine, df: pd.DataFrame, day: str):
    d = df[df.order_datetime.dt.strftime("%Y-%m-%d") == day].reset_index(drop=True)
    dec = engine.decide_frame(d)
    counts, est = impact.summarise(engine.econ, dec, d, realized=False)
    _, real = impact.summarise(engine.econ, dec, d, realized=True)
    return d, dec, counts, est, real

def render(engine, df, day=None):
    if day is None: day = df.order_datetime.max().strftime("%Y-%m-%d")
    d, dec, counts, est, real = day_report(engine, df, day)
    n = max(len(d), 1)
    hold_share = counts[HOLD] / n
    maxh = engine.rules["protect_growth"]["max_hold_share"]
    card = lambda k, v, s="", cls="": f'<div class="card"><div class="k">{k}</div><div class="v {cls}">{v}</div><div class="s">{s}</div></div>'
    buckets = "".join(card(NAMES[a], counts[a], f"{counts[a]/n:.0%} of {len(d)} orders") for a in (SHIP, NUDGE, CONFIRM, HOLD))
    money = "".join([
        card("Saved from avoided RTOs", rs(est["saved_rto"] + est["recovered"]), f"RTO costs avoided {rs(est['saved_rto'])} + sales recovered {rs(est['recovered'])}", "good"),
        card("Lost on orders that may have been genuine", rs(-est["lost_genuine"]), "cancelled or never confirmed", "bad"),
        card("Discounts + WhatsApp cost", rs(-est["costs"]), "price of the prepaid offers and messages", "bad"),
        card("Net \u20b9 impact", rs(est["net"]), "vs. shipping every order as COD", "good" if est["net"] >= 0 else "bad")])
    alert = f'<div class="alert">\u26a0\ufe0f {hold_share:.0%} of yesterday\'s orders were held (limit {maxh:.0%}). Check the hold list below - the rules may be too strict.</div>' if hold_share > maxh else ""
    rows = "".join(f"<tr><td>{escape(x.order_id)}</td><td>{escape(str(r.customer_name))}, {escape(str(r.city))}</td><td>{rs(r.order_value)}</td><td>{x.risk:.0%}</td><td>{escape(x.reason)}</td></tr>"
                   for x, r in zip(dec, d.itertuples()) if x.action in (HOLD,))
    conf = "".join(f"<tr><td>{escape(x.order_id)}</td><td>{escape(str(r.customer_name))}, {escape(str(r.city))}</td><td>{rs(r.order_value)}</td><td>{x.risk:.0%}</td><td>{escape(x.reason)}</td></tr>"
                   for x, r in sorted(zip(dec, d.itertuples()), key=lambda t: -t[0].risk) if x.action == CONFIRM)[:0]
    top = sorted([(x, r) for x, r in zip(dec, d.itertuples()) if x.action == CONFIRM], key=lambda t: -t[0].risk)[:8]
    conf = "".join(f"<tr><td>{escape(x.order_id)}</td><td>{escape(str(r.customer_name))}, {escape(str(r.city))}</td><td>{rs(r.order_value)}</td><td>{x.risk:.0%}</td><td>{escape(x.reason)}</td></tr>" for x, r in top)
    tbl = lambda title, body: f"<h2>{title}</h2><table><tr><th>Order</th><th>Customer</th><th>Value</th><th>Risk</th><th>Why</th></tr>{body or '<tr><td colspan=5>None</td></tr>'}</table>"
    actual = ""
    if d.rto.notna().all():
        actual = (f'<div class="note">Replay check (outcomes are known for past dates): {int(d.rto.sum())} of {len(d)} COD orders really came back. '
                  f'Using real outcomes the net would have been {rs(real["net"])}.</div>')
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RTO Guard - morning view</title><style>{CSS}</style></head><body><main>
<h1>RTO Guard: yesterday's COD orders</h1><div class="sub">{day} - {len(d)} COD orders - average risk {sum(x.risk for x in dec)/n:.0%}</div>{alert}
<div class="grid g4">{buckets}</div><h2>\u20b9 impact (estimated)</h2><div class="grid g4">{money}</div>
{tbl("Held / cancelled - needs a human glance", rows)}{tbl("Highest-risk orders waiting on WhatsApp confirmation", conf)}
<div class="note">Estimates use each order's risk score and the assumptions in config/rules.yaml (reply rates, prepaid acceptance). They are not accounting figures: compare with real RTO numbers after 2 weeks and update the assumptions.</div>{actual}
</main></body></html>"""
