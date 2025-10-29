# nlp_extraction.py
from flask import Blueprint, request, jsonify
import spacy
from spacy.matcher import Matcher

nlp_bp = Blueprint("nlp", __name__, url_prefix="/api/nlp")

NLP = None
MATCHER = None

# ------------------ Helpers ------------------ #
def _full_person(tok, doc):
    """Return full PERSON name (e.g., 'Albert Einstein')."""
    for ent in doc.ents:
        if ent.label_ == "PERSON" and ent.start <= tok.i < ent.end:
            return ent.text
    return tok.text

def _full_np(head):
    """Return complete noun phrase for the given head token."""
    if head is None:
        return ""
    words = [t.text for t in head.subtree]
    return " ".join(words).replace(" ,", ",").replace(" .", ".").strip()

# ------------------ Safe init ------------------ #
def _safe_init():
    """Initialize spaCy + patterns once. Return (ok, error_message)."""
    global NLP, MATCHER
    if NLP is not None and MATCHER is not None:
        return True, None
    try:
        NLP = spacy.load("en_core_web_sm")
        MATCHER = Matcher(NLP.vocab)

        # PERSON discovered|developed|invented NOUN/PROPN+
        MATCHER.add("DISCOVERED", [[
            {"ENT_TYPE": "PERSON"},
            {"LEMMA": {"IN": ["discover", "develop", "invent"]}},
            {"POS": {"IN": ["NOUN", "PROPN"]}, "OP": "+"}
        ]])

        # PERSON is/was (a/an)? NOUN/PROPN+  -> is_a
        MATCHER.add("IS_A", [[
            {"ENT_TYPE": "PERSON"},
            {"LEMMA": "be"},
            {"LOWER": {"IN": ["a", "an"]}, "OP": "?"},
            {"POS": {"IN": ["NOUN", "PROPN"]}, "OP": "+"}
        ]])

        # PERSON was born in GPE/LOC -> born_in
        MATCHER.add("BORN_IN", [[
            {"ENT_TYPE": "PERSON"},
            {"LOWER": "was"},
            {"LOWER": "born"},
            {"LOWER": "in"},
            {"ENT_TYPE": {"IN": ["GPE", "LOC"]}}
        ]])

        # PERSON is the president of GPE -> is_president_of
        # (Allow multi-token GPE and capture the full entity text.)
        MATCHER.add("PRES_OF", [[
            {"ENT_TYPE": "PERSON"},
            {"LEMMA": "be", "OP": "?"},
            {"LOWER": {"IN": ["the", "a"]}, "OP": "?"},
            {"LOWER": {"IN": ["president", "prime", "pm"]}, "OP": "+"},
            {"LOWER": "of"},
            {"ENT_TYPE": {"IN": ["GPE", "LOC"]}, "OP": "+"}
        ]])

        # GPE has president PERSON -> has_president
        MATCHER.add("HAS_PRES", [[
            {"ENT_TYPE": {"IN": ["GPE", "LOC"]}},
            {"LEMMA": "have"},
            {"LOWER": {"IN": ["a", "the"]}, "OP": "?"},
            {"LOWER": "president"},
            {"ENT_TYPE": "PERSON", "OP": "?"}
        ]])

        # GPE has prime minister PERSON -> has_prime_minister
        MATCHER.add("HAS_PM", [[
            {"ENT_TYPE": {"IN": ["GPE", "LOC"]}},
            {"LEMMA": "have"},
            {"LOWER": {"IN": ["a", "the"]}, "OP": "?"},
            {"LOWER": "prime"},
            {"LOWER": {"IN": ["minister", "ministers"]}},
            {"ENT_TYPE": "PERSON", "OP": "?"}
        ]])

        # PERSON won award -> won_award
        MATCHER.add("WON", [[
            {"ENT_TYPE": "PERSON"},
            {"LEMMA": "win"},
            {"POS": "DET", "OP": "?"},
            {"POS": {"IN": ["PROPN", "NOUN"]}, "OP": "+"}
        ]])

        return True, None
    except Exception as e:
        return False, str(e)

