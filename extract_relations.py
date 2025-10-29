# extract_relations.py
# --- CSV & Graph utilities (kept from your file) ---
import pandas as pd
import networkx as nx
from typing import List, Dict, Tuple, Iterable

TRIPLE_COLS = ["entity_1","relation","entity_2","entity_1_type","entity_2_type","start_year","end_year","country","domain","notes"]

def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    for col in TRIPLE_COLS:
        if col not in df.columns:
            df[col] = None
    return df

def df_to_triples(df: pd.DataFrame) -> pd.DataFrame:
    triples = df[["entity_1","relation","entity_2","domain","country","start_year","end_year","entity_1_type","entity_2_type","notes"]].copy()
    triples.rename(columns={
        "entity_1":"subject",
        "entity_2":"object",
        "entity_1_type":"subject_type",
        "entity_2_type":"object_type"
    }, inplace=True)
    triples = triples.dropna(subset=["subject","relation","object"])
    triples = triples.drop_duplicates()
    return triples

def triples_to_graph(triples: pd.DataFrame) -> nx.MultiDiGraph:
    G = nx.MultiDiGraph()
    for _, r in triples.iterrows():
        s = str(r["subject"]).strip()
        o = str(r["object"]).strip()
        rel = str(r["relation"]).strip()
        G.add_node(s, type=r.get("subject_type"), domain=r.get("domain"))
        G.add_node(o, type=r.get("object_type"), domain=r.get("domain"))
        G.add_edge(
            s, o, relation=rel,
            country=r.get("country"),
            start_year=r.get("start_year"),
            end_year=r.get("end_year"),
            notes=r.get("notes")
        )
    return G


# --- NEW: Text -> Triples (spaCy-based) for Milestone-2 ---
# Minimal, safe patterns: avoids the invalid token-pattern error entirely.
import spacy
from spacy.matcher import Matcher

# Load model once (raise clear message if model missing)
try:
    _NLP = spacy.load("en_core_web_sm")
except OSError:
    raise OSError(
        "spaCy model 'en_core_web_sm' not found. Run: python -m spacy download en_core_web_sm"
    )

_MATCHER = Matcher(_NLP.vocab)

# Pattern for:   [SUBJ]+  be  (a|an|the)?  [ATTR]+
# Example: "Albert Einstein is a physicist."
IS_A_PATTERN = [
    {"IS_SPACE": False, "OP": "+"},          # subject tokens
    {"LEMMA": "be"},                         # is/are/was/were
    {"LOWER": {"IN": ["a", "an", "the"]}, "OP": "?"},  # optional article
    {"IS_SPACE": False, "OP": "+"},          # attribute tokens
]
_MATCHER.add("IS_A", [IS_A_PATTERN])

def _clean_span_text(tokens: Iterable[spacy.tokens.Token]) -> str:
    return " ".join(t.text for t in tokens).strip(" .,:;\"'()[]{}")

def _extract_is_a(doc: spacy.tokens.Doc) -> List[Tuple[str, str, str]]:
    triples = []
    for _, start, end in _MATCHER(doc):
        span = doc[start:end]
        # split around first 'be' token
        be_i = None
        for i, t in enumerate(span):
            if t.lemma_ == "be":
                be_i = i
                break
        if be_i is None: 
            continue
        subj = _clean_span_text(span[:be_i])
        rhs = list(span[be_i+1:])
        # drop leading article if present
        if rhs and rhs[0].lower_ in {"a","an","the"}:
            rhs = rhs[1:]
        obj = _clean_span_text(rhs)
        if subj and obj:
            triples.append((subj, "is_a", obj))
    return triples

def _extract_svo(doc: spacy.tokens.Doc) -> List[Tuple[str, str, str]]:
    """
    Dependency SVO: nsubj -- VERB -- dobj (relation = verb lemma)
    Example: "Einstein developed theory" -> ("Einstein","develop","theory")
    """
    triples = []
    for sent in doc.sents:
        for token in sent:
            if token.pos_ == "VERB":
                subs = [c for c in token.children if c.dep_ in ("nsubj","nsubjpass")]
                objs = [c for c in token.children if c.dep_ in ("dobj","attr","oprd","pobj")]
                if subs and objs:
                    s = _clean_span_text(subs[0].subtree)
                    o = _clean_span_text(objs[0].subtree)
                    rel = token.lemma_
                    if s and o and rel:
                        triples.append((s, rel, o))
    return triples

def extract_triples_from_text(text: str) -> List[Dict[str, str]]:
    """
    Public API used by your Flask route.
    Returns list of dicts with subject, relation, object (plus optional type/domain fields set None).
    """
    doc = _NLP(text)
    raw = []
    raw.extend(_extract_is_a(doc))
    raw.extend(_extract_svo(doc))

    # deduplicate preserving order
    seen = set()
    uniq: List[Tuple[str, str, str]] = []
    for t in raw:
        if t not in seen:
            seen.add(t)
            uniq.append(t)

    result: List[Dict[str, str]] = []
    for s, r, o in uniq:
        result.append({
            "subject": s,
            "relation": r,
            "object": o,
            "subject_type": None,
            "object_type": None,
            "domain": None,
            "country": None,
            "start_year": None,
            "end_year": None,
            "notes": None
        })
    return result
