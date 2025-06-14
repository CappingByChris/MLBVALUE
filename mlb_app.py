import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import requests
from config import ODDS_API_KEY, SMTP_EMAIL, SMTP_PASSWORD, RECEIVER_EMAIL, EDGE_THRESHOLD
import smtplib
from email.mime.text import MIMEText

st.set_page_config(page_title="MLB Betting Dashboard", layout="wide")

# Sim data (example hardcoded expected runs)
games = [
    {"home": "PHI", "away": "TOR", "home_exp": 4.8, "away_exp": 4.3},
    {"home": "WSH", "away": "MIA", "home_exp": 4.1, "away_exp": 4.6},
    {"home": "BAL", "away": "LAA", "home_exp": 5.0, "away_exp": 3.9},
    {"home": "NYM", "away": "TB",  "home_exp": 4.9, "away_exp": 4.2},
    {"home": "BOS", "away": "NYY", "home_exp": 5.1, "away_exp": 3.7},
    {"home": "DET", "away": "CIN", "home_exp": 4.5, "away_exp": 4.2},
    {"home": "ATL", "away": "COL", "home_exp": 4.9, "away_exp": 4.1},
    {"home": "TEX", "away": "CWS", "home_exp": 5.0, "away_exp": 3.8},
    {"home": "MIL", "away": "STL", "home_exp": 4.7, "away_exp": 4.0},
    {"home": "HOU", "away": "MIN", "home_exp": 4.8, "away_exp": 4.1},
    {"home": "KC",  "away": "OAK", "home_exp": 5.2, "away_exp": 3.6},
    {"home": "ARI", "away": "SD",  "home_exp": 4.4, "away_exp": 4.7},
    {"home": "SEA", "away": "CLE", "home_exp": 4.6, "away_exp": 4.4},
    {"home": "LAD", "away": "SF",  "home_exp": 5.3, "away_exp": 3.9},
]

def simulate_game(home_exp, away_exp, sims=10000):
    home_wins = sum(np.random.poisson(home_exp) > np.random.poisson(away_exp) for _ in range(sims))
    p_home = home_wins / sims
    p_away = 1 - p_home
    to_ml = lambda p: round(-100 * p / (1 - p), 1) if p > 0.5 else round(100 * (1 - p) / p, 1)
    return p_home, p_away, to_ml(p_home), to_ml(p_away)

def get_odds():
    url = f"https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/?apiKey={ODDS_API_KEY}&regions=us&markets=h2h&oddsFormat=american"
    try:
        res = requests.get(url)
        return res.json()
    except:
        return []

def extract_market_odds(api_data):
    odds_dict = {}
    for game in api_data:
        teams = game['teams']
        home = game['home_team']
        for bookmaker in game['bookmakers']:
            for market in bookmaker['markets']:
                if market['key'] == 'h2h':
                    outcomes = {o['name']: o['price'] for o in market['outcomes']}
                    odds_dict[f"{teams[0]} @ {teams[1]}"] = {
                        "home_odds": outcomes.get(home),
                        "away_odds": outcomes.get(teams[0] if teams[1] == home else teams[1])
                    }
    return odds_dict

def send_email_alert(matchup, edge, fair_odds, book_odds):
    msg = MIMEText(f"Value alert for {matchup}!
Fair: {fair_odds}, Market: {book_odds}, Edge: {edge*100:.1f}%")
    msg["Subject"] = f"VALUE ALERT: {matchup}"
    msg["From"] = SMTP_EMAIL
    msg["To"] = RECEIVER_EMAIL
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        st.error(f"Email failed: {e}")

# Run Sim
st.title("⚾ MLB Betting Dashboard")
odds_data = extract_market_odds(get_odds())
rows = []
for g in games:
    ph, pa, mlh, mla = simulate_game(g["home_exp"], g["away_exp"])
    matchup = f"{g['away']} @ {g['home']}"
    market = odds_data.get(matchup, {})
    mh, ma = market.get("home_odds"), market.get("away_odds")
    edge = None
    bet = ""
    if mh and mlh:
        edge = (int(mh) - mlh) / abs(mlh)
        if edge >= EDGE_THRESHOLD:
            bet = "✅"
            send_email_alert(matchup, edge, mlh, mh)
    rows.append({
        "Matchup": matchup,
        "P(Home Win)": round(ph, 3),
        "Fair ML (Home)": mlh,
        "Book ML (Home)": mh,
        "Edge": f"{edge*100:.1f}%" if edge else "",
        "Alert": bet
    })

df = pd.DataFrame(rows)
st.dataframe(df)

# Export
st.download_button("📁 Export CSV", df.to_csv(index=False), file_name="mlb_odds.csv")