# ------------------ Triple extraction ------------------ #
def _extract_triples(text: str):
    ok, err = _safe_init()
    if not ok:
        raise RuntimeError(f"spaCy init failed: {err}")

    doc = NLP(text)
    triples = []

    for match_id, start, end in MATCHER(doc):
        label = NLP.vocab.strings[match_id]
        span = doc[start:end]

        if label == "DISCOVERED":
            subj = _full_person(span[0], doc)
            verb = span[1].lemma_
            rel = {"discover": "discovered", "develop": "developed", "invent": "invented"}.get(verb, "discovered")
            obj_head = next((t for t in reversed(span) if t.pos_ in {"NOUN", "PROPN"}), None)
            obj = _full_np(obj_head) if obj_head else span[-1].text
            triples.append((subj, rel, obj))

        elif label == "IS_A":
            subj = _full_person(span[0], doc)
            obj_head = next((t for t in reversed(span) if t.pos_ in {"NOUN", "PROPN"}), None)
            obj = _full_np(obj_head)
            triples.append((subj, "is_a", obj))

        elif label == "BORN_IN":
            subj = _full_person(span[0], doc)
            obj = span[-1].text
            triples.append((subj, "born_in", obj))

        elif label == "PRES_OF":
            subj = _full_person(span[0], doc)
            # Prefer the full GPE/LOC entity text inside the span
            obj_ent = next((ent for ent in span.ents if ent.label_ in ("GPE", "LOC")), None)
            obj = obj_ent.text if obj_ent else span[-1].text
            triples.append((subj, "is_president_of", obj))

        elif label == "HAS_PRES":
            country = span[0].text
            person_tok = next((t for t in span if t.ent_type_ == "PERSON"), None)
            if person_tok:
                person = _full_person(person_tok, doc)
                triples.append((country, "has_president", person))

        elif label == "HAS_PM":
            country = span[0].text
            person_tok = next((t for t in span if t.ent_type_ == "PERSON"), None)
            if person_tok:
                person = _full_person(person_tok, doc)
                triples.append((country, "has_prime_minister", person))

        elif label == "WON":
            subj = _full_person(span[0], doc)
            obj_head = next((t for t in reversed(span) if t.pos_ in {"NOUN", "PROPN"}), None)
            obj = _full_np(obj_head)
            triples.append((subj, "won_award", obj))

    # fallback SVO extraction
    for token in doc:
        if token.pos_ == "VERB" and token.lemma_ in {"discover", "develop", "invent", "create"}:
            subj_tok = next((ch for ch in token.children if ch.dep_ in {"nsubj", "nsubjpass"} and ch.ent_type_ == "PERSON"), None)
            obj_tok = next((ch for ch in token.children if ch.dep_ in {"dobj", "attr", "oprd"} and ch.pos_ in {"NOUN", "PROPN"}), None)
            if subj_tok and obj_tok:
                rel = {"discover": "discovered", "develop": "developed", "invent": "invented", "create": "created"}[token.lemma_]
                subj = _full_person(subj_tok, doc)
                obj = _full_np(obj_tok)
                triples.append((subj, rel, obj))

    # ---- Post-process: prefer longest object per (subject, relation) ---- #
    best = {}
    for s, r, o in triples:
        key = (s.strip(), r.strip())
        cand = o.strip()
        if not cand:
            continue
        if key not in best or len(cand) > len(best[key]):
            best[key] = cand

    # Build final list (cap to 3)
    out = []
    for (s, r), o in best.items():
        out.append({"subject": s, "relation": r, "object": o})
        if len(out) >= 3:
            break
    return out

# ------------------ Routes ------------------ #
@nlp_bp.route("/health", methods=["GET"])
def health():
    ok, err = _safe_init()
    return jsonify({"ok": ok, "error": err}), (200 if ok else 500)

@nlp_bp.route("/extract", methods=["POST"])
def extract():
    try:
        data = request.get_json(silent=True) or {}
        text = (data.get("text") or "").strip()
        if not text:
            return jsonify({"error": "text is required"}), 400
        triples = _extract_triples(text)
        return jsonify({"triples": triples}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
