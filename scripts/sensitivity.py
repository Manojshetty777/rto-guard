"""How much do the thresholds matter? Replays September for a grid of settings (realized outcomes)."""
import sys, copy; sys.path.insert(0, ".")
from rtoguard import data, features, impact
from rtoguard.engine import Engine
df, _ = data.load_orders(); sep = df[df.order_datetime >= "2026-09-01"].reset_index(drop=True)
base = Engine(model_path="output/model_backtest.json")
f, p, X = base.score_frame(sep)
print("ship_below confirm_from hold_from |  held confirm nudge ship |  net_Rs")
for sb in (0.15, 0.20, 0.25, 0.30):
    for cf in (0.30, 0.35, 0.40, 0.50):
        for hf in (0.60, 0.68, 0.80):
            e = Engine(model_path="output/model_backtest.json")
            e.rules["thresholds"].update(ship_below=sb, confirm_from=cf, hold_from=hf)
            dec = [e._decide(r, f.iloc[i], X.iloc[i], float(p.iloc[i])) for i, r in enumerate(sep.itertuples())]
            c, t = impact.summarise(e.econ, dec, sep, realized=True)
            if hf == 0.68:
                print(f"{sb:.2f}  {cf:.2f}  {hf:.2f} | {c['HOLD']:4d} {c['CONFIRM']:5d} {c['NUDGE_PREPAID']:5d} {c['SHIP']:4d} | {t['net']:6,d}")

print("\nRobustness: does the net stay positive if our behaviour assumptions are too rosy? (default thresholds)")
cases = {
  "assumptions as set in rules.yaml": {},
  "customers reply/accept 30% less": dict(confirm_reply_genuine=0.56, confirm_reply_risky=0.21, nudge_accept_genuine=0.21, nudge_accept_risky=0.105),
  "genuine customers reply only 60%": dict(confirm_reply_genuine=0.60),
  "no repeat-purchase value for 1st orders": dict(repeat_value_first_order=0),
  "risky customers never convert (worst case)": dict(confirm_risky_then_accept=0.0, nudge_accept_risky=0.0),
}
for name, ch in cases.items():
    e = Engine(model_path="output/model_backtest.json"); e.econ.a.update(ch)
    dec = [e._decide(r, f.iloc[i], X.iloc[i], float(p.iloc[i])) for i, r in enumerate(sep.itertuples())]
    c, t = impact.summarise(e.econ, dec, sep, realized=True)
    print(f"{name:45s} net Rs{t['net']:>7,d}  (saved {t['saved_rto']:,}, recovered {t['recovered']:,}, lost {t['lost_genuine']:,}, costs {t['costs']:,})")
