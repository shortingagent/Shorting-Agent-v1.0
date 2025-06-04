import streamlit as st
import pandas as pd
import requests
import json
from taapi_backend import fetch_taapi_data
import sys
sys.stdout = sys.stderr
from taapi_analyzer import analyze_token

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

# Navigation state
if "app_stage" not in st.session_state:
    st.session_state.app_stage = "step1"

# Step 1: Select trading style and preselect tokens
if st.session_state.app_stage == "step1":
    st.header("Step 1: Choose Trading Style & Preselect Tokens")
    style = st.selectbox("Choose your trading style:", ["Scalping", "Swing Trading"])
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
            # Basic preselection: top tokens by 24h change
            filtered = df.sort_values(by="change_24h", ascending=False).head(100)
            st.session_state["messari_filtered"] = filtered
            display_df = filtered.reset_index(drop=True)
            st.success(f"Top {len(display_df)} potential short candidates fetched.")
            st.dataframe(display_df, use_container_width=True)

    if "messari_filtered" in st.session_state:
        if st.button("➡️ Next: Fetch Indicators"):
            st.session_state.app_stage = "step2"
            st.rerun()

# Step 2: Fetch TAAPI indicators
elif st.session_state.app_stage == "step2":
    if st.button("⬅️ Back to Step 1"):
        st.session_state.app_stage = "step1"
        st.rerun()
    st.header("Step 2: Fetch Indicators from TAAPI")
    if "messari_filtered" not in st.session_state:
        st.warning("⚠️ Please complete Step 1 to load tokens.")
    else:
        if st.button("Fetch Indicators from TAAPI"):
            df = st.session_state["messari_filtered"]
            tokens = df["symbol"].dropna().str.upper().apply(lambda x: f"{x}/USDT").unique().tolist()
            progress = st.progress(0, text="Fetching token indicators...")
            results = []
            total = len(tokens)
            for i, token in enumerate(tokens):
                batch_results = fetch_taapi_data([token], TAAPI_API_KEY)
                results.extend(batch_results)
                progress.progress((i + 1) / total, text=f"Processed {i + 1} of {total} tokens")

            st.session_state["taapi_data"] = results
            st.success(f"✅ TAAPI indicator data fetched. {len(results)} entries.")

        if "taapi_data" in st.session_state:
            if st.button("➡️ Next: Analyze & Strategy"):
                st.session_state.app_stage = "step3"
                st.rerun()

# Step 3: Multi-Timeframe Validation & Strategy Display
elif st.session_state.app_stage == "step3":
    if st.button("⬅️ Back to Step 2"):
        st.session_state.app_stage = "step2"
        st.rerun()
    st.header("Step 3: Multi-Timeframe Validation & Strategy")
    if "taapi_data" not in st.session_state or not st.session_state["taapi_data"]:
        st.warning("⚠️ No TAAPI data found. Please complete Step 2.")
    else:
        style = st.session_state.get("trading_style", "Swing Trading")
        config = trading_modes.get(style)
        timeframes = config["timeframes"]
        thresholds = config["thresholds"]

        # Group entries by token
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
                strategy = strat  # last timeframe strategy
            if is_valid:
                valid_tokens.append({
                    "token": token,
                    "total_score": total_score,
                    "details": details,
                    "strategy": strategy
                })

        st.subheader(f"📊 {style} Candidates: {len(valid_tokens)} tokens")
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
