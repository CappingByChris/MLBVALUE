import streamlit as st
import pandas as pd
import numpy as np
import requests
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from difflib import get_close_matches

from config import ODDS_API_KEY, SMTP_EMAIL, SMTP_PASSWORD, RECEIVER_EMAIL, EDGE_THRESHOLD

st.set_page_config(page_title="MLB Betting Dashboard", layout="wide")

# Abbreviations and expected runs
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

TEAM_FULL_NAMES = {
    "PHI": "Philadelphia Phillies", "TOR": "Toronto Blue Jays", "WSH": "Washington Nationals",
    "MIA": "Miami Marlins", "BAL": "Baltimore Orioles", "LAA": "Los Angeles Angels",
    "NYM": "New York Mets", "TB": "Tampa Bay Rays", "BOS": "Boston Red Sox",
    "NYY": "New York Yankees", "DET": "Detroit Tigers", "CIN": "Cincinnati Reds",
    "ATL": "Atlanta Braves", "COL": "Colorado Rockies", "TEX": "Texas Rangers",
    "CWS": "Chicago White Sox", "MIL": "Milwaukee Brewers", "STL": "St. Louis Cardinals",
    "HOU": "Houston Astros", "MIN": "Minnesota Twins", "KC": "Kansas City Royals",
    "OAK": "Oakland Athletics", "ARI": "Arizona Diamondbacks", "SD": "San Diego Padres",
    "SEA": "Seattle Mariners", "CLE": "Cleveland Guardians", "LAD": "Los Angeles Dodgers",
    "SF": "San Francisco Giants"
}

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

def match_team(name, all_names):
    match = get_close_matches(name, all_names, n=1, cutoff=0.6)
    return match[0] if match else None

def extract_market_odds(api_data):
    odds_dict = {}
    all_teams = set()
    for g in api_data:
        all_teams.update(g.get("teams", []))

    for game in api_data:
        teams = game.get("teams", [])
        home = game.get("home_team")
        if not teams or not home: continue
        away = [t for t in teams if t != home][0]
        for book in game.get("bookmakers", []):
            for market in book.get("markets", []):
                if market["key"] == "h2h":
                    prices = {o["name"]: o["price"] for o in market["outcomes"]}
                    odds_dict[(home, away)] = {
                        "home_odds": prices.get(home),
                        "away_odds": prices.get(away)
                    }
                    break
    return odds_dict

def send_email_alert(matchup, edge, fair_odds, book_odds):
    msg = MIMEText(f"""Value alert for {matchup}!
Fair: {fair_odds}, Market: {book_odds}, Edge: {edge*100:.1f}%""")
    msg["Subject"] = f"VALUE ALERT: {matchup}"
    msg["From"] = SMTP_EMAIL
    msg["To"] = RECEIVER_EMAIL
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        st.error(f"Email failed: {e}")

# === Run App ===
st.title("⚾ MLB Betting Dashboard")
api_data = get_odds()
odds_data = extract_market_odds(api_data)

rows = []
for g in games:
    home_abbr, away_abbr = g["home"], g["away"]
    home_full = TEAM_FULL_NAMES[home_abbr]
    away_full = TEAM_FULL_NAMES[away_abbr]

    ph, pa, mlh, mla = simulate_game(g["home_exp"], g["away_exp"])

    # Fuzzy match odds using difflib
    matchup_key = match_team(home_full, [k[0] for k in odds_data.keys()]), match_team(away_full, [k[1] for k in odds_data.keys()])
    market = odds_data.get(matchup_key, {})
    mh, ma = market.get("home_odds"), market.get("away_odds")

    edge = None
    bet = ""
    if mh and mlh:
        edge = (int(mh) - mlh) / abs(mlh)
        if edge >= EDGE_THRESHOLD:
            bet = "✅"
            send_email_alert(f"{away_abbr} @ {home_abbr}", edge, mlh, mh)

    rows.append({
        "Matchup": f"{away_abbr} @ {home_abbr}",
        "P(Home Win)": round(ph, 3),
        "Fair ML (Home)": mlh,
        "Fair ML (Away)": mla,
        "Book ML (Home)": mh if mh else "❌",
        "Book ML (Away)": ma if ma else "❌",
        "Edge": f"{edge*100:.1f}%" if edge else "",
        "Alert": bet
    })

df = pd.DataFrame(rows)
st.dataframe(df)
st.download_button("📁 Export CSV", df.to_csv(index=False), file_name="mlb_odds.csv")
# config.py

ODDS_API_KEY = "0a9a20c6b8b08c7cec9ed49704a8ffab"
SMTP_EMAIL = "thevaluefinder@gmail.com"
SMTP_PASSWORD = "found value"
RECEIVER_EMAIL = "cappingbychris@gmail.com"
EDGE_THRESHOLD = 0.03  # 3% edge threshold
