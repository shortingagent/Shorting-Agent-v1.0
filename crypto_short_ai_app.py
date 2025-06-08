import streamlit as st
import pandas as pd
import requests
import json
from taapi_backend import fetch_taapi_data
import sys
sys.stdout = sys.stderr
from taapi_analyzer import analyze_token

# --- Batch Fetch Logic for TAAPI ---
import time
import random

def chunked(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]

def batch_fetch_and_save(tokens, api_key, timeframes, indicators, outfile="taapi_results.json"):
    from taapi_backend import fetch_taapi_data

    results = []
    indicator_payload = [{"indicator": ind} for ind in indicators]
    total = len(tokens) * len(timeframes)
    count = 0

    for tf in timeframes:
        max_calcs = 20
        batch_size = max(1, max_calcs // len(indicators))  # 20 // 7 = 2
        for batch in chunked(tokens, batch_size):
            retry_count = 0
            success = False

            while not success and retry_count < 5:
                try:
                    batch_results = fetch_taapi_data(batch, api_key, tf, indicator_payload)
                    results.extend(batch_results)
                    count += len(batch)
                    success = True
                except Exception as e:
                    if "429" in str(e) or "rate" in str(e).lower():
                        retry_count += 1
                        sleep_time = 0.5 * (2 ** retry_count) + random.uniform(0, 0.5)
                        st.warning(f"Rate limit hit. Retrying in {sleep_time:.2f}s...")
                        time.sleep(sleep_time)
                    else:
                        st.error(f"TAAPI error: {e}")
                        break
            time.sleep(0.5)

    with open(outfile, "w") as f:
        json.dump(results, f, indent=2)
    
    return results


# Define multi-timeframe configurations for trading modes
trading_modes = {
    "Scalping": {
        "timeframes": ["1h", "15m", "5m"],
        "thresholds": {"1h": 3, "15m": 3, "5m": 2}
    },
    "Swing Trading": {
        "timeframes": ["4h", "1h", "15m"],
        "thresholds": {"4h": 3, "1h": 3, "15m": 2}
    }
}

TAAPI_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjbHVlIjoiNjgyNjgxYTY4MDZmZjE2NTFlNDdiNGQwIiwiaWF0IjoxNzQ4MDM3ODM4LCJleHAiOjMzMjUyNTAxODM4fQ.cct01_5olPj9vFkEBZlm1MBkxpR47Im6OSauxVyNp8s"

st.set_page_config(page_title="Bearish Token Shorting Agent", layout="wide")
st.title("📉 Bearish Token Shorting Agent")
st.sidebar.write("Current Stage:", st.session_state.get("app_stage", "undefined"))

# Navigation state
if "app_stage" not in st.session_state:
    st.session_state.app_stage = "step1"

# Step 1: Select trading style and preselect tokens
if st.session_state.app_stage == "step1":
    st.header("Step 1: Choose Trading Style & Preselect Tokens")

    col1, col2 = st.columns(2)

    with col1:
        style = st.selectbox("🎯 Trading Style", ["Scalping", "Swing Trading"])
        st.caption("⏱️ *Affects which timeframes and score thresholds are used later.*")

    with col2:
        mode_explanations = {
            "Overextended Gainers": "📈 Big recent gainers likely to reverse (overbought).",
            "Early Decliners": "🔽 Just starting to drop — early short entries.",
            "Illiquid Risks": "💧 Low liquidity tokens vulnerable to dumps.",
            "Declining Momentum": "🚫 Trend slowing down — bearish momentum building."
        }
        mode_options = list(mode_explanations.keys())
        mode_labels = [f"{name} – {mode_explanations[name]}" for name in mode_options]

        selected_mode_label = st.selectbox("📊 Preselection Mode", mode_labels)
        selected_mode = selected_mode_label.split(" – ")[0]
        st.caption("🔍 *Defines which types of tokens are selected for testing.*")

    if st.button("Fetch and Filter Messari Tokens"):
        st.session_state["trading_style"] = style
        with st.spinner("Fetching from Messari and filtering..."):
            def fetch_messari_metrics(limit=500):
                url = "https://data.messari.io/api/v1/assets"
                params = {"limit": limit}
                response = requests.get(url, params=params)
                if response.status_code != 200:
                    raise Exception(f"Failed to fetch Messari data: {response.status_code}")
                data = response.json()["data"]
                tokens = []
                for asset in data:
                    m = asset.get("metrics", {})
                    md = m.get("market_data", {})
                    mc = m.get("marketcap", {})
                    roi = m.get("roi_data", {})
                    rm = m.get("risk_metrics", {})
                    vs = rm.get("volatility_stats", {})
                    sr = rm.get("sharpe_ratios", {})
                    supply = m.get("supply", {})
                    tokens.append({
                        "symbol": asset.get("symbol"),
                        "name": asset.get("name"),
                        "price_usd": md.get("price_usd"),
                        "volume_24h": md.get("volume_last_24_hours"),
                        "real_volume_24h": md.get("real_volume_last_24_hours"),
                        "market_cap_usd": mc.get("current_marketcap_usd"),
                        "market_cap_rank": mc.get("rank"),
                        "change_24h": md.get("percent_change_usd_last_24_hours"),
                        "sharpe_30d": sr.get("last_30_days"),
                        "volatility_30d": vs.get("volatility_last_30_days")
                    })
                return pd.DataFrame(tokens)

            df = fetch_messari_metrics()
            df = df.dropna(subset=["change_24h", "real_volume_24h", "market_cap_usd", "sharpe_30d", "volatility_30d"])
            df = df[df["market_cap_usd"] > 0]

            if selected_mode == "Overextended Gainers":
                filtered = df[df["change_24h"] > 5]
                filtered = filtered.sort_values(by="change_24h", ascending=False).head(100)

            elif selected_mode == "Early Decliners":
                filtered = df[(df["change_24h"] < -0.5) & (df["change_24h"] > -10)]
                filtered = filtered[df["volume_24h"] > 1000000].sort_values(by="change_24h").head(100)

            elif selected_mode == "Illiquid Risks":
                df["volume_to_cap"] = df["real_volume_24h"] / df["market_cap_usd"]
                filtered = df[df["volume_to_cap"] < 0.005].sort_values(by="volume_to_cap").head(100)

            elif selected_mode == "Declining Momentum":
                filtered = df[
                    (df["change_24h"] < 0) &
                    (df["sharpe_30d"] < 0.5) &
                    (df["volatility_30d"] > 0.05)
                ].sort_values(by=["sharpe_30d", "volatility_30d"]).head(100)

            else:
                st.warning("⚠️ Unknown mode selected.")
                filtered = df.head(0)

            st.session_state["messari_filtered"] = filtered
            display_df = filtered.reset_index(drop=True)
            st.success(f"Top {len(display_df)} potential short candidates fetched.")
            st.info(f"🧠 Preselection mode applied: **{selected_mode}** — {mode_explanations[selected_mode]}")
            st.dataframe(display_df, use_container_width=True)

    next_disabled = "messari_filtered" not in st.session_state or st.session_state["messari_filtered"].empty

    st.button(
        "➡️ Next: Fetch Indicators",
        disabled=next_disabled,
        on_click=lambda: st.session_state.update(app_stage="step2") if not next_disabled else None
)


# Step 2: Fetch TAAPI indicators
elif st.session_state.app_stage == "step2":
    if st.button("⬅️ Back to Step 1"):
        st.session_state.app_stage = "step1"
        st.rerun()

    st.header("Step 2: Fetch TAAPI Indicators Automatically")

    df = st.session_state.get("messari_filtered")
    if df is None or df.empty:
        st.error("❌ No tokens available. Please complete Step 1 first.")
        st.stop()

    style = st.session_state.get("trading_style", "Swing Trading")
    config = trading_modes.get(style)
    timeframes = config["timeframes"]

    tokens = df["symbol"].dropna().str.upper().apply(lambda x: f"{x}/USDT").unique().tolist()
    indicators = ["rsi", "ema", "macd", "sar", "bbands", "adx", "volume"]
    api_key = TAAPI_API_KEY

    with st.spinner("⏳ Fetching indicator data from TAAPI..."):
        try:
            results = batch_fetch_and_save(tokens, api_key, timeframes, indicators)
            st.session_state["taapi_data"] = results
            st.success(f"✅ {len(results)} indicator entries saved to `taapi_results.json`.")
        except Exception as e:
            st.error(f"🔥 TAAPI fetch failed: {e}")
            st.stop()

    if st.button("➡️ Next: Analyze & Strategy"):
        st.session_state.app_stage = "step3"
        st.rerun()

# Step 3: Multi-Timeframe Validation & Strategy Display
elif st.session_state.app_stage == "step3":
    if st.button("🔄 Restart Test"):
        st.session_state.app_stage = "step1"
        st.rerun()
    st.header("Step 3: Multi-Timeframe Validation & Strategy")
    if "taapi_data" not in st.session_state or not st.session_state["taapi_data"]:
        st.warning("⚠️ No TAAPI data found. Please complete Step 2.")
    else:
        style = st.session_state.get("trading_style", "Swing Trading")
        config = trading_modes.get(style)
        timeframes = config["timeframes"]
        thresholds = config["thresholds"]

        from collections import defaultdict
        grouped = defaultdict(dict)
        for entry in st.session_state["taapi_data"]:
            grouped[entry["token"]][entry["interval"]] = entry

        valid_tokens = []
        for token, entries in grouped.items():
            is_valid = True
            total_score = 0
            details = {}
            strategy = None
            for tf in timeframes:
                if tf not in entries:
                    is_valid = False
                    break
                score, breakdown, strat = analyze_token(entries[tf])
                if score < thresholds[tf]:
                    is_valid = False
                    break
                details[tf] = {"score": score, "breakdown": breakdown}
                total_score += score
                strategy = strat
            if is_valid:
                valid_tokens.append({
                    "token": token,
                    "total_score": total_score,
                    "details": details,
                    "strategy": strategy
                })

        valid_tokens = sorted(valid_tokens, key=lambda x: x["total_score"], reverse=True)

        st.subheader(f"📊 {style} Candidates: {len(valid_tokens)} tokens (sorted by score)")
        for item in valid_tokens:
            st.markdown(f"### {item['token']} (Score: {item['total_score']})")
            for tf, info in item['details'].items():
                st.markdown(f"**{tf}**: Score {info['score']}")
                for line in info['breakdown']:
                    st.markdown(f"- {line}")
            if item['strategy']:
                strat = item['strategy']
                st.markdown("**Suggested Shorting Strategy:**")
                st.markdown(f"- Entry: {strat['entry_range'][0]:.6f} – {strat['entry_range'][1]:.6f}")
                st.markdown(f"- Stop Loss: {strat['stop_loss']:.6f}")
                st.markdown(f"- Take Profit: {strat['take_profit']:.6f}")
                st.markdown(f"- Time Limit: {strat['time_limit']}")
            st.markdown("---")
