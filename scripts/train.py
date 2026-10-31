"""Train the risk model on ALL cleaned data and save config/model.json.
Also prints an honest out-of-time check: train on Apr-Aug, test on Sep."""
import sys; sys.path.insert(0, ".")
import pandas as pd
from sklearn.metrics import roc_auc_score
from rtoguard import data, features, model

df, log = data.load_orders()
f = features.build(df)
tr = df.order_datetime < "2026-09-01"
m = model.fit(df[tr], f[tr]); p, _ = model.predict(m, df[~tr], f[~tr])
print(f"Cleaning: {log}")
print(f"Out-of-time check (train Apr-Aug n={tr.sum()}, test Sep n={(~tr).sum()}): AUC = {roc_auc_score(df[~tr].rto, p):.3f}")
t = df[~tr].assign(p=p); t["band"] = pd.qcut(t.p, 5, duplicates="drop")
print(t.groupby("band", observed=True).agg(orders=("rto", "size"), predicted=("p", "mean"), actual=("rto", "mean")).round(3))
model.save(model.fit(df, f))
print("saved config/model.json (fitted on all data)")
