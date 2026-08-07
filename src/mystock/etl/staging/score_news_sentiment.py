"""Scores unscored staging.news_raw headlines with FinBERT (ProsusAI/finbert, local —
same no-cloud-API philosophy as the RAG embeddings, see MYSTOCK_PRODUCT_SPEC.md §11), and
writes results to staging.news_sentiment.

sentiment_score = P(positive) - P(negative), range [-1, 1] — a single signed number that
compute_news_price_signal.py can average per day without needing to carry the full
3-class distribution around. sentiment_label is just the argmax class.

Idempotent — only scores rows with no existing staging.news_sentiment entry (LEFT JOIN ...
WHERE IS NULL), so re-running after fetch_news.py adds new headlines only scores the
delta.

Usage:
    python -m mystock.etl.staging.score_news_sentiment
    python -m mystock.etl.staging.score_news_sentiment --batch-size 32
"""
import argparse

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from mystock.db import get_conn

MODEL_NAME = "ProsusAI/finbert"


def fetch_unscored(conn):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT b.id, b.security_key, b.raw_payload->>'title', b.raw_payload->>'link',
                      b.raw_payload->>'source_name', b.published_at
               FROM staging.news_raw b
               LEFT JOIN staging.news_sentiment s ON s.news_raw_id = b.id
               WHERE s.news_raw_id IS NULL AND b.raw_payload->>'title' IS NOT NULL"""
        )
        return cur.fetchall()


def score_batch(tokenizer, model, titles):
    inputs = tokenizer(titles, return_tensors="pt", padding=True, truncation=True, max_length=64)
    with torch.no_grad():
        probs = torch.nn.functional.softmax(model(**inputs).logits, dim=-1)
    id2label = model.config.id2label
    results = []
    for p in probs:
        scores = {id2label[i]: v.item() for i, v in enumerate(p)}
        label = max(scores, key=scores.get)
        signed_score = scores["positive"] - scores["negative"]
        results.append((label, signed_score))
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-size", type=int, default=32)
    args = ap.parse_args()

    conn = get_conn()
    rows = fetch_unscored(conn)
    print(f"{len(rows)} unscored headlines", flush=True)
    if not rows:
        conn.close()
        return

    print(f"Loading {MODEL_NAME}...", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
    model.eval()

    scored = 0
    with conn.cursor() as cur:
        for i in range(0, len(rows), args.batch_size):
            batch = rows[i:i + args.batch_size]
            titles = [r[2] for r in batch]
            results = score_batch(tokenizer, model, titles)
            for (news_raw_id, security_key, title, link, source_name, published_at), (label, score) in zip(batch, results):
                cur.execute(
                    """INSERT INTO staging.news_sentiment
                           (news_raw_id, security_key, title, link, source_name, published_at,
                            sentiment_label, sentiment_score, model_name)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (news_raw_id) DO NOTHING""",
                    (news_raw_id, security_key, title, link, source_name, published_at, label, round(score, 4), MODEL_NAME),
                )
            conn.commit()
            scored += len(batch)
            print(f"  scored {scored}/{len(rows)}", flush=True)

    conn.close()
    print(f"Done. {scored} headlines scored.")


if __name__ == "__main__":
    main()
