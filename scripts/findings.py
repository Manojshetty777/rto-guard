"""Numbers quoted in the business memo. Run: python scripts/findings.py"""
import sys; sys.path.insert(0, ".")
import pandas as pd
from rtoguard import data, features
from rtoguard.economics import Econ, load_rules
df, log = data.load_orders(); f = features.build(df, use_llm=False); d = df.join(f)
E = Econ(load_rules()); L = E.rto_loss
pr = lambda s, m: print(f"{s}: n={len(m)} ({len(m)/len(d):.1%} of orders) RTO={m.rto.mean():.1%}  share of all RTOs={m.rto.sum()/d.rto.sum():.1%}")
print(log); print(f"overall RTO {d.rto.mean():.1%}, cost per RTO Rs{L:.1f}, total RTO cost Rs{d.rto.sum()*L:,.0f}")
pr("junk address", d[d.addr_junk == 1]); pr("fake name", d[d.fake_name == 1])
pr("junk OR fake", d[(d.addr_junk == 1) | (d.fake_name == 1)])
_g = d.groupby("city").rto.agg(["mean","count"]); hot = d.city.isin(_g[(_g["mean"] > .40) & (_g["count"] >= 20)].index)
print("hot cities:", sorted(d[hot].city.unique())); pr("hot cities", d[hot]); pr("other cities", d[~hot])
print(d.groupby("city").rto.agg(["count", "mean"]).sort_values("mean", ascending=False).round(3).head(8))
for flag, name in ((d.first_time == 1, "first-time"), (d.first_time == 0, "repeat")): pr(name, d[flag])
clean = (d.addr_junk == 0) & (d.fake_name == 0) & ~hot
print("first-time, clean address+name, non-hot city:", f"{d[clean & (d.first_time==1)].rto.mean():.1%} (n={int((clean&(d.first_time==1)).sum())})",
      "| repeat same:", f"{d[clean & (d.first_time==0)].rto.mean():.1%}")
print("prior_rto:", d.groupby("customer_prior_rto").rto.agg(["count", "mean"]).round(3).to_dict("index"))
print("pincodes:", d.pincode.nunique(), "median orders/pincode", d.groupby("pincode").size().median(), "share of pincodes with >=10 orders", (d.groupby("pincode").size() >= 10).mean())
hing = d.addr_quality.isin(["landmark_only", "partial"])
print("landmark/Hinglish-style address: all cities", f"{d[hing].rto.mean():.1%}", "| in non-hot cities", f"{d[hing & ~hot].rto.mean():.1%} vs complete in non-hot {d[(d.addr_quality=='complete') & ~hot].rto.mean():.1%}",
      "| in hot cities", f"{d[hing & hot].rto.mean():.1%} vs complete {d[(d.addr_quality=='complete') & hot].rto.mean():.1%}")
print("value>1800:", f"{d[d.value_high==1].rto.mean():.1%} n={int(d.value_high.sum())}")
print("meta:", f"{d[d.meta_ads==1].rto.mean():.1%} vs other {d[d.meta_ads==0].rto.mean():.1%}")
print("bad phone:", f"{d[d.bad_phone==1].rto.mean():.1%} n={int(d.bad_phone.sum())}")
mv = d.order_value.mean(); print("avg order value in data Rs", round(mv), "(brief says 649)")
print("cost of RTO as % of margin on delivered:", round(L/E.margin(649)*100), "% of a Rs649 order's margin of Rs", round(E.margin(649)))
print("break-even RTO rate to justify cancel (V=649):", round(E.margin(649)/(E.margin(649)+L), 3), " (V=918):", round(E.margin(918)/(E.margin(918)+L), 3))
