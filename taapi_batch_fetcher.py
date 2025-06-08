import json
import time
import random
from taapi_backend import fetch_taapi_data

# Pure Python chunking to batch tokens
def chunked(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]

def batch_fetch_from_taapi(tokens, api_key, timeframes, indicators=None, batch_size=20):
    results = []
    combined_inds = indicators or ["rsi", "ema", "macd", "sar", "bbands", "adx", "volume"]
    indicator_payload = [{"indicator": ind} for ind in combined_inds]
    total = len(tokens) * len(timeframes)
    count = 0

    for tf in timeframes:
        for token_batch in chunked(tokens, batch_size):
            retry_count = 0
            max_retries = 5
            success = False

            while not success and retry_count < max_retries:
                try:
                    print(f"⏳ Fetching {len(token_batch)} tokens at {tf}...")
                    batch_results = fetch_taapi_data(token_batch, api_key, tf, indicator_payload)
                    results.extend(batch_results)
                    count += len(token_batch)
                    print(f"✅ Progress: {count}/{total}")
                    success = True
                except Exception as e:
                    if "429" in str(e) or "rate" in str(e).lower():
                        retry_count += 1
                        sleep_time = 0.5 * (2 ** retry_count) + random.uniform(0, 0.5)
                        print(f"⏱️ Rate limit hit. Retrying in {sleep_time:.2f} seconds...")
                        time.sleep(sleep_time)
                    else:
                        print(f"🔥 Error: {e}")
                        break

            time.sleep(0.5)  # respect TAAPI's rate limit between requests

    return results

if __name__ == "__main__":
    # Load config with TAAPI key
    with open("config.json") as f:
        cfg = json.load(f)

    # Example tokens (replace with your actual list)
    example_tokens = [f"{sym}/USDT" for sym in ["BTC", "ETH", "ADA", "XRP", "DOGE", "SOL", "AVAX", "LTC"]]

    # Example timeframes
    timeframes = ["4h", "1h", "15m"]

    # Optional: custom indicators
    indicators = ["rsi", "ema", "macd", "sar", "bbands"]

    print("🚀 Starting TAAPI batch fetch...")
    result = batch_fetch_from_taapi(
        tokens=example_tokens,
        api_key=cfg["taapi_api_key"],
        timeframes=timeframes,
        indicators=indicators
    )

    # Save to file
    with open("taapi_results.json", "w") as f:
        json.dump(result, f, indent=2)

    print("✅ TAAPI data saved to taapi_results.json")
