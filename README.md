# RTO Guard

Decides what to do with every COD order *before* it ships: **Ship as-is / Nudge to prepaid / Ship after WhatsApp confirmation / Hold-cancel**, with a plain-English reason and a Rs impact estimate. Built for the D2C haircare take-home.

## Run it (about 5 minutes)

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/train.py        # trains the risk model, prints the out-of-time accuracy check
python scripts/backtest.py     # replays September: bucket sizes, real RTO rates, Rs impact vs Ops-style cancelling
python -m rtoguard.app         # http://localhost:5000  (dashboard)   http://localhost:5000/chat  (WhatsApp simulator)
pytest -q                      # 15 tests
```
No server? Open `output/dashboard.html` (static copy). Optional: `export ANTHROPIC_API_KEY=...` turns on the LLM judge; without it a rule-based fallback runs and every decision records `judge_source`.

| What | Where |
|---|---|
| Decision engine (Part 1) | `rtoguard/engine.py`, `features.py`, `model.py`, `llm.py` |
| **Thresholds, discounts, costs, assumptions (edit, no code)** | `config/rules.yaml` |
| WhatsApp flows + mock API + chat simulator (Part 2) | `rtoguard/whatsapp.py`, `/chat` |
| Prepaid discount maths | `python scripts/discount_math.py` |
| Dashboard (Part 3) | `rtoguard/dashboard.py`, `/`, `output/dashboard.html` (`?day=2026-09-15` to pick a day) |
| Memo, decision log, AI usage log (Parts 4 + deliverables) | `docs/` |
| Numbers quoted in the memo | `python scripts/findings.py`, `scripts/sensitivity.py` |

Try the API: `curl -X POST localhost:5000/api/decide -H 'content-type: application/json' -d '{"customer_name":"asdf","address":"xyz","phone":"9805943782","city":"Bareilly","state":"Uttar Pradesh","order_value":799}'`

## Where the LLM is used, and where it isn't
| LLM (judging messy human text) | Plain code (has a right answer) |
|---|---|
| Is the address complete / real? (incl. Hinglish) | Phone format, risk score, all Rs maths |
| Is the name fake ("asdf", "Test Order")? | Thresholds -> the 4 actions |
| What does a free-text WhatsApp reply mean? | YES / NO / haan / nahi keywords, timers, night-time rule |

Cheap rules run first; the LLM only sees addresses the rules can't settle, and answers are cached. The LLM never picks the action.

## How a decision is made
1. Clean data -> features (code + LLM judge) -> logistic-regression **risk** (chance of RTO).
2. Guardrails: invalid phone, unusable address + fake name, or 2+ earlier refusals -> Hold. First orders are never cancelled on score alone.
3. Thresholds in `rules.yaml`: <20% ship, 20-40% prepaid offer, 40-68% confirm, 68%+ hold.
4. Impact in Rs vs "ship everything as COD": RTO costs avoided + recovered sales - margin lost on genuine orders - discounts/messages.

## Caveats
- ~2,000 orders is small. Out-of-time AUC 0.74 (train Apr-Aug, test Sep).
- Customer-behaviour assumptions (reply and prepaid take-up, repeat value) are **not in the data**; they live in `rules.yaml` and are stress-tested in `scripts/sensitivity.py`. Measure them first.
- All reported numbers use the rule-based fallback judge; the Claude-API path is implemented but untested on this dataset.
- Mock WhatsApp/payment only; dashboard "yesterday" = the last day in the CSV (30 Sep), scored by a model trained on Apr-Aug only.







<img width="1327" height="884" alt="image" src="https://github.com/user-attachments/assets/34ea723f-be2c-4cb2-b964-7ad71fefbc2d" />

