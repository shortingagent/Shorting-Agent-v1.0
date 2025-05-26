import json
import openai

# Load OpenAI key from config.json
with open("config.json") as f:
    config = json.load(f)

client = openai.OpenAI(api_key=config["openai_api_key"])

def summarize_indicators(entry):
    message = f"""
Analyze the following technical indicators for {entry['token']} on the {entry['interval']} timeframe:

import pprint
pretty_data = pprint.pformat(entry["data"], indent=2, width=80)

Summarize what this means in terms of bearish signals and technical weaknesses.
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a trading assistant who explains bearish market indicators."},
            {"role": "user", "content": message}
        ]
    )
    return response.choices[0].message.content.strip()

def diagnose_missing_data(entry):
    message = f"""
This token's indicator data is incomplete. Please identify which common indicators are missing and what that might imply:

import pprint
pretty_data = pprint.pformat(entry["data"], indent=2, width=80)

"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a crypto diagnostics expert."},
            {"role": "user", "content": message}
        ]
    )
    return response.choices[0].message.content.strip()

def generate_trade_advice(entry):
    message = f"""
Based on the following bearish technical indicators for {entry['token']} on the {entry['interval']} chart:

import pprint
pretty_data = pprint.pformat(entry["data"], indent=2, width=80)


Would you recommend shorting this token? If yes, why? If not, why not?
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a crypto trading advisor who makes concise shorting recommendations."},
            {"role": "user", "content": message}
        ]
    )
    return response.choices[0].message.content.strip()
