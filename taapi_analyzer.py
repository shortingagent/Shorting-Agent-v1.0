#Bearish Scoring & Strategy Logic

#This file analyzes the data fetched from TAAPI and provides:
#A numeric bearish score.
#A list of bearish indicator breakdowns (e.g., “MACD Histogram < 0 → Bearish Momentum”).
#A suggested shorting strategy: entry range, stop loss, take profit.
#It also logs invalid or missing indicators to logs/skipped_indicators.log.
#Called during Step 3 in crypto_short_ai_app.py.

import os
import json

with open("config.json") as f:
    config = json.load(f)

def analyze_token(entry):
    raw_block = entry.get("data", {})
    data_items = raw_block.get("data")

    if not data_items:
        raise KeyError("Missing 'data' field in TAAPI response")

    # Create logs/ directory if it doesn't exist
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "skipped_indicators.log")

    with open(log_path, "a") as log_file:
        for item in data_items:
            if "indicator" not in item or "result" not in item or item.get("errors"):
                token = entry.get("token", "UNKNOWN")
                interval = entry.get("interval", "UNKNOWN")
                indicator = item.get("indicator", "UNKNOWN")
                error = item.get("errors", ["No error message"])[0]
                log_file.write(f"{token},{interval},{indicator},{error}\n")

    data = {
        item["indicator"]: item["result"]
        for item in data_items
        if "indicator" in item and "result" in item and not item.get("errors")
    }

    rsi = data.get("rsi", {}).get("value")
    macd_hist = data.get("macd", {}).get("valueMACDHist")
    ema = data.get("ema", {}).get("value")
    sar = data.get("sar", {}).get("value")
    bb = data.get("bbands", {})
    adx = data.get("adx", {}).get("value")

    breakdown = []
    score = 0

    if rsi is not None:
        if rsi < 30:
            breakdown.append(f"🔴 RSI {rsi:.2f} → Extremely Bearish")
            score += 3
        elif rsi < 40:
            breakdown.append(f"🟠 RSI {rsi:.2f} → Very Bearish")
            score += 2
        elif rsi < 50:
            breakdown.append(f"🟡 RSI {rsi:.2f} → Slightly Bearish")
            score += 1
        else:
            breakdown.append(f"🟢 RSI {rsi:.2f} → Not Bearish")

    if macd_hist is not None:
        if macd_hist < -1:
            breakdown.append(f"🔴 MACD Histogram {macd_hist:.2f} → Extremely Bearish")
            score += 2
        elif macd_hist < -0.3:
            breakdown.append(f"🟠 MACD Histogram {macd_hist:.2f} → Very Bearish")
            score += 2
        elif macd_hist < 0:
            breakdown.append(f"🟡 MACD Histogram {macd_hist:.2f} → Slightly Bearish")
            score += 1
        else:
            breakdown.append(f"🟢 MACD Histogram {macd_hist:.2f} → Not Bearish")

    if sar is not None and ema is not None:
        if sar > ema:
            breakdown.append(f"🟠 SAR {sar:.2f} > EMA {ema:.2f} → Bearish Crossover")
            score += 2
        else:
            breakdown.append(f"🟢 SAR {sar:.2f} < EMA {ema:.2f} → Neutral")

    if adx is not None:
        if adx > 40:
            breakdown.append(f"🟠 ADX {adx:.2f} → Strong trend")
            score += 1
        elif adx > 25:
            breakdown.append(f"🟡 ADX {adx:.2f} → Moderate trend")
            score += 1
        else:
            breakdown.append(f"🟢 ADX {adx:.2f} → Weak trend")

    if bb.get("valueMiddleBand") and bb.get("valueLowerBand"):
        mb = bb["valueMiddleBand"]
        lb = bb["valueLowerBand"]
        near_lower_band = (mb - lb) / mb > 0.03
        if near_lower_band:
            breakdown.append(f"🟠 BB: Middle {mb:.4f}, Lower {lb:.4f} → Price near lower band")
            score += 1
        else:
            breakdown.append(f"🟢 BB: Middle {mb:.4f}, Lower {lb:.4f} → Normal range")

    # Shorting strategy
    strategy = {}
    if bb and sar and bb.get("valueMiddleBand") is not None and bb.get("valueLowerBand") is not None:
        strategy = {
            "entry_range": (bb["valueMiddleBand"] * 0.985, bb["valueMiddleBand"] * 0.995),
            "stop_loss": sar * 1.015,
            "take_profit": bb["valueLowerBand"],
            "time_limit": "2–3 days" if adx and adx > 30 and macd_hist and macd_hist < -1 else "12–24 hours"
        }

    return score, breakdown, strategy
