import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import copy
import pytest
from rtoguard import data, llm, features
from rtoguard.economics import Econ, load_rules
from rtoguard.engine import Engine, SHIP, NUDGE, CONFIRM, HOLD
from rtoguard.whatsapp import Conversation, MockWhatsApp

BASE = dict(order_id="T", customer_name="Priya Sharma", phone="9805943782", address="B-342, Om Society, Station Marg",
            city="Mumbai", state="Maharashtra", pincode=400008, order_value=649, items="Satin Bonnet", customer_prior_orders=2,
            customer_prior_rto=0, utm_source="direct")
def order(**kw): return {**BASE, **kw}

def test_rto_cost_matches_brief():
    assert Econ(load_rules()).rto_loss == pytest.approx(169.4)

def test_cancel_breakeven_is_high():
    e = Econ(load_rules()); m = e.margin(649)
    assert m / (m + e.rto_loss) > 0.6   # cancelling only pays above ~65% risk

def test_discount_bounds():
    e = Econ(load_rules())
    for p in (0.2, 0.4, 0.6):
        d = e.discount(p, 649)
        assert 30 <= d <= 0.10 * 649 + 5

def test_cleaning_removes_dupes_and_bad_rows():
    df, log = data.load_orders("data/orders_sample.csv")
    assert not df.duplicated().any() and set(df.final_status) == {"DELIVERED", "RTO"} and (df.order_value > 0).all()

def test_address_rules_without_llm():
    assert llm.judge("xyz", use_llm=False)["address_quality"] == "junk"
    assert llm.judge("B-342, Om Society, Station Marg", use_llm=False)["address_quality"] == "complete"
    assert llm.judge("ph krke aana, Big Bazaar ke paas", use_llm=False)["address_quality"] == "landmark_only"
    assert llm.rule_judge("x", "asdf")[1]["fake_name"] is True

def test_phone_validation():
    assert features.phone_ok("9805943782") and features.phone_ok("+91 98059 43782")
    assert not features.phone_ok("980594378")

@pytest.fixture(scope="module")
def eng(): return Engine(use_llm=False)

def test_good_repeat_customer_ships(eng):
    d = eng.decide(order()); assert d.action == SHIP and d.reason

def test_junk_and_fake_is_held(eng):
    assert eng.decide(order(customer_name="asdf", address="xyz")).action == HOLD

def test_invalid_phone_held(eng):
    assert eng.decide(order(phone="12345")).action == HOLD

def test_refused_twice_held(eng):
    assert eng.decide(order(customer_prior_rto=2)).action == HOLD

def test_first_order_not_cancelled_on_score_alone(eng):
    d = eng.decide(order(customer_prior_orders=0, city="Gorakhpur", state="Uttar Pradesh", address="gali no 22 ke andar, Masjid ke paas",
                         order_value=2500, utm_source="meta_ads"))
    assert d.action != HOLD and d.action in (CONFIRM, NUDGE)

def test_thresholds_editable_without_code():
    e = Engine(use_llm=False)
    o = order(customer_prior_orders=0, city="Patna", state="Bihar", address="gali no 22 ke andar, Masjid ke paas")
    before = e.decide(o).action
    e.rules["thresholds"].update(ship_below=0.99, confirm_from=0.995, hold_from=0.999)
    assert e.decide(o).action == SHIP and before != SHIP or before == SHIP

# ---- WhatsApp flows ----
def mk(kind, first=True, now=None, disc=60):
    o = dict(order_id="K1", customer_name="Ritu Pillai", items="Satin Bonnet", order_value=798, state="Uttar Pradesh", customer_prior_orders=0 if first else 3)
    class D: pass
    D.action = kind; D.discount = disc
    return MockWhatsApp().open(o, D, now=now)

def test_confirm_yes_no_random_silence():
    assert mk("CONFIRM").reply("haan bhej do").status == "SHIP"
    assert mk("CONFIRM").reply("nahi").status == "CANCELLED"
    c = mk("CONFIRM"); c.reply("blah"); assert c.status == "AWAITING_REPLY"; c.reply("???"); assert c.status == "CALL_QUEUE"
    assert mk("CONFIRM", first=False).advance(25).status == "CANCELLED"
    assert mk("CONFIRM", first=True).advance(25).status == "CALL_QUEUE"   # first orders get a human call, not a cancel

def test_nudge_paths():
    assert mk("NUDGE_PREPAID").pay().status == "SHIP_PREPAID"
    assert mk("NUDGE_PREPAID").reply("COD").status == "SHIP_COD"
    assert mk("NUDGE_PREPAID").advance(25).status == "SHIP_COD"

def test_no_night_messages():
    from datetime import datetime
    c = mk("CONFIRM", now=datetime(2026, 10, 31, 23, 30))
    assert c.started.hour == 9 and c.started.day == 1
