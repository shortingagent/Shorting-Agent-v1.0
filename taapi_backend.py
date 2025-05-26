#TAAPI Fetching Engine
#This handles interacting with the TAAPI.io API:

#Sends a bulk request for multiple indicators (rsi, ema, macd, etc.) across several timeframes.
#Batches the requests and respects API rate limits.
#Filters valid results (≥5 indicators) and returns them to the main app.
#Provides verbose logging and indicator failure output.
#Used in Step 2 of crypto_short_ai_app.py.

import requests
import time
import json
from collections import defaultdict

def fetch_taapi_data(tokens, api_key):
    print("🔍 Tokens sent to TAAPI:", tokens)
    url = "https://api.taapi.io/bulk"
    headers = {"Content-Type": "application/json"}

    timeframes = ["5m", "15m", "1h", "4h"]
    indicators = [
        {"indicator": "rsi"},
        {"indicator": "ema"},
        {"indicator": "sar"},
        {"indicator": "macd"},
        {"indicator": "adx"},
        {"indicator": "bbands"},
        {"indicator": "volume"}
    ]

    all_results = []
    batch_size = 1
    exchange = "binance"

    for tf in timeframes:
        for i in range(0, len(tokens), batch_size):
            batch = tokens[i:i+batch_size]
            constructs = []

            for token in batch:
                constructs.append({
                    "exchange": exchange,
                    "symbol": token,
                    "interval": tf,
                    "indicators": indicators
                })

            payload = {"secret": api_key, "construct": constructs}

            try:
                response = requests.post(url, headers=headers, json=payload, timeout=30)

                print("\n📤 Payload:")
                print(json.dumps(payload, indent=2))
                print("📥 Response status:", response.status_code)
                print("📥 Response text:", response.text)

                if response.status_code == 200:
                    resp_data = response.json()
                    if "data" in resp_data:
                        symbol_to_entries = defaultdict(list)

                        for entry in resp_data["data"]:
                            parts = entry.get("id", "").split("_")
                            if len(parts) < 3:
                                print(f"⚠️ Invalid ID format: {entry.get('id')}")
                                continue
                            symbol = parts[1]
                            symbol_to_entries[symbol].append(entry)

                        for symbol, entries in symbol_to_entries.items():
                            valid_entries = [e for e in entries if "result" in e and not e.get("errors")]
                            failed = [e["indicator"] for e in entries if e.get("errors")]
                            token_match = next((t for t in batch if symbol in t), None)

                            if not token_match:
                                print(f"⚠️ Symbol {symbol} not matched to batch.")
                                continue

                            if len(valid_entries) >= 5:
                                all_results.append({
                                    "token": token_match,
                                    "interval": tf,
                                    "exchange": exchange,
                                    "data": {
                                        "data": valid_entries
                                    }
                                })
                                print(f"✅ {token_match} {tf} OK ({len(valid_entries)} indicators)")
                            else:
                                print(f"❌ {token_match} {tf}: only {len(valid_entries)} indicators. Skipping.")
                                if failed:
                                    print(f"   ↪️  Missing indicators: {', '.join(failed)}")
                    else:
                        print("❌ No 'data' field in TAAPI response.")
                else:
                    print(f"❌ HTTP error {response.status_code} for batch {batch} @ {tf}")

            except requests.exceptions.Timeout:
                print(f"⏳ Timeout on {batch} {tf}")
            except Exception as e:
                print(f"🔥 Exception: {e}")

            time.sleep(0.5)

    return all_results
