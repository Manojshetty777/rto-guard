"""decide(order) -> one of 4 actions + plain-English reason.
Order of play: (1) hard guardrails, (2) risk score vs thresholds in rules.yaml, (3) growth protection."""
from dataclasses import dataclass, field, asdict
import pandas as pd
from . import features, model
from .economics import Econ, load_rules

SHIP, NUDGE, CONFIRM, HOLD = "SHIP", "NUDGE_PREPAID", "CONFIRM", "HOLD"
NAMES = {SHIP: "Ship as-is", CONFIRM: "Ship after confirmation", NUDGE: "Nudge to prepaid", HOLD: "Hold / cancel"}

@dataclass
class Decision:
    order_id: str
    action: str
    risk: float
    reason: str
    discount: float = 0.0
    rule: str = ""
    factors: list = field(default_factory=list)
    judge_source: str = ""
    def to_dict(self): return asdict(self)

class Engine:
    def __init__(self, rules_path="config/rules.yaml", model_path="config/model.json", use_llm=True):
        self.rules = load_rules(rules_path)
        self.econ = Econ(self.rules)
        self.model = model.load(model_path)
        self.use_llm = use_llm

    def score_frame(self, df):
        f = features.build(df, self.use_llm)
        p, X = model.predict(self.model, df, f)
        return f, p, X

    def decide_frame(self, df):
        f, p, X = self.score_frame(df)
        out = []
        for i, row in enumerate(df.itertuples()):
            out.append(self._decide(row, f.iloc[i], X.iloc[i], float(p.iloc[i])))
        return out

    def decide(self, order: dict):
        return self.decide_frame(pd.DataFrame([order]))[0]

    def _decide(self, row, f, x, p):
        th, g, ops = self.rules["thresholds"], self.rules["protect_growth"], self.rules["protect_ops"]
        factors = model.explain(self.model, x)
        first = bool(f.first_time)
        d = self.econ.discount(p, row.order_value)
        why = ("; ".join(factors) if factors else "no major risk signals")
        def mk(action, reason, rule, disc=0.0):
            return Decision(row.order_id, action, round(p, 3), reason, disc, rule, factors, f.judge_source)

        # 1) hard guardrails ------------------------------------------------------------------
        if f.bad_phone:
            if self.rules["unreachable_phone"] == "hold" and not (first and g["first_orders_never_cancelled"] and p < g["first_order_hold_from"]):
                return mk(HOLD, f"Phone number looks invalid, so we cannot confirm or reach the customer. {p:.0%} risk. Why: {why}.", "unreachable_phone")
        if f.addr_junk and f.fake_name and ops["unusable_address_and_fake_name"] == "hold":
            return mk(HOLD, f"Address is unusable and the name looks fake: nobody to deliver to. {p:.0%} risk.", "junk_address_and_fake_name")
        if row.customer_prior_rto >= 2 and ops["refused_twice_before"] == "hold":
            return mk(HOLD, f"Customer refused {int(row.customer_prior_rto)} earlier orders. {p:.0%} risk.", "refused_twice_before")

        # 2) thresholds -------------------------------------------------------------------------
        hold_from = g["first_order_hold_from"] if (first and g["first_orders_never_cancelled"]) else th["hold_from"]
        if p >= hold_from:
            return mk(HOLD, f"{p:.0%} chance this order comes back, too high to ship even after confirmation. Why: {why}.", "risk>=hold_from")
        if p >= th["confirm_from"]:
            note = " First order: we confirm rather than cancel, to protect the ad spend." if (first and p >= th["hold_from"]) else ""
            return mk(CONFIRM, f"{p:.0%} chance this order comes back. Customer confirms on WhatsApp before we ship. Why: {why}.{note}", "risk>=confirm_from")
        if p >= th["ship_below"]:
            return mk(NUDGE, f"{p:.0%} chance this order comes back. Offer Rs{d:.0f} off to pay online (prepaid returns are ~4%). Why: {why}.", "risk>=ship_below", d)
        return mk(SHIP, f"Low risk ({p:.0%}). Ship as normal.", "risk<ship_below")
