# Decision log

Format: **decision**, alternatives considered, why. Most important first.

## Framing
- **Judge everything in rupees, per order.** One RTO costs Rs169.4 (65 + 65 + 25 + 8% x Rs180). A delivered order earns 62% of its value minus Rs90 shipping/packing (Rs312 on a Rs649 order). *Alternative:* optimise "RTO rate". *Rejected:* cancelling a 50%-risk order lowers the rate but loses money, because Rs312 x 50% > Rs169 x 50%. The brief asked for Rs reasoning, and this is what it shows.
- **Treated the Rs65+Rs65+Rs25 as sunk once shipped, and the 62% margin as before shipping/packing.** The brief is ambiguous. *Alternative:* margin already net of shipping. That would make every order Rs90 more profitable and cancelling even less attractive, so my assumption is the conservative one for "don't cancel".
- **Ad spend (Rs300) is sunk, so it is not a reason to ship.** What Marketing is right about is future value, so I added a configurable "repeat value of a first order" (Rs100, an assumption, flagged to measure).

## Data
- Dropped 30 exact duplicate rows, 1 IN_TRANSIT order (outcome unknown), 3 Rs0 orders; normalised "Rto"/"delivered". Kept missing city/pincode (12 / 4 rows) as a feature, not a deletion. Logged in `data.load_orders`.
- File AOV is Rs921, not Rs649, and 2,000 orders over 6 months is a sample, not 3,000/month. I use per-order values from the file and scale to ~1,650 COD orders/month only for the memo headline.

## Risk model
- **Logistic regression scorecard, not gradient boosting.** *Alternative:* XGBoost/random forest. *Why not:* ~2,000 rows, ops must understand the reasons, and every coefficient maps to a plain-English reason. Out-of-time AUC 0.74 (train Apr-Aug, test Sep); predicted vs actual risk matches by band.
- **City, not pincode.** 1,066 pincodes for ~2,000 orders, median 1 order, none with 10+. A pincode ban (Ops' idea) would be fitted on noise. City rate is shrunk toward the average (strength 20) so a 3-order city cannot read as 100%.
- **Out-of-fold city encoding** for training rows so a city's own outcome doesn't leak into its feature.
- **Excluded courier, hour of day, item count:** differences were small/inconsistent. Courier looks like a lever (Xpressbees 31% vs Delhivery 26%) but needs a controlled test, listed as next step.
- Kept `meta_ads` (31% vs 27%); it is a weak signal and can be removed in `FEATURES`.

## Where the LLM is used (and not)
- **LLM:** address quality (complete / landmark-only / partial / junk, reads Hinglish), fake-name check, free-text WhatsApp reply intent. These need language judgement.
- **Plain code:** phone validity, risk maths, Rs maths, thresholds, decisions, keyword replies (YES/NO/haan/nahi). A regex is faster, free and predictable.
- **Rules before LLM:** obvious junk ("xyz", ".", under 8 chars) and clearly structured addresses are decided by regex. The LLM sees only the ambiguous ~25% of addresses, with results cached. *Alternative:* LLM for every field. *Rejected:* cost, latency, and nondeterminism on things that have right answers.
- **LLM never decides the action.** It produces features; thresholds decide. If the API is down or no key is set, a rule-based fallback keeps orders flowing and the decision records `judge_source`.
- **Honest limit:** I ran the full pipeline with the rule-based fallback (no API key in my build environment), so all numbers in the memo come from the fallback judge. LLM mode is implemented but its accuracy is untested on this data (see memo risk section).

## Decision rules
- **Four buckets from risk thresholds in `config/rules.yaml`** (20% / 40% / 68%), derived from break-even maths (see `scripts/discount_math.py` and the EV table in the memo), not from tuning on September. Nudge beats shipping from ~15% risk; WhatsApp confirmation beats the nudge from ~30-40%; cancelling beats shipping only above ~65-74%. A grid search (`scripts/sensitivity.py`) shows net impact is flat (about Rs5-6.5k per 329 orders) for any sensible thresholds, so I kept the principled values instead of overfitting 329 orders.
- **Confirmation beats cancellation almost everywhere** under my assumptions, so "Hold / cancel" is reserved for orders we cannot confirm or should not ship: invalid phone, junk address + fake name, 2+ earlier refusals, or risk >= 68%.
- **First orders are never cancelled on score alone** (hold only if risk >= 80%, or the phone is unreachable). They get WhatsApp confirmation, plus one human call before any silence-cancellation. This is Marketing's guardrail; only 4 of 241 first orders in September were held.
- **Hold-share alarm (8%)** on the dashboard as the Ops/Marketing safety valve.

## WhatsApp flow
- Hinglish by default, English for Karnataka/TN/Telangana or English addresses. Never message 21:00-09:00 (queue to 09:00). Reminder at 4h (confirm) or 20h (nudge). 24h deadline.
- Silence on CONFIRM: cancel (repeat customers) or human call (first orders). Silence on NUDGE: ship COD (it was low risk). Unclear reply: one re-ask, then a human (confirm) or ship COD (nudge). Address-change replies go to a human.
- **Prepaid discount = half the break-even,** min Rs30, max 10% of order, rounded to Rs10. Break-even accounts for discount leakage (genuine customers take it too). Full maths: `scripts/discount_math.py`.

## Behaviour assumptions (not in the data, flagged in rules.yaml)
- 80% of genuine / 30% of would-be-refusing customers answer YES; half of those then take delivery; 30% / 15% accept a prepaid offer; Rs100 repeat value. Chosen to be plausible and slightly cautious. `scripts/sensitivity.py` stress-tests them: net stays about Rs0.7k even when responsiveness is 30% lower, and -Rs1.2k in a worst case where risky customers never convert. **First thing to measure live.**

## Things I left out on purpose
- Real WhatsApp/Shopify/payment integrations (mock API per the brief), auth on the dashboard, a database (CSV replay is enough for the take-home), model retraining automation.
