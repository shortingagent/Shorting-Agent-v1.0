def fetch_taapi_data(tokens, api_key, timeframe="1h", indicators=None):
    import requests
    import json
    from collections import defaultdict

    print("🔍 Tokens sent to TAAPI:", tokens)
    url = "https://api.taapi.io/bulk"
    headers = {"Content-Type": "application/json"}

    if indicators is None:
        indicators = [
            {"indicator": "rsi"},
            {"indicator": "ema"},
            {"indicator": "macd"},
            {"indicator": "sar"},
            {"indicator": "bbands"},
            {"indicator": "adx"},
            {"indicator": "volume"}
        ]
# Don't wrap again if already formatted
    elif isinstance(indicators[0], str):
        indicators = [{"indicator": ind} for ind in indicators]


    all_results = []
    exchange = "binance"

    constructs = []
    for token in tokens:
        constructs.append({
            "exchange": exchange,
            "symbol": token,
            "interval": timeframe,
            "indicators": indicators
        })

    payload = {"secret": api_key, "construct": constructs}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        print("📤 Sent to TAAPI:", json.dumps(payload, indent=2))
        print("📥 Response code:", response.status_code)

        if response.status_code == 200:
            resp_data = response.json()
            if "data" in resp_data:
                symbol_to_entries = defaultdict(list)
                for entry in resp_data["data"]:
                    parts = entry.get("id", "").split("_")
                    if len(parts) < 3:
                        continue
                    symbol = parts[1]
                    symbol_to_entries[symbol].append(entry)

                for symbol, entries in symbol_to_entries.items():
                    valid_entries = [e for e in entries if "result" in e and not e.get("errors")]
                    if len(valid_entries) >= 5:
                        all_results.append({
                            "token": symbol,
                            "interval": timeframe,
                            "exchange": exchange,
                            "data": {"data": valid_entries}
                        })
                    else:
                        print(f"⚠️ {symbol} ({timeframe}): only {len(valid_entries)} indicators.")
            else:
                print("❌ No 'data' field in response.")
        else:
            print(f"❌ HTTP error {response.status_code}")

    except requests.exceptions.Timeout:
        print(f"⏳ Timeout on {tokens} ({timeframe})")
    except Exception as e:
        print(f"🔥 Exception: {e}")

    return all_results
