"""Minimal Oura API v2 client with automatic token refresh."""

import json
import os

import requests
from dotenv import load_dotenv

API_BASE = "https://api.ouraring.com/v2/usercollection"
TOKEN_URL = "https://api.ouraring.com/oauth/token"
TOKENS_FILE = os.path.join(os.path.dirname(__file__), "..", "tokens.json")

load_dotenv()


class OuraClient:
    def __init__(self):
        self.client_id = os.environ["OURA_CLIENT_ID"]
        self.client_secret = os.environ["OURA_CLIENT_SECRET"]
        with open(TOKENS_FILE) as f:
            self.tokens = json.load(f)

    def _refresh(self):
        resp = requests.post(TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": self.tokens["refresh_token"],
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        })
        resp.raise_for_status()
        self.tokens = resp.json()
        with open(TOKENS_FILE, "w") as f:
            json.dump(self.tokens, f, indent=2)

    def _get(self, url: str, params: dict) -> dict:
        headers = {"Authorization": f"Bearer {self.tokens['access_token']}"}
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code == 401:  # expired access token -> refresh once
            self._refresh()
            headers = {"Authorization": f"Bearer {self.tokens['access_token']}"}
            resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json()

    def fetch_all(self, endpoint: str, start_date: str, end_date: str):
        """Yield every document from an endpoint, following pagination."""
        url = f"{API_BASE}/{endpoint}"
        params = {"start_date": start_date, "end_date": end_date}
        while True:
            page = self._get(url, params)
            yield from page.get("data", [])
            next_token = page.get("next_token")
            if not next_token:
                break
            params["next_token"] = next_token

    def fetch_all_heartrate(self, start_datetime: str, end_datetime: str):
        """Heart rate endpoint uses datetime params instead of dates."""
        url = f"{API_BASE}/heartrate"
        params = {"start_datetime": start_datetime, "end_datetime": end_datetime}
        while True:
            page = self._get(url, params)
            yield from page.get("data", [])
            next_token = page.get("next_token")
            if not next_token:
                break
            params["next_token"] = next_token
