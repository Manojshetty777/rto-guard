"""Shows the prepaid-discount maths. Usage: python scripts/discount_math.py"""
import sys; sys.path.insert(0, ".")
from rtoguard.economics import Econ, load_rules
E = Econ(load_rules()); q = E.c["prepaid_rto_rate"]; a = E.a
print(f"One RTO costs Rs{E.rto_loss:.1f} = 65 + 65 + 25 + {E.c['damaged_return_share']:.0%} x Rs180 damaged stock")
print(f"Prepaid RTO is {q:.0%}. Assumed take-up of the offer: genuine customers {a['nudge_accept_genuine']:.0%}, would-be refusers {a['nudge_accept_risky']:.0%}")
print("\nBreak-even discount d* = [ k_r * p * (1-q) * (margin + RTO loss) - msg cost ] / [ k_g * (1-p) + k_r * p * (1-q) ]")
print("(gain from turning a would-be refuser into a paid delivery must cover the discount given to EVERY customer who accepts, genuine ones too)\n")
print(f"{'order':>6} {'risk':>5} {'margin':>7} {'break-even':>10} {'we offer':>9} {'% of order':>10}")
for V in (449, 649, 918, 1500):
    for p in (0.20, 0.30, 0.40):
        print(f"{V:>6} {p:>5.0%} {E.margin(V):>7.0f} {E.prepaid_breakeven(p, V):>10.0f} {E.discount(p, V):>9.0f} {E.discount(p, V)/V:>10.1%}")
print("\nWe offer half of break-even (config: share_of_break_even), at least Rs30, at most 10% of the order.")
