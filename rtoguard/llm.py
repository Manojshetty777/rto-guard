"""Where the LLM is used - and where it is NOT.

LLM (judgement over messy human text):
  * Is this address complete / real / deliverable? (reads Hinglish, landmarks, typos)
  * Does this customer name look fake ("asdf", "Test Order")?
Plain code (anything with a right answer): phone format, pincode<->state, money, risk maths, thresholds.

Cheap rules run first. The LLM is called ONLY for addresses the rules cannot settle, and every
answer is cached on disk, so a 2,000 order backtest costs a few hundred small calls, not 2,000.

No ANTHROPIC_API_KEY? The same interface falls back to a rule-based judge (source="heuristic")
so the whole project runs offline. Decisions record which source judged the order.
"""
import json, os, re, hashlib
from pathlib import Path

CACHE_PATH = Path(os.environ.get("RTOGUARD_CACHE", ".cache/llm_cache.json"))
MODEL = os.environ.get("RTOGUARD_LLM_MODEL", "claude-haiku-4-5")
JUNK = {".", "xyz", "home", "call me", "near station", "na", "n/a", "abc", "test", "asdf", "none"}
FAKE_NAME = re.compile(r"\b(test|asdf|qwerty|demo|fake|xyz|abc|dummy)\b|^[a-z]{1,2}$", re.I)
STRUCT = re.compile(r"(\d+\s*[/-]?\s*\d*)", re.I)  # has a house/flat/gali number
LOCALITY = re.compile(r"(nagar|society|sector|colony|marg|road|street|apartment|layout|enclave|park|niwas|gali|chowk)", re.I)
LANDMARK_ONLY = re.compile(r"(ke paas|ke saamne|ke peeche|se left|se right|ph krke|call krke|near )", re.I)

PROMPT = """You check Indian delivery details for a COD (cash on delivery) courier.
Addresses may be English, Hinglish (Hindi in Roman script) or mixed.
Return ONLY JSON: {{"address_quality": "complete|landmark_only|partial|junk",
 "fake_name": true|false, "language": "english|hinglish|other", "reason": "<=15 words"}}
complete = a courier could find it (house/flat no. + locality). landmark_only = only "near X / X ke paas"
directions. partial = some detail but missing house or locality. junk = unusable ("xyz", ".", "home").
Address: {address!r}  City: {city!r}  State: {state!r}  Customer name: {name!r}"""

def _load():
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return {}

_cache = _load()

def _save():
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(_cache, indent=1))

def rule_judge(address, name=""):
    """Deterministic judge. Returns (verdict_or_None, result). None = ambiguous, ask the LLM."""
    a = (address or "").strip()
    low = a.lower()
    fake = bool(FAKE_NAME.search(name or ""))
    if len(a) < 8 or low in JUNK or low.isalpha() and " " not in low:
        return "junk", dict(address_quality="junk", fake_name=fake, language="other", reason="too short / placeholder text")
    has_num = bool(STRUCT.search(a))
    has_loc = bool(LOCALITY.search(a))
    if has_num and has_loc and not re.search(r"ke paas|ke saamne|ke peeche|ph krke", low):
        return "complete", dict(address_quality="complete", fake_name=fake, language="english", reason="house number + locality present")
    return None, dict(address_quality="landmark_only" if LANDMARK_ONLY.search(a) else "partial",
                      fake_name=fake, language="hinglish" if re.search(r"ke |ghar|wala|krke|gali", low) else "english",
                      reason="no house number/locality; direction or landmark only")

def judge(address, city="", state="", name="", use_llm=True):
    verdict, fallback = rule_judge(address, name)
    if verdict is not None:
        return {**fallback, "source": "rules"}
    key = hashlib.md5(f"{address}|{city}|{state}|{name}".encode()).hexdigest()
    if key in _cache:
        return _cache[key]
    key_set = os.environ.get("ANTHROPIC_API_KEY")
    if use_llm and key_set:
        try:
            import anthropic
            client = anthropic.Anthropic()
            msg = client.messages.create(model=MODEL, max_tokens=150, messages=[
                {"role": "user", "content": PROMPT.format(address=address, city=city, state=state, name=name)}])
            txt = msg.content[0].text
            res = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
            res["source"] = "llm"
            res["fake_name"] = bool(res.get("fake_name")) or fallback["fake_name"]
            _cache[key] = res; _save()
            return res
        except Exception as e:  # never let an LLM outage block an order
            fallback["reason"] += f" (LLM unavailable: {type(e).__name__})"
    return {**fallback, "source": "heuristic"}

YES = {"yes", "y", "yep", "haan", "han", "haa", "ha", "ok", "okay", "confirm", "confirmed", "theek", "thik", "ji", "yes please", "ok bhej do", "bhej do", "kar do", "\U0001F44D"}
NO = {"no", "n", "nahi", "nahin", "nhi", "nope", "cancel", "cancel kar do", "mat bhejo", "nahi chahiye", "\U0001F44E"}
COD = {"cod", "cash", "cash on delivery", "cod hi", "cod chahiye"}
PAID = {"paid", "done", "payment done", "pay kar diya", "ho gaya"}
REPLY_PROMPT = """A customer replied to a COD confirmation / prepaid offer on WhatsApp (English or Hinglish).
Classify the reply. Return ONLY JSON: {{"intent": "yes|no|cod|change_address|question|unclear"}}
Reply: {text!r}"""

YES_TOK = {"yes", "y", "yep", "haan", "han", "haa", "ha", "ok", "okay", "confirm", "confirmed", "theek", "thik", "ji", "\U0001F44D"}
NO_TOK = {"no", "n", "nope", "nahi", "nahin", "nhi", "cancel", "\U0001F44E"}

def classify_reply(text, use_llm=True):
    """Short replies are read by keywords (free, instant, predictable). Anything longer or mixed
    ("no, I want to change the address") is free text -> LLM, because a bare keyword would misread it."""
    t = re.sub(r"[^\w\s\U0001F44D\U0001F44E]", "", (text or "").lower()).strip()
    tok = set(t.split())
    if t in COD or tok == {"cod"}: return {"intent": "cod", "source": "keywords"}
    if t in PAID: return {"intent": "paid", "source": "keywords"}
    if len(t.split()) <= 4:
        y, n = bool(tok & YES_TOK) or t in YES, bool(tok & NO_TOK) or t in NO
        if y and not n: return {"intent": "yes", "source": "keywords"}
        if n and not y: return {"intent": "no", "source": "keywords"}
    if os.environ.get("ANTHROPIC_API_KEY") and use_llm:
        try:
            import anthropic
            msg = anthropic.Anthropic().messages.create(model=MODEL, max_tokens=40, messages=[
                {"role": "user", "content": REPLY_PROMPT.format(text=text)}])
            r = json.loads(re.search(r"\{.*\}", msg.content[0].text, re.S).group(0))
            return {"intent": r.get("intent", "unclear"), "source": "llm"}
        except Exception:
            pass
    if re.search(r"address|pata|pin ?code|lane|flat|house|ghar", t or ""):
        return {"intent": "change_address", "source": "keywords"}
    return {"intent": "unclear", "source": "keywords"}
