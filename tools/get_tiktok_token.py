"""Get a TikTok refresh token for one person's account.

Run on your laptop:
    python tools/get_tiktok_token.py <client_key> <client_secret> <redirect_url>

<redirect_url> is the callback page, e.g.
    https://YOUR-GITHUB-NAME.github.io/alt-reposter/callback.html
It must exactly match the Redirect URI saved in the TikTok developer portal.

1. Open the link it prints, logged into the TikTok account (Lucas's, then Tate's).
2. Approve. The callback page shows a code; copy it.
3. Paste the code back here. It prints the refresh token. Save it in GitHub
   as TIKTOK_REFRESH_TOKEN_<NAME>.
"""
import secrets as pysecrets
import sys
import urllib.parse

import requests

if len(sys.argv) != 4:
    sys.exit(__doc__)
client_key, client_secret, redirect = sys.argv[1:]

params = {
    "client_key": client_key,
    "scope": "user.info.basic,video.upload,video.publish",
    "response_type": "code",
    "redirect_uri": redirect,
    "state": pysecrets.token_urlsafe(8),
}
print("\n1) Open this link and approve:\n")
print("https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(params))
code = input("\n2) Paste the code from the callback page: ").strip()
code = urllib.parse.unquote(code)

r = requests.post("https://open.tiktokapis.com/v2/oauth/token/", data={
    "client_key": client_key,
    "client_secret": client_secret,
    "code": code,
    "grant_type": "authorization_code",
    "redirect_uri": redirect,
}, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
data = r.json()
if "refresh_token" not in data:
    sys.exit(f"Didn't work: {data}")
print("\nRefresh token (keep this private):\n")
print(data["refresh_token"])
print(f"\nGranted scopes: {data.get('scope')}")
