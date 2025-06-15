import streamlit as st
import pandas as pd
import numpy as np
import requests
from config import ODDS_API_KEY, SMTP_EMAIL, SMTP_PASSWORD, RECEIVER_EMAIL, EDGE_THRESHOLD
import smtplib
from email.mime.text import MIMEText

st.set_page_config(page_title="MLB Betting Dashboard", layout="wide")

# Hardcoded team map to match API full names
TEAM_MAP = {
    "PHI": "Philadelphia Phillies", "TOR": "Toronto Blue Jays",
    "WSH": "Washington Nationals", "MIA": "Miami Marlins",
    "BAL": "Baltimore Orioles", "LAA": "Los Angeles Angels",
    "NYM": "New York Mets", "TB": "Tampa Bay Rays",
    "BOS": "Boston Red Sox", "NYY": "New York Yankees",
    "DET": "Detroit Tigers", "CIN": "Cincinnati Reds",
    "ATL": "Atlanta Braves", "COL": "Colorado Rockies",
    "TEX": "Texas Rangers", "CWS": "Chicago White Sox",
    "MIL": "Milwaukee Brewers", "STL": "St. Louis Cardinals",
    "HOU": "Houston Astros", "MIN": "Minnesota Twins",
    "KC": "Kansas City Royals", "OAK": "Oakland Athletics",
    "ARI": "Arizona Diamondbacks", "SD": "San Diego Padres",
    "SEA": "Seattle Mariners", "CLE": "Cleveland Guardians",
    "LAD": "Los Angeles Dodgers", "SF": "San Francisco Giants",
}

games = [
    {"home": "PHI", "away": "TOR", "home_exp": 4.8, "away_exp": 4.3},
    {"home": "WSH", "away": "MIA", "home_exp": 4.1, "away_exp": 4.6},
    # ... Add others here ...
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
        home_team = game.get('home_team')
        teams = game.get('teams')
        if not teams or not home_team:
            continue
        try:
            for bookmaker in game['bookmakers']:
                for market in bookmaker['markets']:
                    if market['key'] == 'h2h':
                        outcomes = {o['name']: o['price'] for o in market['outcomes']}
                        away_team = [t for t in teams if t != home_team][0]
                        matchup = f"{away_team} @ {home_team}"
                        odds_dict[matchup] = {
                            "home_odds": outcomes.get(home_team),
                            "away_odds": outcomes.get(away_team)
                        }
                        break
                break
        except Exception as e:
            st.warning(f"Failed parsing odds: {e}")
    return odds_dict

def send_email_alert(matchup, team, edge, fair_odds, book_odds):
    msg = MIMEText(
        f"Value alert for {team} in {matchup}!\nFair: {fair_odds}, Market: {book_odds}, Edge: {edge*100:.1f}%"
    )
    msg["Subject"] = f"VALUE ALERT: {team} in {matchup}"
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
    home_team = TEAM_MAP[g['home']]
    away_team = TEAM_MAP[g['away']]
    matchup_full = f"{away_team} @ {home_team}"
    matchup_abbrev = f"{g['away']} @ {g['home']}"
    
    market = odds_data.get(matchup_full, {})
    mh, ma = market.get("home_odds"), market.get("away_odds")

    edge_home = edge_away = None
    alert_home = alert_away = ""

    if mh and mlh:
        edge_home = (int(mh) - mlh) / abs(mlh)
        if edge_home >= EDGE_THRESHOLD:
            alert_home = "✅"
            send_email_alert(matchup_abbrev, g["home"], edge_home, mlh, mh)

    if ma and mla:
        edge_away = (int(ma) - mla) / abs(mla)
        if edge_away >= EDGE_THRESHOLD:
            alert_away = "✅"
            send_email_alert(matchup_abbrev, g["away"], edge_away, mla, ma)

    rows.append({
        "Matchup": matchup_abbrev,
        "P(Home Win)": round(ph, 3),
        "P(Away Win)": round(pa, 3),
        "Fair ML (Home)": mlh,
        "Fair ML (Away)": mla,
        "Book ML (Home)": mh if mh else "❌",
        "Book ML (Away)": ma if ma else "❌",
        "Edge (Home)": f"{edge_home*100:.1f}%" if edge_home else "",
        "Edge (Away)": f"{edge_away*100:.1f}%" if edge_away else "",
        "Alert (Home)": alert_home,
        "Alert (Away)": alert_away
    })

df = pd.DataFrame(rows)
st.dataframe(df)

# Export
st.download_button("📁 Export CSV", df.to_csv(index=False), file_name="mlb_odds.csv")
