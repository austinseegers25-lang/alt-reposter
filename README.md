# ALT Reposter

Every 15 minutes this bot checks Lucas's and Tate's Instagram. When either posts a new video,
it downloads the original file (no watermark) and sends it to **that same person's** TikTok and
YouTube Shorts.

It runs free on GitHub Actions. No server and no monthly bill.

---

## Read this first: what works on day one

| | Day one | After approval |
|---|---|---|
| **Instagram** (reading new posts) | ✅ Works | — |
| **TikTok** | ✅ The video lands in the TikTok app inbox as a draft. Open it, tap Post (and add a trending sound if you want). | Posts automatically (set `tiktok_mode: direct`). Approval usually takes days to ~2 weeks. |
| **YouTube Shorts** | ⚠️ Uploads, but YouTube **locks it to private** until your API project is approved. | Posts publicly, fully automatic. |

Both TikTok and YouTube make every new app go through a review before it can post publicly.
Paid tools like Repurpose.io already passed those reviews, which is why they work instantly.
Your own version is free and you control it, but you wait on the approvals.

**Other limits:**
- **Reels that use Instagram's music library won't come through.** Instagram doesn't share the
  file for those. The bot skips them and tells you; post those by hand. Original audio works.
- **Paid promos (e.g. Astral):** turn on the branded/paid-promotion label on each platform.
  In TikTok draft mode you do it when you tap Post.

---

## Setup (about 1–2 hours, one time)

You'll do this on your Windows laptop in a browser. A few steps need Lucas and Tate to log in
to their own accounts, so have them around or on FaceTime.

### Step 1: Put the code on GitHub

1. Make a free account at github.com if you don't have one.
2. Click **New repository** and name it `alt-reposter`. Choose **Public**. Public is fine and
   needed for the free plan to cover it; secrets and tokens stay hidden.
3. On the empty repo page, click **uploading an existing file**. Drag in **everything inside**
   the unzipped `alt-reposter` folder (including the `.github` folder), then click **Commit**.
   - If the `.github` folder doesn't show up (Windows hides it sometimes), make it by hand:
     **Add file → Create new file**, type the name `.github/workflows/repost.yml`, and paste in
     the contents of that file.
4. **Settings → Pages**: set Source to **Deploy from a branch**, Branch **main**, folder
   **/docs**, then Save. After a minute your site is live at
   `https://YOUR-GITHUB-NAME.github.io/alt-reposter/`. TikTok and Meta need this site for their
   app forms.
5. Edit `docs/privacy.html` and `docs/terms.html` (pencil icon) and replace
   `[YOUR BUSINESS EMAIL]` with a real email.

> **Where secrets go:** every "add secret" step below means **Settings → Secrets and variables
> → Actions → New repository secret**. Names must match exactly.

### Step 2: The encryption key

The bot saves its memory (what it already posted, plus refreshed logins) in an encrypted file.

1. Install Python from python.org on your laptop. During install, check **"Add python.exe to
   PATH"**.
2. Open **Command Prompt**, `cd` into the unzipped folder, and run:
   ```
   pip install cryptography requests google-auth-oauthlib
   python tools\make_state_key.py
   ```
3. Add the printed value as the secret **`STATE_KEY`**.

### Step 3: Instagram

Lucas's and Tate's Instagram accounts must be **Creator** or **Business** accounts (in the
Instagram app: Settings → Account type and tools).

1. Go to developers.facebook.com, log in, and click **My Apps → Create App**.
   Choose the **Business** type if asked. When it asks for a use case, pick
   **"Manage messaging & content on Instagram"** (Instagram API with Instagram login).
2. In the app: **Instagram → API setup with Instagram login**.
3. Under **Generate access tokens**, click **Add account**. Lucas logs into his Instagram and
   approves, then do the same for Tate.
   - If it says they must be testers first: **App roles → Roles → Add People → Instagram
     Tester**, enter their usernames. They accept in the Instagram app (Settings → Website
     permissions → Apps and websites → Tester invites), then retry.
4. Click **Generate token** next to each account and copy it.
5. Add secrets **`IG_TOKEN_LUCAS`** and **`IG_TOKEN_TATE`**.

You don't need Meta's App Review, because these are your own accounts.

### Step 4: YouTube

1. Go to console.cloud.google.com and create a project called `alt-reposter`.
2. **APIs & Services → Library**: search **YouTube Data API v3** and click **Enable**.
3. **APIs & Services → OAuth consent screen** (may be called "Google Auth Platform"):
   - User type **External**. App name `ALT Reposter`. Use your email.
   - Under **Data access / Scopes**, add `.../auth/youtube.upload`.
   - Under **Audience**, click **Publish app** (move it to "In production"). **Don't skip this.**
     In "Testing" mode Google kills the login every 7 days. Google will warn that the app is
     unverified; that's fine for your own use.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**, type **Desktop
   app**. Download the JSON file.
