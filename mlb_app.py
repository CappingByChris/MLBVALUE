import streamlit as st
import pandas as pd
import numpy as np
import requests
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from difflib import get_close_matches
import os

# Load environment variables (use st.secrets for Streamlit Cloud, fallback to os.environ)
ODDS_API_KEY = st.secrets.get("ODDS_API_KEY", os.environ.get("ODDS_API_KEY"))
SMTP_EMAIL = st.secrets.get("SMTP_EMAIL", os.environ.get("SMTP_EMAIL"))
SMTP_PASSWORD = st.secrets.get("SMTP_PASSWORD", os.environ.get("SMTP_PASSWORD"))
RECEIVER_EMAIL = st.secrets.get("RECEIVER_EMAIL", os.environ.get("RECEIVER_EMAIL"))
EDGE_THRESHOLD = float(st.secrets.get("EDGE_THRESHOLD", os.environ.get("EDGE_THRESHOLD", 0.05)))

# Validate environment variables
if not ODDS_API_KEY:
    st.error("ODDS_API_KEY is not set. Please configure it in secrets.toml or environment variables.")
    st.stop()
else:
    st.info("ODDS_API_KEY loaded successfully.")  # Temporary debug message

if not all([SMTP_EMAIL, SMTP_PASSWORD, RECEIVER_EMAIL]):
    st.warning("Email settings are incomplete. Email alerts will not be sent.")

st.set_page_config(page_title="MLB Betting Dashboard", layout="wide")

# Team abbreviations and expected runs
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

# Team full names mapping
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
    """Simulate game outcomes based on expected runs."""
    home_wins = sum(np.random.poisson(home_exp) > np.random.poisson(away_exp) for _ in range(sims))
    p_home = home_wins / sims
    p_away = 1 - p_home
    to_ml = lambda p: round(-100 * p / (1 - p), 1) if p > 0.5 else round(100 * (1 - p) / p, 1)
    return p_home, p_away, to_ml(p_home), to_ml(p_away)

def get_odds():
    """Fetch odds from The Odds API."""
    url = f"https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/?apiKey={ODDS_API_KEY}®ions=us&markets=h2h&oddsFormat=american"
    try:
        res = requests.get(url)
        res.raise_for_status()
        return res.json()
    except requests.RequestException as e:
        st.error(f"Failed to fetch odds from API: {e}")
        return []

def match_team(name, all_names):
    """Match team name to closest full name with high confidence."""
    match = get_close_matches(name, all_names, n=1, cutoff=0.8)
    if not match:
        st.warning(f"No close match found for team: {name}")
        return None
    return match[0]

def extract_market_odds(api_data):
    """Extract head-to-head odds from API data."""
    odds_dict = {}
    for game in api_data:
        home = game.get("home_team")
        teams = game.get("teams", [])
        if not teams or not home:
            continue
        away = next((t for t in teams if t != home), None)
        if not away:
            continue
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
    """Send email alert for betting opportunities."""
    if not all([SMTP_EMAIL, SMTP_PASSWORD, RECEIVER_EMAIL]):
        st.error(f"Cannot send email for {matchup}: Email settings incomplete.")
        return
    msg = MIMEText(f"""Value alert for {matchup}!
Fair: {fair_odds}, Market: {book_odds}, Edge: {edge*100:.1f}%""")
    msg["Subject"] = f"VALUE ALERT: {matchup}"
    msg["From"] = SMTP_EMAIL
    msg["To"] = RECEIVER_EMAIL
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
            st.success(f"Email sent for {matchup}")
    except Exception as e:
        st.error(f"Email failed for {matchup}: {e}")

# === Run App ===
st.title("⚾ CC's MLB Moneyline Dashboard")

# Fetch and process odds
api_data = get_odds()
if not api_data:
    st.stop()
odds_data = personally_market_odds(api_data)

# Process games and calculate betting metrics
rows = []
all_team_names = list(TEAM_FULL_NAMES.values())
for g in games:
    home_abbr, away_abbr = g["home"], g["away"]
    home_full = TEAM_FULL_NAMES.get(home_abbr, home_abbr)
    away_full = TEAM_FULL_NAMES.get(away_abbr, away_abbr)

    # Simulate game to get probabilities and fair odds
    ph, pa, mlh, mla = simulate_game(g["home_exp"], g["away_exp"])

    # Match teams to API data
    matchup_key = (
        match_team(home_full, all_team_names),
        match_team(away_full, all_team_names)
    )
    if None in matchup_key:
        mh, ma = None, None
    else:
        market = odds_data.get(matchup_key, {})
        mh, ma = market.get("home_odds"), market.get("away_odds")

    # Calculate edge if odds are valid
    edge = None
    bet = ""
    if mh and mlh and isinstance(mh, (int, float)) and isinstance(mlh, (int, float)) and mlh != 0:
        edge = (mh - mlh) / abs(mlh)
        if edge >= EDGE_THRESHOLD:
            bet = "✅"
            send_email_alert(f"{away_abbr} @ {home-CoreLogic}", edge, mlh, mh)

    rows.append({
        "Matchup": f"{away_abbr} @ {home_abbr}",
        "P(Home Win)": round(ph, 3),
        "Fair ML (Home)": mlh,
        "Fair ML (Away)": mla,
        "Book ML (Home)": mh if mh is not None else "❌",
        "Book ML (Away)": ma if ma is not None else "❌",
        "Edge": f"{edge*100:.1f}%" if edge is not None else "",
        "Alert": bet
    })

# Display results
df = pd.DataFrame(rows)
df.fillna("", inplace=True)
st.dataframe(df, use_container_width=True)

# Export CSV with timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
st.download_button(
    "📁 Export CSV",
    df.to_csv(index=False),
    file_name=f"mlb_odds_{timestamp}.csv"
)
