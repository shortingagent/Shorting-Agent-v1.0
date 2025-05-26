#Main Streamlit App — Full Workflow

#This is your primary application script. It includes:
#📊 Step 1: Load tokens from the Messari API and filter them by risk level.
#📈 Step 2: Fetch indicator data from TAAPI using taapi_backend.py.
#🧠 Step 3: Score tokens and show shorting strategies based on taapi_analyzer.py.
#⚙️ A sidebar panel to configure indicator thresholds (config.json) with sliders and reset button.

import streamlit as st
import pandas as pd
import requests
import json
from taapi_backend import fetch_taapi_data
import sys
sys.stdout = sys.stderr  # Make sure print() logs show in Streamlit
from taapi_analyzer import analyze_token


TAAPI_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjbHVlIjoiNjgyNjgxYTY4MDZmZjE2NTFlNDdiNGQwIiwiaWF0IjoxNzQ4MDM3ODM4LCJleHAiOjMzMjUyNTAxODM4fQ.cct01_5olPj9vFkEBZlm1MBkxpR47Im6OSauxVyNp8s"

st.set_page_config(page_title="Bearish Token Analyzer", layout="wide")
st.title("📉 Bearish Token Shorting Agent")

DEFAULT_CONFIG = {
    "rsi_bearish_threshold": 40,
    "macd_hist_bearish_threshold": 0,
    "adx_minimum": 25,
    "bbands_entry_range_factor": 0.99,
    "sar_stoploss_factor": 1.02
}

def load_config():
    try:
        with open("config.json") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return DEFAULT_CONFIG.copy()

def save_config(config):
    with open("config.json", "w") as f:
        json.dump(config, f, indent=2)

config = load_config()


# Sidebar navigation
st.sidebar.title("Navigation")
section = st.sidebar.radio("Go to:", ["1. Load Messari Tokens", "2. Token Scoring", "3. Analyze & Trade Setup"])
# --- Strategy Configuration Panel ---
st.sidebar.markdown("### Strategy Settings")

# Initialize toggle state
if "show_config" not in st.session_state:
    st.session_state.show_config = False

# Toggle visibility
if st.sidebar.button("🔧 Show/Hide Config Panel"):
    st.session_state.show_config = not st.session_state.show_config

# Reset config
if st.sidebar.button("🧹 Reset to Default"):
    config = DEFAULT_CONFIG.copy()
    save_config(config)
    st.success("Config reset to default.")

# Show sliders if toggled
if st.session_state.show_config:
    config["rsi_bearish_threshold"] = st.sidebar.slider("RSI bearish threshold", 10, 70, config["rsi_bearish_threshold"])
    config["macd_hist_bearish_threshold"] = st.sidebar.number_input("MACD histogram max", value=config["macd_hist_bearish_threshold"])
    config["adx_minimum"] = st.sidebar.slider("ADX minimum", 5, 50, config["adx_minimum"])
    config["bbands_entry_range_factor"] = st.sidebar.slider("BBands entry range factor", 0.90, 1.0, config["bbands_entry_range_factor"])
    config["sar_stoploss_factor"] = st.sidebar.slider("SAR stop-loss factor", 1.0, 1.2, config["sar_stoploss_factor"])
    save_config(config)

# Step 1: Load Messari Data
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
            "id": asset.get("id"),
            "symbol": asset.get("symbol"),
            "name": asset.get("name"),
            "price_usd": md.get("price_usd"),
            "volume_24h": md.get("volume_last_24_hours"),
            "real_volume_24h": md.get("real_volume_last_24_hours"),
            "market_cap_usd": mc.get("current_marketcap_usd"),
            "market_cap_rank": mc.get("rank"),
            "market_cap_dominance_percent": mc.get("marketcap_dominance_percent"),
            "change_24h": md.get("percent_change_usd_last_24_hours"),
            "change_1w": roi.get("percent_change_last_1_week"),
            "change_1m": roi.get("percent_change_last_1_month"),
            "change_3m": roi.get("percent_change_last_3_months"),
            "change_1y": roi.get("percent_change_last_1_year"),
            "sharpe_30d": sr.get("last_30_days"),
            "sharpe_90d": sr.get("last_90_days"),
            "volatility_30d": vs.get("volatility_last_30_days"),
            "volatility_90d": vs.get("volatility_last_90_days"),
            "circulating_supply": supply.get("circulating")
        })
    return pd.DataFrame(tokens)