5. Add secrets **`YT_CLIENT_ID`** and **`YT_CLIENT_SECRET`** (both are in that JSON file).
6. On your laptop, run:
   ```
   python tools\get_youtube_token.py C:\path\to\the-downloaded-file.json
   ```
   A browser opens. Sign in with **Lucas's** YouTube account. On the "Google hasn't verified this
   app" screen, click **Advanced → Go to ALT Reposter**. Copy the refresh token it prints into
   secret **`YT_REFRESH_TOKEN_LUCAS`**.
   Run it again with **Tate's** account and save **`YT_REFRESH_TOKEN_TATE`**.
7. **Apply for approval** so uploads can be public: fill out the
   *YouTube API Services Audit and Quota Extension* form (search that name; it's on
   support.google.com). Describe it as: "Internal tool that republishes our own creators'
   Instagram videos to their own YouTube channels." Include your site and privacy URLs.

### Step 5: TikTok

1. Go to developers.tiktok.com, log in, and register as a developer (organization:
   ALT Marketing LLC).
2. **Manage apps → Connect an app**. Fill in:
   - Platform: **Web**. Website URL: your GitHub Pages site.
   - Terms of Service URL: `…/alt-reposter/terms.html`. Privacy URL: `…/alt-reposter/privacy.html`.
   - Add products **Login Kit** and **Content Posting API**.
   - Scopes: `user.info.basic`, `video.upload`, `video.publish`.
   - Login Kit Redirect URI: `https://YOUR-GITHUB-NAME.github.io/alt-reposter/callback.html`
3. **Sandbox (works right away):** create a Sandbox for the app and add Lucas's and Tate's
   TikTok accounts as **target users**. Use the sandbox's client key and secret for now.
4. Add secrets **`TIKTOK_CLIENT_KEY`** and **`TIKTOK_CLIENT_SECRET`**.
5. On your laptop, run:
   ```
   python tools\get_tiktok_token.py CLIENT_KEY CLIENT_SECRET https://YOUR-GITHUB-NAME.github.io/alt-reposter/callback.html
   ```
   Open the link while logged in as **Lucas** on TikTok, approve, copy the code from the page,
   and paste it in. Save the printed token as **`TIKTOK_REFRESH_TOKEN_LUCAS`**. Repeat for
   Tate and save **`TIKTOK_REFRESH_TOKEN_TATE`**.
6. **Later, for fully automatic posting:** submit the app for review, then request the
   **Direct Post** audit. TikTok wants a screen recording of the flow. Once approved:
   - swap in the production client key and secret
   - redo step 5 for both accounts
   - change `tiktok_mode: draft` to `tiktok_mode: direct` in `config.yaml`

### Step 6: Turn it on and test

1. Open the **Actions** tab. If asked, click **"I understand my workflows, go ahead and enable
   them"**.
2. Click **Repost Instagram to TikTok + Shorts → Run workflow** and tick **Dry run**. When it
   finishes with a green check, click into the run. You should see "first run: marked N existing
   videos as already handled". **The bot never reposts old videos, only ones posted after this
   first run.**
3. Have Lucas post a test reel with original audio. Within about 15–20 minutes it should show up
   in his TikTok inbox and his YouTube Studio.

### Optional: Discord pings

Make a Discord channel webhook (Channel settings → Integrations → Webhooks) and save it as the
secret **`DISCORD_WEBHOOK`**. You'll get a message for every post, skip, and error.

---

## Day to day

- **Nothing to do.** It runs every 15 minutes on its own. GitHub sometimes runs it a few
  minutes late.
- **Adding someone** (e.g. another creator): add a block in `config.yaml` with their name, then
  add their three secrets: `IG_TOKEN_NAME`, `YT_REFRESH_TOKEN_NAME`, `TIKTOK_REFRESH_TOKEN_NAME`.
- **Turning a platform off** for someone: set `youtube: false` or `tiktok: false` under
  their name.
- **If a login breaks** (you'll see errors in Actions or Discord): redo that person's step
  for that platform and paste the new token over the old secret. The bot picks up the new
  one automatically.
  - Instagram logins refresh themselves weekly. They only die if the bot is off for 60+ days.
  - TikTok logins last about a year.
- Failed uploads retry up to 3 times, then give up and tell you.

## What's in here

```
reposter/       the bot (main.py runs it)
config.yaml     who and where; edit this
.github/        the 15-minute schedule
tools/          one-time login helpers you run on your laptop
docs/           the small website TikTok/Meta require (homepage, privacy, terms, login callback)
tests/          automated tests
state.enc       the bot's encrypted memory (created automatically)
```
