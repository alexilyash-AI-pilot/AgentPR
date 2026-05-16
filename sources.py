# Search keywords and media sources configuration

# ---------------------------------------------------------------------------
# Search keyword groups
# ---------------------------------------------------------------------------

KEYWORD_GROUPS = {
    "own_brand": [
        "Choice restaurant CRM",
        "Choice app restaurant",
        "choice.app",
        "Czech Choice restaurant",
    ],
    "competitors": [
        "Sunday.app restaurant",
        "Deliverect",
        "Restimo restaurant",
        "Restaumatic",
        "Upmenu restaurant",
        "restaurant loyalty platform",
        "restaurant CRM software",
        "restaurant POS system",
        "restaurant ordering system",
        "restaurant guest management",
    ],
    "ai_topic": [
        "AI restaurant",
        "artificial intelligence restaurant",
        "restaurant technology startup",
        "restaurant automation AI",
        "restaurant digitalization",
        "restaurant SaaS platform",
        "foodtech AI",
        "hospitality technology AI",
    ],
    "funding": [
        "restaurant startup funding",
        "foodtech startup investment",
        "restaurant tech Series A",
        "restaurant tech seed round",
    ],
}

# Flat list of all queries (used by Google News RSS)
ALL_QUERIES = [q for group in KEYWORD_GROUPS.values() for q in group]

# ---------------------------------------------------------------------------
# Tier 1 — Major international media (used with NewsAPI domains filter)
# ---------------------------------------------------------------------------

TIER1_DOMAINS = [
    "techcrunch.com",
    "pathfounders.com",
    "sifted.eu",
    "euronews.com",
    "ft.com",
    "washingtonpost.com",
    "nytimes.com",
    "forbes.com",
    "theguardian.com",
    "bloomberg.com",
    "wsj.com",
    "businessinsider.com",
    "fastcompany.com",
    "euractiv.com",
    "thetimes.co.uk",
    "wired.com",
    "dailymail.co.uk",
    "reuters.com",
    "economist.com",
    "theobserver.co.uk",
    "theverge.com",
    "politico.com",
    "newsweek.com",
    "cnbc.com",
    "cybernews.com",
    "fortune.com",
    "axios.com",
    "morningbrew.com",
]

# ---------------------------------------------------------------------------
# Tier 2 — European startup / tech portals
# Try common RSS paths; fall back to Google News RSS site: query
# ---------------------------------------------------------------------------

TIER2_DOMAINS = [
    "tech.eu",
    "vestbee.com",
    "maddyness.com",
    "eu-startups.com",
    "therecursive.com",
    "itkey.media",
    "techfundingnews.com",
    "dispatcheseurope.com",
    "siliconcanals.com",
    "startupreporter.eu",
    "news.crunchbase.com",
    "pitchbook.com",
    "thenextweb.com",
    "itlogs.com",
    "restauranttechnologynews.com",
    "thesaasnews.com",
]

# ---------------------------------------------------------------------------
# Tier 3 — Regional and niche portals
# ---------------------------------------------------------------------------

TIER3_DOMAINS = [
    "startuprise.co.uk",
    "forbes.hu",
    "netokracija.com",
    "bebeez.eu",
    "technews180.com",
    "start-up.ro",
    "friss-hirek.hu",
    "er10.kz",
]

ALL_DOMAINS = TIER1_DOMAINS + TIER2_DOMAINS + TIER3_DOMAINS

# ---------------------------------------------------------------------------
# Known RSS feed paths to probe (tried in order for each domain)
# ---------------------------------------------------------------------------

RSS_PATHS = [
    "/feed",
    "/rss",
    "/feed/rss2",
    "/rss.xml",
    "/feed.xml",
    "/feeds/posts/default",
    "/blog/feed",
    "/news/feed",
]

# ---------------------------------------------------------------------------
# Country mapping by domain TLD / known domain
# ---------------------------------------------------------------------------

DOMAIN_COUNTRY_MAP = {
    "eu-startups.com": "Europe",
    "sifted.eu": "Europe",
    "tech.eu": "Europe",
    "therecursive.com": "Southeast Europe",
    "netokracija.com": "Croatia",
    "forbes.hu": "Hungary",
    "friss-hirek.hu": "Hungary",
    "start-up.ro": "Romania",
    "er10.kz": "Kazakhstan",
    "bebeez.eu": "Italy",
    "siliconcanals.com": "Netherlands",
    "maddyness.com": "France",
    "dispatcheseurope.com": "Europe",
    "startupreporter.eu": "Europe",
    "techcrunch.com": "USA",
    "reuters.com": "USA",
    "bloomberg.com": "USA",
    "wsj.com": "USA",
    "nytimes.com": "USA",
    "washingtonpost.com": "USA",
    "ft.com": "UK",
    "theguardian.com": "UK",
    "thetimes.co.uk": "UK",
    "theobserver.co.uk": "UK",
    "dailymail.co.uk": "UK",
    "startuprise.co.uk": "UK",
    "cybernews.com": "Lithuania",
    "itlogs.com": "International",
}

# Cutoff date — only articles published after this date are processed
CUTOFF_DATE = "2026-05-01"
