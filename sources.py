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
# Tier 1 — European & international English-language media
# (US-only outlets removed; remaining ones cover European topics in English)
# ---------------------------------------------------------------------------

TIER1_DOMAINS = [
    "pathfounders.com",
    "sifted.eu",
    "euronews.com",
    "ft.com",
    "theguardian.com",
    "bloomberg.com",
    "euractiv.com",
    "thetimes.co.uk",
    "wired.com",
    "dailymail.co.uk",
    "reuters.com",
    "economist.com",
    "theobserver.co.uk",
    "politico.com",
    "cybernews.com",
]

# Domains known to publish US-centric content — excluded from all results
US_ONLY_DOMAINS = {
    "techcrunch.com",
    "washingtonpost.com",
    "nytimes.com",
    "wsj.com",
    "axios.com",
    "morningbrew.com",
    "cnbc.com",
    "newsweek.com",
    "businessinsider.com",
    "fastcompany.com",
    "fortune.com",
    "theverge.com",
    "forbes.com",
}

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
    # UK startup / tech
    "uktech.news",
    "techround.co.uk",
    "startups.co.uk",
    # Hospitality & foodtech trade press
    "thecaterer.com",
    "foodnavigator.com",
    "hospitalitynet.org",
    "big-hosp.co.uk",
    # DACH / German-speaking region
    "gruenderszene.de",
    "deutsche-startups.de",
    # French tech
    "frenchweb.fr",
    # Iberia / Southern Europe
    "elreferente.es",
    "startupxplore.com",
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
    # Additional CEE / regional portals
    "www.innowacje.newseria.pl",
    "czechcrunch.cz",
    "lupa.cz",
    "forbes.cz",
    "startitup.sk",
    "businessinsider.com.pl",
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
    "uktech.news": "UK",
    "techround.co.uk": "UK",
    "startups.co.uk": "UK",
    "thecaterer.com": "UK",
    "big-hosp.co.uk": "UK",
    "foodnavigator.com": "UK",
    "hospitalitynet.org": "International",
    "gruenderszene.de": "Germany",
    "deutsche-startups.de": "Germany",
    "frenchweb.fr": "France",
    "elreferente.es": "Spain",
    "startupxplore.com": "Spain",
    "czechcrunch.cz": "Czech Republic",
    "lupa.cz": "Czech Republic",
    "forbes.cz": "Czech Republic",
    "startitup.sk": "Slovakia",
    "businessinsider.com.pl": "Poland",
}

# ---------------------------------------------------------------------------
# EU relevance signals — article title/text must contain at least one
# of these to pass the EU relevance filter for non-EU-specific domains
# ---------------------------------------------------------------------------

EU_SIGNALS = {
    # Continent / bloc
    "europe", "european", " eu ", "euro",
    # Countries
    "uk", "united kingdom", "france", "germany", "spain", "italy",
    "netherlands", "poland", "czech", "slovakia", "hungary", "romania",
    "bulgaria", "croatia", "sweden", "denmark", "norway", "finland",
    "belgium", "austria", "switzerland", "portugal", "ireland", "greece",
    "latvia", "lithuania", "estonia", "slovenia", "serbia", "ukraine",
    # Cities
    "london", "paris", "berlin", "amsterdam", "madrid", "rome", "warsaw",
    "prague", "budapest", "bucharest", "stockholm", "copenhagen", "dublin",
    "brussels", "vienna", "zurich", "lisbon", "milan", "barcelona",
    # Tracked companies (always EU-relevant by definition)
    "deliverect", "restimo", "restaumatic", "upmenu", "sunday.app",
    "choice restaurant", "choice crm", "choice.app",
}

# Cutoff date — only articles published after this date are processed
CUTOFF_DATE = "2026-05-01"
