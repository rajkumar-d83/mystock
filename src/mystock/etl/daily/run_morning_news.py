"""Morning-only news fetch + sentiment scoring, standalone from run_daily_job.py.

Runs fetch_news then score_news_sentiment so fresh headlines are ready before market
open, rather than only showing up after the evening run (19:07 — gated to run late
because it needs that day's bhavcopy, not published by NSE until evening). News itself
has no such dependency — Google News RSS is "right now" regardless of market state — so
there's no reason to make it wait for the rest of the pipeline.

The evening job still fetches/scores news again too (idempotent — staging.news_raw
dedupes on (security_key, link), score_news_sentiment only scores unscored rows) because
compute_news_price_signal needs sentiment paired with that day's price move, which isn't
available until evening. This job is purely for reading, not signal computation.

Usage:
    python -m mystock.etl.daily.run_morning_news
"""
import subprocess
import sys

PYTHON = sys.executable


def run_step(name, module):
    cmd = [PYTHON, "-m", module]
    print(f"--- {name}: {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise RuntimeError(f"{name} failed with exit code {result.returncode}")


def main():
    run_step("fetch holdings news", "mystock.etl.daily.fetch_news")
    run_step("score news sentiment", "mystock.etl.staging.score_news_sentiment")
    print("Morning news fetch complete.")


if __name__ == "__main__":
    main()
