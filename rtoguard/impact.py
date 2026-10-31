"""Rupee impact of each decision vs. the do-nothing baseline (ship every COD order as-is).
Formulas are linear in w = chance the order would come back:
  expected (live dashboard): w = model risk.   realized (backtest): w = 1 if it really came back else 0.
Components (all Rs):
  saved_rto     - RTO costs avoided (shipping both ways, packing, damaged stock)
  recovered     - margin from would-be refusers who took delivery after confirmation / prepaid
  lost_genuine  - margin lost on orders that would have been delivered (cancelled / never confirmed)
  costs         - prepaid discounts given + WhatsApp messages
"""
from .engine import SHIP, NUDGE, CONFIRM, HOLD

def order_impact(econ, action, w, value, first_time=False, discount=0.0):
    L, a, q = econ.rto_loss, econ.a, econ.c["prepaid_rto_rate"]
    m = econ.margin(value) + (a["repeat_value_first_order"] if first_time else 0)
    c = econ.c["whatsapp_cost_per_order"]
    z = dict(saved_rto=0.0, recovered=0.0, lost_genuine=0.0, costs=0.0)
    if action == HOLD:
        z["saved_rto"] = w * L
        z["lost_genuine"] = (1 - w) * m
    elif action == CONFIRM:
        rb, acc, rg = a["confirm_reply_risky"], a["confirm_risky_then_accept"], a["confirm_reply_genuine"]
        z["saved_rto"] = w * ((1 - rb) * L + rb * acc * L)
        z["recovered"] = w * rb * acc * m
        z["lost_genuine"] = (1 - w) * (1 - rg) * m
        z["costs"] = c
    elif action == NUDGE:
        kg, kr = a["nudge_accept_genuine"], a["nudge_accept_risky"]
        z["saved_rto"] = w * kr * (1 - q) * L
        z["recovered"] = w * kr * (1 - q) * m
        z["costs"] = (1 - w) * kg * discount + w * kr * (1 - q) * discount + c
    z["net"] = z["saved_rto"] + z["recovered"] - z["lost_genuine"] - z["costs"]
    return z

def summarise(econ, decisions, df, realized=False):
    """decisions: list[Decision] aligned with df rows."""
    tot = dict(saved_rto=0.0, recovered=0.0, lost_genuine=0.0, costs=0.0, net=0.0)
    counts = {SHIP: 0, NUDGE: 0, CONFIRM: 0, HOLD: 0}
    for d, r in zip(decisions, df.itertuples()):
        w = float(r.rto) if realized else d.risk
        z = order_impact(econ, d.action, w, r.order_value, r.customer_prior_orders == 0, d.discount)
        for k in tot: tot[k] += z[k]
        counts[d.action] += 1
    return counts, {k: round(v) for k, v in tot.items()}
