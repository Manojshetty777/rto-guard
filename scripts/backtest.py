"""Replay last month (September). The model is trained ONLY on April-August, so this is a fair test.
Counts per bucket and actual RTO rates are facts; Rs impact uses the behaviour assumptions in rules.yaml."""
import sys, json; sys.path.insert(0, ".")
import pandas as pd
from rtoguard import data, features, model, impact
from rtoguard.engine import Engine, NAMES, SHIP, NUDGE, CONFIRM, HOLD

df, _ = data.load_orders()
f = features.build(df)
tr = df.order_datetime < "2026-09-01"
m = model.fit(df[tr], f[tr]); model.save(m, "output/model_backtest.json")
sep = df[~tr].reset_index(drop=True)
eng = Engine(model_path="output/model_backtest.json")
dec = eng.decide_frame(sep)
sep["action"] = [d.action for d in dec]; sep["risk"] = [d.risk for d in dec]

print(f"September: {len(sep)} COD orders, {sep.rto.mean():.1%} came back. Baseline RTO cost = Rs{sep.rto.sum()*eng.econ.rto_loss:,.0f}")
t = sep.groupby("action").agg(orders=("rto", "size"), actual_rto_rate=("rto", "mean"), avg_value=("order_value", "mean")).round(3)
t["share"] = (t.orders / len(sep)).round(3)
print(t.rename(index=NAMES))
counts, tot = impact.summarise(eng.econ, dec, sep, realized=True)
print("Realized impact vs shipping everything (Rs):", tot)

# What would the two leaders' policies have done? (realized outcomes, no behaviour assumptions needed)
L = eng.econ.rto_loss
def cancel_policy(mask, name):
    s = sep[mask]; saved = s.rto.sum() * L
    lost = sum(eng.econ.margin(r.order_value) + (eng.econ.a["repeat_value_first_order"] if r.customer_prior_orders == 0 else 0)
               for r in s.itertuples() if r.rto == 0)
    print(f"{name}: cancels {mask.sum()} orders ({mask.mean():.0%}); saves Rs{saved:,.0f} of RTO cost, loses Rs{lost:,.0f} of genuine margin, net Rs{saved-lost:,.0f}")
    return dict(cancelled=int(mask.sum()), saved=round(saved), lost=round(lost), net=round(saved - lost))
res = {"ops_cancel_risky": cancel_policy(sep.risk >= 0.40, "OPS 'cancel anything risky (>=40%)'"),
       "ops_cancel_30": cancel_policy(sep.risk >= 0.30, "OPS 'cancel >=30%'"),
       "ours": tot, "counts": counts, "rto_cost_baseline": round(sep.rto.sum() * L)}
first = sep.customer_prior_orders == 0
print("first-time orders held/cancelled by our rules:", int(((sep.action == HOLD) & first).sum()), "of", int(first.sum()))
print("first-time orders in confirm/nudge:", int(((sep.action.isin([CONFIRM, NUDGE])) & first).sum()))
json.dump(res, open("output/backtest.json", "w"), indent=1)
sep.to_csv("output/september_decisions.csv", index=False)
