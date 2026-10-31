"""WhatsApp confirmation + prepaid-nudge flows, with a mock WhatsApp API (no real account needed).

Design rules
  * Language: Hinglish (Roman Hindi) by default; English for the southern states and when the
    customer's own address is in English. Customers can switch by replying in the other language.
  * Never message at night: messages queue until 09:00 (orders placed 21:00-09:00).
  * Never leave an order in limbo: every path ends in SHIP / SHIP_COD / SHIP_PREPAID / CANCELLED / CALL_QUEUE.
  * Cancel only when the customer says NO, or stays silent on a CONFIRM order. Silence on a NUDGE
    order simply ships COD (the order was low enough risk to ship anyway).
  * First-time customers are never auto-cancelled for silence: they get one human call first.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from . import llm

SOUTH = {"Karnataka", "Tamil Nadu", "Telangana"}

def language(state, address_lang="hinglish"):
    return "en" if (state in SOUTH or address_lang == "english") else "hi"

T = {  # message templates
 "confirm": {
  "hi": "Namaste {name}! \U0001F64F {brand} par aapka COD order #{oid} ({items}, \u20b9{value}) mila hai. Delivery se pehle confirm kar dein:\n\u2705 Reply *YES* - order bhej dein\n\u274c Reply *NO* - cancel kar dein{addr}",
  "en": "Hi {name}! \U0001F64F We received your COD order #{oid} ({items}, \u20b9{value}) at {brand}. Please confirm before we ship:\n\u2705 Reply *YES* to confirm\n\u274c Reply *NO* to cancel{addr}"},
 "addr_ask_hi": " Aapka address poora nahi dikh raha - kripya pura address (ghar no., colony, pincode) bhi bhej dein.",
 "addr_ask_en": " Your address looks incomplete - please also send the full address (house no., area, pincode).",
 "nudge": {
  "hi": "Namaste {name}! \U0001F64F Aapka order #{oid} (\u20b9{value}) ready hai. Abhi online pay karein toh *\u20b9{disc} off* - sirf \u20b9{final}! \U0001F381\nPay: {link}\nCOD hi chahiye toh *COD* likhein. (Offer 24 ghante tak)",
  "en": "Hi {name}! \U0001F64F Your order #{oid} (\u20b9{value}) is ready. Pay online now and get *\u20b9{disc} off* - just \u20b9{final}! \U0001F381\nPay: {link}\nPrefer cash on delivery? Reply *COD*. (Offer valid 24 hours)"},
 "reminder_confirm": {
  "hi": "Reminder: order #{oid} abhi bhi confirm nahi hua. Bhejne ke liye *YES*, cancel ke liye *NO* likhein.",
  "en": "Reminder: order #{oid} is still waiting for your confirmation. Reply *YES* to ship or *NO* to cancel."},
 "reminder_nudge": {
  "hi": "\u20b9{disc} off wala offer aaj khatam ho raha hai! Order #{oid}: {link}. COD ke liye *COD* likhein.",
  "en": "Your \u20b9{disc} discount ends today! Order #{oid}: {link}. Reply *COD* for cash on delivery."},
 "shipped_cod": {"hi": "Dhanyavaad! \U0001F389 Order #{oid} ship ho raha hai. Delivery par \u20b9{value} COD dein.",
                 "en": "Thank you! \U0001F389 Order #{oid} is on its way. Please keep \u20b9{value} ready for delivery."},
 "shipped_prepaid": {"hi": "Payment mil gaya, shukriya! \U0001F389 Order #{oid} ship ho raha hai.",
                     "en": "Payment received, thank you! \U0001F389 Order #{oid} is on its way."},
 "cancelled": {"hi": "Theek hai, order #{oid} cancel kar diya gaya hai. Jab chahein dobara order karein! \U0001F64F",
               "en": "No problem - order #{oid} has been cancelled. Come back anytime! \U0001F64F"},
 "cancelled_silence": {"hi": "Aapka jawab nahi mila, isliye order #{oid} cancel ho gaya. Order karna ho toh bas yahi reply karein, hum dobara bana denge.",
                       "en": "We didn't hear back, so order #{oid} was cancelled. Just reply here if you still want it and we'll recreate it."},
 "unclear": {"hi": "Maaf kijiye, samajh nahi aaya \U0001F64F Kripya *YES* ya *NO* likhein.",
             "en": "Sorry, I didn't catch that \U0001F64F Please reply *YES* or *NO*."},
 "unclear_nudge": {"hi": "Maaf kijiye, samajh nahi aaya. Online pay ke liye link use karein, ya *COD* likhein.",
                   "en": "Sorry, I didn't catch that. Use the link to pay online, or reply *COD*."},
 "call": {"hi": "Hamari team aapko jald call karegi \U0001F4DE taaki order #{oid} confirm ho sake.",
          "en": "Our team will call you shortly \U0001F4DE to confirm order #{oid}."},
}
DONE = {"SHIP_COD", "SHIP_PREPAID", "SHIP", "CANCELLED", "CALL_QUEUE"}

@dataclass
class Conversation:
    order: dict            # order_id, customer_name, items, order_value, state, address, ...
    kind: str              # "CONFIRM" or "NUDGE_PREPAID"
    discount: float = 0.0
    first_time: bool = False
    lang: str = "hi"
    now: datetime = field(default_factory=lambda: datetime(2026, 10, 31, 12, 0))
    status: str = "AWAITING_REPLY"
    unclear: int = 0
    log: list = field(default_factory=list)       # [(time, who, text)]
    reminders: int = 0
    started: datetime = None
    junk_address: bool = False

    def _fmt(self, key, **kw):
        o = self.order
        d = dict(name=str(o["customer_name"]).split()[0].title(), oid=o["order_id"], items=str(o.get("items", "")).replace("|", ", "),
                 value=int(o["order_value"]), brand="our store", disc=int(self.discount),
                 final=int(o["order_value"] - self.discount), link=f"https://pay.example.com/{o['order_id']}", addr="")
        d.update(kw)
        tpl = T[key][self.lang] if isinstance(T[key], dict) else T[key]
        return tpl.format(**d)

    def _say(self, text): self.log.append((self.now.strftime("%d %b %H:%M"), "bot", text))

    def start(self):
        # never message at night: wait until 09:00
        if self.now.hour >= 21 or self.now.hour < 9:
            nxt = self.now.replace(hour=9, minute=0) + (timedelta(days=1) if self.now.hour >= 21 else timedelta())
            self.log.append((self.now.strftime("%d %b %H:%M"), "system", f"night-time: message queued for {nxt:%d %b %H:%M}"))
            self.now = nxt
        self.started = self.now
        if self.kind == "CONFIRM":
            addr = T["addr_ask_hi" if self.lang == "hi" else "addr_ask_en"] if self.junk_address else ""
            self._say(self._fmt("confirm", addr=addr))
        else:
            self._say(self._fmt("nudge"))
        return self

    # ---- customer reply -------------------------------------------------------------------
    def reply(self, text, use_llm=True):
        if self.status in DONE:
            self.log.append((self.now.strftime("%d %b %H:%M"), "customer", text))
            self._say("(conversation closed - handed to the team if the customer still wants the order)")
            return self
        self.log.append((self.now.strftime("%d %b %H:%M"), "customer", text))
        intent = llm.classify_reply(text, use_llm)["intent"]
        if self.kind == "CONFIRM":
            if intent == "yes": self._finish("SHIP", "shipped_cod")
            elif intent == "no": self._finish("CANCELLED", "cancelled")
            elif intent == "change_address":
                self._say(self._fmt("call")); self.status = "CALL_QUEUE"
            else: self._unclear("unclear")
        else:  # NUDGE
            if intent == "paid": self._finish("SHIP_PREPAID", "shipped_prepaid")
            elif intent in ("cod", "no", "yes"): self._finish("SHIP_COD", "shipped_cod")
            elif intent == "change_address": self._say(self._fmt("call")); self.status = "CALL_QUEUE"
            else: self._unclear("unclear_nudge")
        return self

    def pay(self):
        """Mock payment-gateway webhook: customer paid via the link."""
        self.log.append((self.now.strftime("%d %b %H:%M"), "system", "payment webhook: PAID"))
        if self.status not in DONE and self.kind == "NUDGE_PREPAID":
            self._finish("SHIP_PREPAID", "shipped_prepaid")
        return self

    def _unclear(self, key):
        self.unclear += 1
        if self.unclear == 1:
            self._say(self._fmt(key))
        elif self.kind == "CONFIRM":      # second miss: a human decides, bot stops guessing
            self._say(self._fmt("call")); self.status = "CALL_QUEUE"
        else:                             # nudge: low risk anyway, ship as COD
            self._finish("SHIP_COD", "shipped_cod")

    def _finish(self, status, msg):
        self.status = status; self._say(self._fmt(msg))

    # ---- time passes ---------------------------------------------------------------------
    def advance(self, hours):
        """Move the clock forward; fire reminders and the 24h deadline."""
        end = self.now + timedelta(hours=hours)
        while self.status not in DONE:
            elapsed = (self.now - self.started).total_seconds() / 3600
            events = [(4, "r1"), (20, "r2"), (24, "end")]
            nxt = next(((h, e) for h, e in events if h > elapsed + 1e-9 and self.started + timedelta(hours=h) <= end), None)
            if not nxt: break
            h, e = nxt
            self.now = self.started + timedelta(hours=h)
            if e == "r1" and self.kind == "CONFIRM" or e == "r2" and self.kind == "NUDGE_PREPAID":
                if 9 <= self.now.hour < 21:
                    self._say(self._fmt("reminder_confirm" if self.kind == "CONFIRM" else "reminder_nudge"))
                else:
                    self.log.append((self.now.strftime("%d %b %H:%M"), "system", "reminder skipped: night-time"))
            elif e == "end":
                if self.kind == "NUDGE_PREPAID":
                    self._finish("SHIP_COD", "shipped_cod")
                    self.log.append((self.now.strftime("%d %b %H:%M"), "system", "no reply in 24h on a low-risk order: ship as COD"))
                elif self.first_time:
                    self.log.append((self.now.strftime("%d %b %H:%M"), "system", "no reply in 24h, FIRST ORDER: one human call before any cancellation"))
                    self._say(self._fmt("call")); self.status = "CALL_QUEUE"
                else:
                    self._finish("CANCELLED", "cancelled_silence")
                    self.log.append((self.now.strftime("%d %b %H:%M"), "system", "no reply in 24h: auto-cancelled"))
        self.now = end if self.status not in DONE else self.now
        return self

class MockWhatsApp:
    """In-memory stand-in for the WhatsApp Business API."""
    def __init__(self): self.conv = {}
    def open(self, order, decision, now=None, lang=None, junk=False):
        kind = decision.action
        c = Conversation(order=order, kind=kind, discount=decision.discount, first_time=order.get("customer_prior_orders", 0) == 0,
                         lang=lang or language(order.get("state", "")), junk_address=junk)
        if now: c.now = now
        self.conv[order["order_id"]] = c.start()
        return c
