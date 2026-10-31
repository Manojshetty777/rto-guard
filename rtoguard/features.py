"""Deterministic features. No LLM here: these have right/wrong answers."""
import re
import pandas as pd
from . import llm

VALID_PHONE = re.compile(r"^(\+91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}$")

def phone_ok(p):
    p = str(p).strip()
    return bool(VALID_PHONE.match(p))

def build(df, use_llm=True):
    out = pd.DataFrame(index=df.index)
    j = [llm.judge(r.address, r.city, r.state, r.customer_name, use_llm) for r in df.itertuples()]
    out["addr_quality"] = [x["address_quality"] for x in j]
    out["fake_name"] = [int(x["fake_name"]) for x in j]
    out["judge_source"] = [x["source"] for x in j]
    out["addr_reason"] = [x["reason"] for x in j]
    out["addr_junk"] = (out.addr_quality == "junk").astype(int)
    out["addr_landmark_only"] = out.addr_quality.isin(["landmark_only", "partial"]).astype(int)
    out["bad_phone"] = (~df.phone.map(phone_ok)).astype(int)
    out["first_time"] = (df.customer_prior_orders == 0).astype(int)
    out["prior_rto_1"] = (df.customer_prior_rto == 1).astype(int)
    out["prior_rto_2plus"] = (df.customer_prior_rto >= 2).astype(int)
    out["value_high"] = (df.order_value > 1800).astype(int)
    out["meta_ads"] = (df.utm_source == "meta_ads").astype(int)
    out["no_pincode"] = df.pincode.isna().astype(int)
    return out
