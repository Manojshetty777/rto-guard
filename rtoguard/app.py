"""Flask app: / dashboard, /chat WhatsApp simulator, /api/decide JSON endpoint."""
import os
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from . import data, dashboard
from .engine import Engine
from .whatsapp import MockWhatsApp

app = Flask(__name__)
DF, _ = data.load_orders()
MODEL = "output/model_backtest.json" if os.path.exists("output/model_backtest.json") else "config/model.json"
ENGINE = Engine(model_path=MODEL)   # demo model is trained on Apr-Aug only, so September dates are out-of-sample
WA = MockWhatsApp()

@app.get("/")
def home():
    return dashboard.render(Engine(model_path=MODEL), DF, request.args.get("day"))   # reload rules.yaml on every refresh

@app.post("/api/decide")
def decide():
    o = request.get_json(force=True)
    o.setdefault("order_id", "NEW1"); o.setdefault("customer_prior_orders", 0); o.setdefault("customer_prior_rto", 0)
    o.setdefault("utm_source", "direct"); o.setdefault("pincode", None); o.setdefault("city", ""); o.setdefault("state", "")
    o.setdefault("items", ""); o.setdefault("customer_name", "Customer"); o.setdefault("phone", "")
    return jsonify(Engine(model_path=MODEL).decide(o).to_dict())

CHAT = """<!doctype html><meta name=viewport content="width=device-width,initial-scale=1"><title>WhatsApp simulator</title>
<style>body{font:15px system-ui;max-width:640px;margin:0 auto;padding:16px;background:#ece5dd}.b{background:#fff;border-radius:10px;padding:8px 12px;margin:6px 40px 6px 0;white-space:pre-wrap}
.c{background:#dcf8c6;margin:6px 0 6px 40px;border-radius:10px;padding:8px 12px}.s{color:#777;font-size:12px;text-align:center;margin:6px}.t{font-size:11px;color:#777}
button,select,input{font:inherit;padding:6px 10px;margin:2px;border-radius:8px;border:1px solid #bbb}.bar{position:sticky;bottom:0;background:#ece5dd;padding:8px 0}</style>
<h3>WhatsApp confirmation simulator</h3>
<form method=get>Order: <select name=oid onchange=this.form.submit()>{% for o in opts %}<option value="{{o[0]}}" {{'selected' if o[0]==oid}}>{{o[0]}} - {{o[1]}} (risk {{o[2]}})</option>{% endfor %}</select></form>
{% if c %}<p><b>{{c.kind}}</b> - status: <b>{{c.status}}</b> - language: {{c.lang}}</p>
{% for t,who,txt in c.log %}{% if who=='system' %}<div class=s>{{t}} - {{txt}}</div>{% else %}<div class="{{'b' if who=='bot' else 'c'}}">{{txt}}<div class=t>{{t}}</div></div>{% endif %}{% endfor %}
<div class=bar><form method=post><input type=hidden name=oid value="{{oid}}"><input name=text placeholder="type a customer reply (yes / nahi / haan bhej do / random)" size=36 autofocus>
<button name=act value=reply>Send</button><button name=act value=pay>Customer pays</button><button name=act value=h4>+4h</button><button name=act value=h24>+24h</button><button name=act value=reset>Reset</button></form></div>{% endif %}"""

@app.route("/chat", methods=["GET", "POST"])
def chat():
    pend = [(d, r) for d, r in zip(ENGINE.decide_frame(DF.tail(300).reset_index(drop=True)), DF.tail(300).itertuples()) if d.action in ("CONFIRM", "NUDGE_PREPAID")]
    pend.sort(key=lambda t: t[0].order_id)
    oid = request.values.get("oid") or (pend[0][0].order_id if pend else None)
    pick = {d.order_id: (d, r) for d, r in pend}
    if oid in pick and oid not in WA.conv:
        d, r = pick[oid]
        o = {k: getattr(r, k) for k in ("order_id", "customer_name", "items", "order_value", "state", "customer_prior_orders", "address")}
        WA.open(o, d, now=datetime(2026, 10, 31, 11, 0), junk=d.rule == "x" or "unusable" in d.reason)
    c = WA.conv.get(oid)
    if request.method == "POST" and c:
        act = request.form.get("act")
        if act == "reply" and request.form.get("text"): c.reply(request.form["text"])
        elif act == "pay": c.pay()
        elif act == "h4": c.advance(4)
        elif act == "h24": c.advance(24)
        elif act == "reset": WA.conv.pop(oid, None); return chat()
    opts = [(d.order_id, d.action, f"{d.risk:.0%}") for d, _ in pend[:60]]
    return render_template_string(CHAT, c=c, oid=oid, opts=opts)

if __name__ == "__main__":
    app.run(port=5000, debug=False)
