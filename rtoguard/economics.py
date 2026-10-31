"""All rupee maths lives here. Plain code - no LLM."""
import yaml

def load_rules(path="config/rules.yaml"):
    return yaml.safe_load(open(path))

class Econ:
    def __init__(self, rules):
        c, a = rules["costs"], rules["assumptions"]
        self.c, self.a, self.pd = c, a, rules["prepaid_discount"]
        # What one RTO costs us: both shipping legs + packing + expected write-off of damaged stock
        self.rto_loss = (c["forward_shipping"] + c["return_shipping"] + c["packaging_handling"]
                         + c["damaged_return_share"] * c["product_cost"])

    def margin(self, value):
        """Profit on a delivered order after shipping and packing."""
        c = self.c
        return c["gross_margin"] * value - c["forward_shipping"] - c["packaging_handling"]

    def ev_ship(self, p, value, first_time=False):
        m = self.margin(value) + (self.a["repeat_value_first_order"] if first_time else 0)
        return (1 - p) * m - p * self.rto_loss

    def _nudge_terms(self, p, value, first_time=False):
        a, q = self.a, self.c["prepaid_rto_rate"]
        m = self.margin(value) + (a["repeat_value_first_order"] if first_time else 0)
        kg, kr = a["nudge_accept_genuine"], a["nudge_accept_risky"]
        gain = kr * p * (1 - q) * (m + self.rto_loss)       # a would-be refuser pays online and takes delivery
        leak = kg * (1 - p) + kr * p * (1 - q)              # everyone who accepts gets the discount
        return gain, leak

    def prepaid_breakeven(self, p, value):
        """Largest discount at which the nudge is still no worse than just shipping COD.
        Gain from converting would-be refusers (prepaid RTO only ~4%) must pay for the discount
        handed to ALL who accept, including genuine customers who would have paid COD anyway."""
        gain, leak = self._nudge_terms(p, value)
        return max(0.0, (gain - self.c["whatsapp_cost_per_order"]) / leak)

    def discount(self, p, value):
        d = self.pd["share_of_break_even"] * self.prepaid_breakeven(p, value)
        d = min(max(d, self.pd["min_rupees"]), self.pd["max_percent_of_order"] * value)
        r = self.pd["round_to"]
        return float(round(d / r) * r)

    def ev_confirm(self, p, value, first_time=False):
        a = self.a
        m = self.margin(value) + (a["repeat_value_first_order"] if first_time else 0)
        gen = (1 - p) * a["confirm_reply_genuine"] * m
        bad = p * a["confirm_reply_risky"] * (a["confirm_risky_then_accept"] * m
                                              - (1 - a["confirm_risky_then_accept"]) * self.rto_loss)
        return gen + bad - self.c["whatsapp_cost_per_order"]

    def ev_nudge(self, p, value, first_time=False):
        gain, leak = self._nudge_terms(p, value, first_time)
        d = self.discount(p, value)
        return self.ev_ship(p, value, first_time) + gain - leak * d - self.c["whatsapp_cost_per_order"]
