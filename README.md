# WorldPulse: world news and its effect on share markets

WorldPulse pulls current-affairs news from 30 sources across the world, merges duplicate stories, and tags each one with the markets and sectors it is likely to move. You can read stories in detail, track the ones you care about, and follow topics.

**Not investment advice.** Impact tags come from keyword rules or AI and are indicative only.

## What it does

| Page | What you get |
|---|---|
| **Live news** | Stories from Google News editions (US, India, UK, Singapore, Australia), BBC, Al Jazeera, Guardian, DW, France 24, NYT, CNBC, Economic Times, Livemint, Business Standard and Moneycontrol. You can filter by region, category, time and market impact, and search. A "Market-moving now" strip sits on top. |
| **Markets** | 16 indices across the US, India, Europe, Japan, China, the rest of Asia and the Middle East, plus oil, gold, silver, US 10-year yield, currencies and Bitcoin. Each has a 1-month sparkline. Below them, the stories moving each region. |
| **Reader** | The full article, where the publisher allows it, and related coverage. Also the impact view: markets, sectors with ▲ ▼ ◆, and an impact level. An optional Claude AI analysis adds stocks to watch, time horizon and confidence. A **"How the market reacted"** chart marks when the story came out. |
| **My tracker** | Tracked stories with your notes, Following/Done status, and newer updates on each story. Followed topics show a "new" count. Also your reading history and how much you read today and this week. |
| **Sources & settings** | Turn sources on or off and see which ones are working. Add any RSS feed, including any Google News search. Add your AI key here. |

## Make it a live website (free, no installing anything)

You do all of this in your web browser in about 15 minutes. You get a link like `https://worldpulse-yourname.streamlit.app` that opens on any phone or laptop. News updates on its own every few minutes and prices every minute.

1. **Unzip** `WorldPulse.zip` on your computer.
2. **Create a free GitHub account** at github.com, then click **+ → New repository**. Name it `worldpulse`, choose **Public**, and click **Create repository**.
3. On the new repository page, click **uploading an existing file**. Open the unzipped `newsmarket` folder, select **everything inside it** (including the `.streamlit` folder), and drag it into the browser. Click **Commit changes**.
   - On a Mac, hidden folders like `.streamlit` don't show by default. Press `Cmd + Shift + .` to show them. The app still works without that folder; it only sets colours.
4. Go to **share.streamlit.io** and sign in with your GitHub account.
5. Click **Create app → Deploy a public app from GitHub**. Pick the `worldpulse` repository, branch `main`, and main file `app.py`. Choose your web address, then click **Deploy**.
6. Wait 2–4 minutes while it installs. Your website is live. Share the link with anyone; nobody needs to download anything.

**Optional, for AI analysis:** in your app on share.streamlit.io, open **⋮ → Settings → Secrets**, paste `ANTHROPIC_API_KEY = "your-key"` and save.

**How "live" works:** while the page is open, it checks for new stories every 60 seconds and pops up "N new stories". It re-fetches all sources at most every 3 minutes and refreshes prices every minute. You can turn this off with the **Live auto-update** switch in the sidebar. Change the timings in `core/config.py`.

**Things to know about the free hosting:**
- If nobody opens the site for a few days, it goes to sleep. The next visitor clicks "wake up" and waits about 30 seconds.
- Your tracker data (tracked stories, notes, reading history) resets when the app restarts. That happens after an update or a sleep. To keep it permanently, move storage to a free hosted database such as Supabase.
- Everyone who opens your link shares the same tracker. Personal logins are a good next version.

## Run it on your own computer instead (optional)

1. Install **Python 3.11 or newer** from python.org. On Windows, tick "Add Python to PATH".
2. Open a terminal in the unzipped folder and run `pip install -r requirements.txt`, then `streamlit run app.py`.
3. To try it offline with sample data: `WORLDPULSE_DEMO=1 streamlit run app.py` (on Windows: `set WORLDPULSE_DEMO=1`, then the run command).

## Optional: AI impact analysis

1. Create a key at console.anthropic.com. You need billing set up.
2. Paste the key on the **Sources & settings** page. That keeps it for the browser session only. To keep it permanently, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and put the key there.
3. Open any story and click **Analyse impact with Claude**. The result is saved, so each story is only analysed once. The default model (Claude Haiku 4.5) is the cheapest. You can switch to Claude Sonnet 5.5 in settings for deeper analysis.

## Changing things yourself

Everything you're likely to change is in **`core/config.py`**:
- `SOURCES` holds the news feeds. Add a line with a name, URL, region and category.
- `INDICES` and `COMMODITIES_FX` are the markets shown. They use Yahoo Finance tickers, such as `^NSEI` for Nifty or `RELIANCE.NS` for a single stock.
- `SECTOR_RULES` and `DIRECTION_HINTS` hold the keyword rules that link news to sectors. For example, "crude oil up" is negative for airlines and paints.
- `DISPLAY_TIMEZONE` sets the time zone. `REFRESH_MINUTES`, `PRICE_REFRESH_SECONDS` and `AUTO_REFRESH_SECONDS` set how often news and prices update.

## Good to know

- **Prices** come from Yahoo Finance through the free `yfinance` library and can be about 15 minutes delayed. If Yahoo blocks requests for a while, a tile shows "–".
- **Full text in the app:** stories that come through Google News, or from paywalled sites, often can't be shown inside the app. Use **Open original** for those. Always credit and link the publisher. The reader view is for personal reading.
- **Source health:** each feed shows ✓ or ✗ on the Settings page. If a publisher changes its feed address, turn that source off or replace its URL.
- **The market reaction chart** shows timing, not cause. Markets react to many things at once.

## For developers

```
core/news.py      fetch RSS in parallel, clean, merge duplicate stories
core/impact.py    rule engine + optional Claude analysis (JSON)
core/markets.py   quotes, intraday prices, reaction around publish time
core/store.py     SQLite: reads, tracked, topics, notes, caches, settings
core/article.py   full-text extraction (trafilatura)
app.py            Streamlit UI
tests/            offline tests: python -m pytest -q
```

Ideas for next versions:
- Email or Telegram alerts for followed topics.
- A watchlist of single stocks.
- Sentiment trend charts per sector.
- User logins.
- Hosted database storage.
