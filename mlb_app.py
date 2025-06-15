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

# ... (rest of your script remains unchanged)
