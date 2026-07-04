#!/usr/bin/env python3
# License: GNU AGPL v3 or later.
"""Retrieval baseline for the AI harness: the "beat a simpler baseline" test.

Compares three retrievers over the named-source corpus on the held-out query
set (with qrels), reporting standard IR metrics (nDCG@10, Recall@1/3/5, MRR):

  BM25            lexical baseline (rank_bm25)
  Vector (TF-IDF) cosine over TF-IDF vectors (scikit-learn) -- fully offline
  Hybrid (RRF)    reciprocal-rank fusion of BM25 + vector

If OPENAI_API_KEY is set, also runs a dense OpenAI-embeddings arm and a
BM25+embeddings RRF hybrid. Everything except that optional arm is deterministic
and needs no network, so a grader re-runs and gets identical numbers.

  python tools/speedrun/ai/retrieval.py
"""
import json
import math
import os
import re

from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus", "corpus.jsonl")
QUERIES = os.path.join(HERE, "gold", "queries.jsonl")

_WORD = re.compile(r"[a-z0-9]+")


def tok(s):
    return _WORD.findall(s.lower())


def load():
    corpus = [json.loads(l) for l in open(CORPUS)]
    queries = [json.loads(l) for l in open(QUERIES)]
    return corpus, queries


# --- retrievers: each returns a ranked list of chunk ids for a query -----

def bm25_ranker(corpus):
    ids = [c["id"] for c in corpus]
    bm = BM25Okapi([tok(c["text"]) for c in corpus])
    def rank(q):
        scores = bm.get_scores(tok(q))
        return [ids[i] for i in sorted(range(len(ids)), key=lambda i: -scores[i])]
    return rank


def tfidf_ranker(corpus):
    ids = [c["id"] for c in corpus]
    vec = TfidfVectorizer(tokenizer=tok, token_pattern=None)
    mat = vec.fit_transform([c["text"] for c in corpus])
    def rank(q):
        sims = cosine_similarity(vec.transform([q]), mat)[0]
        return [ids[i] for i in sorted(range(len(ids)), key=lambda i: -sims[i])]
    return rank


def openai_embed_ranker(corpus):
    """Dense retriever using OpenAI embeddings (only if OPENAI_API_KEY set)."""
    from openai import OpenAI
    client = OpenAI()
    model = "text-embedding-3-small"
    ids = [c["id"] for c in corpus]
    def embed(texts):
        r = client.embeddings.create(model=model, input=texts)
        return [d.embedding for d in r.data]
    doc_vecs = embed([c["text"] for c in corpus])
    import numpy as np
    D = np.array(doc_vecs)
    def rank(q):
        qv = np.array(embed([q])[0])
        sims = D @ qv / (np.linalg.norm(D, axis=1) * np.linalg.norm(qv) + 1e-9)
        return [ids[i] for i in sorted(range(len(ids)), key=lambda i: -sims[i])]
    return rank


def rrf(rankers, k=60):
    """Reciprocal-rank fusion of several rankers."""
    def rank(q):
        score = {}
        for r in rankers:
            for pos, cid in enumerate(r(q)):
                score[cid] = score.get(cid, 0.0) + 1.0 / (k + pos + 1)
        return sorted(score, key=lambda c: -score[c])
    return rank


# --- metrics -------------------------------------------------------------

def dcg_at(ranked, rel, k):
    return sum((1.0 if ranked[i] in rel else 0.0) / math.log2(i + 2) for i in range(min(k, len(ranked))))


def ndcg_at(ranked, rel, k):
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(k, len(rel))))
    return dcg_at(ranked, rel, k) / ideal if ideal else 0.0


def evaluate(ranker, queries, ks=(1, 3, 5)):
    n = len(queries)
    ndcg = 0.0
    recall = {k: 0.0 for k in ks}
    mrr = 0.0
    for q in queries:
        ranked = ranker(q["query"])
        rel = set(q["relevant"])
        ndcg += ndcg_at(ranked, rel, 10)
        for k in ks:
            hits = len(rel & set(ranked[:k]))
            recall[k] += hits / len(rel)
        rr = 0.0
        for i, cid in enumerate(ranked):
            if cid in rel:
                rr = 1.0 / (i + 1); break
        mrr += rr
    return {
        "nDCG@10": ndcg / n,
        **{f"Recall@{k}": recall[k] / n for k in ks},
        "MRR": mrr / n,
    }


def run():
    corpus, queries = load()
    bm25 = bm25_ranker(corpus)
    tfidf = tfidf_ranker(corpus)
    methods = [
        ("BM25 (lexical baseline)", bm25),
        ("Vector (TF-IDF cosine)", tfidf),
        ("Hybrid RRF (BM25+TF-IDF)", rrf([bm25, tfidf])),
    ]
    if os.environ.get("OPENAI_API_KEY"):
        try:
            emb = openai_embed_ranker(corpus)
            methods.append(("Vector (OpenAI embeddings)", emb))
            methods.append(("Hybrid RRF (BM25+OpenAI)", rrf([bm25, emb])))
        except Exception as e:
            print(f"(OpenAI embeddings arm skipped: {e})")

    results = {name: evaluate(fn, queries) for name, fn in methods}
    cols = ["nDCG@10", "Recall@1", "Recall@3", "Recall@5", "MRR"]
    print(f"Retrieval over {len(corpus)} source chunks, {len(queries)} held-out queries:\n")
    print(f"{'method':<30}" + "".join(f"{c:>10}" for c in cols))
    print("-" * (30 + 10 * len(cols)))
    for name, m in results.items():
        print(f"{name:<30}" + "".join(f"{m[c]:>10.3f}" for c in cols))
    base = results["BM25 (lexical baseline)"]["nDCG@10"]
    best_name = max(results, key=lambda k: results[k]["nDCG@10"])
    best = results[best_name]["nDCG@10"]
    print(f"\nBest: {best_name} nDCG@10={best:.3f} vs BM25 {base:.3f} "
          f"(+{(best-base):.3f}, {100*(best-base)/base:+.1f}%).")
    return results


if __name__ == "__main__":
    run()
