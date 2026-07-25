"""One-time OAuth2 authorization for the Oura API.

Run: python -m ingestion.auth

Opens the browser, you approve your own app, the local server catches the
redirect and exchanges the code for tokens. Tokens land in tokens.json
(gitignored). After this, ingestion refreshes tokens by itself.
"""

import http.server
import json
import os
import secrets
import urllib.parse
import webbrowser

import requests
from dotenv import load_dotenv

AUTHORIZE_URL = "https://cloud.ouraring.com/oauth/authorize"
TOKEN_URL = "https://api.ouraring.com/oauth/token"
REDIRECT_URI = "http://localhost:8765/callback"
TOKENS_FILE = os.path.join(os.path.dirname(__file__), "..", "tokens.json")

load_dotenv()
CLIENT_ID = os.environ["OURA_CLIENT_ID"]
CLIENT_SECRET = os.environ["OURA_CLIENT_SECRET"]

_received = {}


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        _received.update({k: v[0] for k, v in params.items()})
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h2>Authorized. You can close this tab.</h2>")

    def log_message(self, *args):
        pass  # keep the terminal quiet


def save_tokens(tokens: dict) -> None:
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=2)
    print(f"Tokens saved to {os.path.abspath(TOKENS_FILE)}")


def main():
    state = secrets.token_urlsafe(16)
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "state": state,
    }
    url = f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"
    print("Opening browser for authorization...")
    webbrowser.open(url)

    server = http.server.HTTPServer(("localhost", 8765), CallbackHandler)
    while "code" not in _received:
        server.handle_request()

    if _received.get("state") != state:
        raise SystemExit("State mismatch — possible CSRF, aborting.")

    resp = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": _received["code"],
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    })
    resp.raise_for_status()
    save_tokens(resp.json())
    print("Done. Now run: python -m ingestion.ingest --start 2022-01-01")


if __name__ == "__main__":
    main()