def filter_top_shorts(df, risk_level="2"):
    risk_filters = {
        "1": {"min_24h_change": 10, "max_sharpe_30d": 1.0, "min_real_volume": 1_000_000, "min_volatility_30d": 0.3},
        "2": {"min_24h_change": 5, "max_24h_change": 15, "min_sharpe_30d": 1.0, "min_real_volume": 5_000_000, "min_volatility_30d": 0.2},
        "3": {"max_24h_change": 5, "min_7d_change": 10, "min_market_cap": 100_000_000, "max_volatility_30d": 0.25}
    }
    filters = risk_filters.get(risk_level)
    if not filters:
        raise ValueError("Invalid risk level. Choose '1', '2', or '3'")
    candidates = df.copy()
    if risk_level == "1":
        candidates = candidates[
            (candidates["change_24h"] > filters["min_24h_change"]) &
            (candidates["real_volume_24h"] > filters["min_real_volume"]) &
            (candidates["sharpe_30d"] < filters["max_sharpe_30d"]) &
            (candidates["volatility_30d"] > filters["min_volatility_30d"])
        ]
    elif risk_level == "2":
        candidates = candidates[
            (candidates["change_24h"] > filters["min_24h_change"]) &
            (candidates["change_24h"] < filters["max_24h_change"]) &
            (candidates["real_volume_24h"] > filters["min_real_volume"]) &
            (candidates["sharpe_30d"] > filters["min_sharpe_30d"]) &
            (candidates["volatility_30d"] > filters["min_volatility_30d"])
        ]
    elif risk_level == "3":
        candidates = candidates[
            (candidates["change_1w"] > filters["min_7d_change"]) &
            (candidates["change_24h"] < filters["max_24h_change"]) &
            (candidates["market_cap_usd"] > filters["min_market_cap"]) &
            (candidates["volatility_30d"] < filters["max_volatility_30d"])
        ]
    return candidates.sort_values(by="sharpe_30d", ascending=False)


# --- Step 1: Load Messari Tokens ---
if section == "1. Load Messari Tokens":
    st.header("Step 1: Token Preselection via Messari")
    st.info("Select a risk level to filter tokens before analyzing indicators.")
    risk_level = st.selectbox("Choose your risk level:", ["1 - High Risk", "2 - Medium Risk", "3 - Low Risk"])
    risk_key = risk_level.split(" - ")[0]

    if st.button("Fetch and Filter Messari Tokens"):
        with st.spinner("Fetching from Messari and filtering..."):
            df = fetch_messari_metrics()
            filtered = filter_top_shorts(df, risk_level=risk_key)
            st.session_state["messari_filtered"] = filtered

            display_df = filtered.reset_index(drop=True).drop(columns=["id"], errors="ignore")
            cols = display_df.columns.tolist()
            if "name" in cols and "symbol" in cols:
                cols.insert(0, cols.pop(cols.index("name")))
                cols.insert(1, cols.pop(cols.index("symbol")))
                display_df = display_df[cols]

            st.success(f"Top {len(display_df)} potential short candidates found. (Not yet scored)")
            st.dataframe(display_df, use_container_width=True)


