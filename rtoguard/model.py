"""Risk model = plain logistic regression (a transparent scorecard), not a black box.
City risk is a smoothed historical RTO rate (shrunk toward the national average, so a city with
3 orders cannot look like 100% risk). Pincodes are NOT used: 1,066 pincodes for ~2,000 orders
means the median pincode has 1 order - far too thin to learn from."""
import json
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import KFold

FEATURES = ["city_risk", "addr_junk", "addr_landmark_only", "fake_name", "bad_phone", "first_time",
            "prior_rto_1", "prior_rto_2plus", "value_high", "meta_ads", "no_pincode"]
LABELS = {  # plain-English text used in the per-order reason
    "city_risk": "delivery city has a high return history",
    "addr_junk": "address is unusable",
    "addr_landmark_only": "address has landmarks but no house number",
    "fake_name": "customer name looks fake",
    "bad_phone": "phone number looks invalid",
    "first_time": "first order from this customer",
    "prior_rto_1": "customer refused one earlier order",
    "prior_rto_2plus": "customer refused 2+ earlier orders",
    "value_high": "unusually high order value",
    "meta_ads": "came from Meta ads",
    "no_pincode": "pincode missing",
}
K = 20  # shrinkage strength: a city needs ~20 orders before its own rate dominates

def city_table(df):
    g = df.groupby("city").rto.agg(["sum", "count"])
    prior = df.rto.mean()
    g["rate"] = (g["sum"] + K * prior) / (g["count"] + K)
    return {"prior": prior, "rates": g["rate"].to_dict()}

def city_rate(tbl, city):
    return tbl["rates"].get(city, tbl["prior"])

def _X(df, feats, tbl):
    X = feats.copy()
    X["city_risk"] = df.city.map(lambda c: city_rate(tbl, c))
    return X[FEATURES]

def fit(df, feats):
    # out-of-fold city rates for training rows, so a city's own outcome never leaks into its feature
    oof = pd.Series(index=df.index, dtype=float)
    for tr, te in KFold(5, shuffle=True, random_state=0).split(df):
        t = city_table(df.iloc[tr])
        oof.iloc[te] = df.iloc[te].city.map(lambda c: city_rate(t, c)).values
    X = feats.copy(); X["city_risk"] = oof; X = X[FEATURES]
    lr = LogisticRegression(C=1.0, max_iter=2000).fit(X, df.rto)
    return {"coef": {f: round(float(c), 4) for f, c in zip(FEATURES, lr.coef_[0])}, "intercept": float(lr.intercept_[0]),
            "city": city_table(df)}

def predict(m, df, feats):
    X = _X(df, feats, m["city"])
    z = m["intercept"] + sum(m["coef"][f] * X[f] for f in FEATURES)
    return 1 / (1 + np.exp(-z)), X

def explain(m, xrow, top=3):
    """Top risk-raising factors for one order, in plain English."""
    base = m["city"]["prior"]
    contrib = {}
    for f in FEATURES:
        v = xrow[f] - (base if f == "city_risk" else 0)
        c = m["coef"][f] * v
        if f == "city_risk" and xrow[f] < base + 0.05:  # only flag clearly-risky cities
            continue
        if c > 0.15:
            contrib[f] = c
    top_f = sorted(contrib, key=contrib.get, reverse=True)[:top]
    out = []
    for f in top_f:
        out.append(LABELS[f] + (f" ({xrow[f]:.0%} of past orders there came back)" if f == "city_risk" else ""))
    return out

def save(m, path="config/model.json"):
    json.dump(m, open(path, "w"), indent=1)

def load(path="config/model.json"):
    return json.load(open(path))
