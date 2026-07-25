"""One-time OAuth2 authorization for the Oura API.

Run: python -m ingestion.auth

Flow: the script opens the Oura consent page in your browser. After you
approve, the browser redirects to https://localhost:8765/callback and shows
a "can't connect" page — that is expected, nothing listens there. The
authorization code is in the address bar: copy the FULL URL from the browser
and paste it into the terminal. The script exchanges it for tokens and saves
them to tokens.json (gitignored). After this, ingestion refreshes tokens by
itself.

Why no local server: Oura requires HTTPS redirect URIs, and running a
self-signed HTTPS server locally adds friction for zero gain in a
single-user app. Copy-paste once and forget.
"""

import json
import os
import secrets
import urllib.parse
import webbrowser

import requests
from dotenv import load_dotenv

AUTHORIZE_URL = "https://cloud.ouraring.com/oauth/authorize"
TOKEN_URL = "https://api.ouraring.com/oauth/token"
REDIRECT_URI = "https://github.com/masixz/oura-data-pipeline"
TOKENS_FILE = os.path.join(os.path.dirname(__file__), "..", "tokens.json")

load_dotenv()
CLIENT_ID = os.environ["OURA_CLIENT_ID"]
CLIENT_SECRET = os.environ["OURA_CLIENT_SECRET"]


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
    print("If it does not open, visit this URL manually:\n")
    print(url + "\n")
    webbrowser.open(url)

    print("After approving, the browser lands on the GitHub repo page.")
    print("The address bar now contains ?code=... - copy the FULL URL.\n")
    pasted = input("Paste the redirect URL here: ").strip()

    query = urllib.parse.urlparse(pasted).query
    received = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}

    if "code" not in received:
        raise SystemExit("No code found in that URL. Copy the whole address bar.")
    if received.get("state") != state:
        raise SystemExit("State mismatch — restart the script and try again.")

    data = {
        "grant_type": "authorization_code",
        "code": received["code"],
        "redirect_uri": REDIRECT_URI,
    }
    # Try credentials in the POST body first, then HTTP Basic auth —
    # Oura's auth server has accepted different styles over time.
    resp = requests.post(TOKEN_URL, data={
        **data, "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
    })
    if resp.status_code in (400, 401):
        print(f"Body-auth failed ({resp.status_code}), retrying with Basic auth...")
        resp = requests.post(TOKEN_URL, data=data,
                             auth=(CLIENT_ID, CLIENT_SECRET))
    if not resp.ok:
        print(f"Token exchange failed: {resp.status_code}\n{resp.text}")
        raise SystemExit(1)
    save_tokens(resp.json())
    print("Done. Now run: python -m ingestion.ingest --start 2022-01-01")


if __name__ == "__main__":
    main()
