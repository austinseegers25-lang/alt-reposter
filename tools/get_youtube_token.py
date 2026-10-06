"""Get a YouTube refresh token for one person's channel.

Run on your laptop:
    pip install google-auth-oauthlib
    python tools/get_youtube_token.py path\\to\\client_secret.json

A browser opens. Sign in with the Google account that owns the YouTube channel
(Lucas's, then run it again for Tate's) and pick the right channel. The script
prints a refresh token. Paste it into GitHub as YT_REFRESH_TOKEN_<NAME>.
"""
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

if len(sys.argv) != 2:
    sys.exit(__doc__)

flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
print("\nRefresh token (keep this private):\n")
print(creds.refresh_token)
