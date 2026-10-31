# AI usage log

> **Review before submitting.** The entries below are what happened in my build session; edit them so they match your own experience, and be ready to explain each one in the interview.

## Tools
- **Claude (claude.ai chat, with a code sandbox):** planned the approach, profiled the CSV, wrote the first version of the code, tests, docs and memo draft. I reviewed, ran and challenged the output.
- **Claude API (optional, in the product itself):** address-quality, fake-name and reply-intent judgement via `rtoguard/llm.py`. Not used for numbers or decisions.

## What AI did vs. what I decided
- AI: exploratory analysis, boilerplate (Flask app, dashboard HTML, tests), drafting.
- Me: the framing (judge in Rs, not RTO rate), what to do about the two leaders' positions, which assumptions to flag, which numbers go in the memo, thresholds.

## Where the AI was wrong or weak, and how it was caught
1. **Over-optimistic nudge maths.** The first version of the prepaid nudge assumed every customer who accepted was a would-be refuser who would then reliably take delivery. The September replay then showed a net of about Rs8.1k driven mostly by a "recovered sales" line of Rs9.0k, which looked too good. I traced it: the discount was only charged to would-be refusers, ignoring that genuine customers take the discount too ("leakage"), and acceptance was the same for both groups. Fix: separate acceptance rates (30% genuine, 15% risky), discount cost charged to all acceptors, break-even discount re-derived. Net fell to Rs5.7k, which I trust more.
2. **"Hinglish addresses are riskier" (false headline).** First cut of the data showed landmark/Hinglish-style addresses at 31% RTO versus 23% for structured ones, which suggested penalising them. Splitting by city showed most of the gap is city mix (they cluster in tier-3 cities): 24% vs 19% in ordinary cities, 51% vs 49% in high-RTO cities. So the model keeps a small address-quality term, the memo says Hinglish is not a red flag, and the LLM is there to *understand* addresses, not to punish them.
3. **A silly "hot city" bug.** The findings script flagged '' (4 orders with a blank city, 50% RTO) as a high-RTO city and the first list of "bad cities" included it. Caught by reading the printed list; fixed with a minimum of 20 orders per city.
4. **WhatsApp reply reader too naive.** The first version matched exact phrases, so "haan bhej do" ("yes, send it") was not recognised, and a keyword-in-text shortcut I considered would have read "No, I want to change the address" as a cancellation. A unit test I wrote for the yes/no/random paths failed on the first case, which exposed both. Fix: keywords only for short replies (4 words or fewer, no conflicting yes/no words); longer or mixed text goes to the LLM, or to a human if no LLM is available.
5. **Shell mistake.** The first scaffold command used brace expansion that the shell didn't support and silently created a directory literally named `{rtoguard,config,...}`. Caught from the `cp` error; deleted and recreated.

## Not verified (be honest in the interview)
- The Claude-API path in `llm.py` was never exercised against this dataset in my session (no API key in the sandbox). All reported numbers use the rule-based fallback judge. Before relying on it, run with `ANTHROPIC_API_KEY` set and spot-check ~50 address judgements against the heuristic.