# --- Step 2: TAAPI Indicator Fetch (Backend) ---
elif section == "2. Token Scoring":
    st.header("Step 2: Fetch and Score Tokens")

    if "messari_filtered" not in st.session_state:
        st.warning("⚠️ Please complete Step 1 to load and filter tokens.")
    else:
        st.info("Click below to fetch indicators from TAAPI for selected tokens.")
        
        if st.button("Fetch Indicators from TAAPI"):
            print("🚀 Step 2 triggered.")

            df = st.session_state["messari_filtered"]
            tokens = df["symbol"].dropna().str.upper().apply(lambda x: f"{x}/USDT").unique().tolist()
            st.write("📦 Tokens formatted for TAAPI:", tokens)

            with st.spinner("Fetching indicators from TAAPI..."):
                TAAPI_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjbHVlIjoiNjgyNjgxYTY4MDZmZjE2NTFlNDdiNGQwIiwiaWF0IjoxNzQ4MDM3ODM4LCJleHAiOjMzMjUyNTAxODM4fQ.cct01_5olPj9vFkEBZlm1MBkxpR47Im6OSauxVyNp8s"
                
                try:
                    results = fetch_taapi_data(tokens, TAAPI_API_KEY)
                    
                    if results:
                        st.session_state["taapi_data"] = results
                        st.success(f"✅ TAAPI indicator data fetched and stored. {len(results)} entries.")
                        st.markdown("➡️ Proceed to **Step 3** to score tokens.")
                    else:
                        st.error("❌ No successful TAAPI results. Try fewer tokens or check API key/symbols.")
                
                except Exception as e:
                    st.error(f"❌ Error fetching from TAAPI: {str(e)}")

elif section == "3. Analyze & Trade Setup":
    st.header("Step 3: Analyze & Generate Shorting Strategy")

    if "taapi_data" not in st.session_state or not st.session_state["taapi_data"]:
        st.warning("⚠️ No TAAPI data found. Please complete Step 2.")
    else:
        st.markdown("### 🧠 Bearish Tokens Overview")
        bearish_tokens = []
        for result in st.session_state["taapi_data"]:
            try:
                score, reasons, _ = analyze_token(result)
                if score > 0:
                    bearish_tokens.append({
                        "token": result["token"],
                        "interval": result["interval"],
                        "score": score,
                        "reasons": reasons,
                        "raw": result
                    })
            except Exception as e:
                st.error(f"❌ Error analyzing {result['token']}: {e}")

        for token in bearish_tokens:
            with st.expander(f"{token['token']} @ {token['interval']} — Score: {token['score']}"):
                st.markdown("**Bearish Indicators:**")
                for reason in token["reasons"]:
                    st.markdown(f"- {reason}")
                if st.button(f"Analyze {token['token']} {token['interval']}", key=token['token'] + token['interval']):
                    st.session_state.selected_analysis = token["raw"]

        if "selected_analysis" in st.session_state:
            entry = st.session_state.selected_analysis
            st.subheader(f"📊 Detailed Analysis for {entry['token']} @ {entry['interval']}")

            score, breakdown, strategy = analyze_token(entry)

            st.markdown("### 🧠 Bearish Indicator Summary")
            for line in breakdown:
                st.markdown(f"- {line}")

            # GPT-enhanced explanation
            from gpt_assistant import summarize_indicators, diagnose_missing_data, generate_trade_advice

            try:
                summary = summarize_indicators(entry)
                diagnosis = diagnose_missing_data(entry)
                advice = generate_trade_advice(entry)

                st.markdown("### 🧠 GPT Summary")
                st.markdown(summary)

                st.markdown("### 🔍 GPT Diagnosis")
                st.markdown(diagnosis)

                st.markdown(f"### 📢 GPT Recommendation: **{advice}**")

            except Exception as e:
                st.error(f"⚠️ GPT analysis failed: {e}")

            st.markdown(f"### ✅ Bearish Score: **{score}**")

            st.markdown("### 📉 Suggested Shorting Strategy")
            if strategy:
                st.markdown(f"- **Entry Range:** {strategy['entry_range'][0]:.6f} – {strategy['entry_range'][1]:.6f} USDT")
                st.markdown(f"- **Stop Loss:** {strategy['stop_loss']:.6f} USDT")
                st.markdown(f"- **Take Profit:** {strategy['take_profit']:.6f} USDT")
                st.markdown(f"- **Time-Based Exit:** {strategy['time_limit']}")
            else:
                st.warning("⚠️ Not enough data to generate a strategy.")


