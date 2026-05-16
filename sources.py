# Search keywords and media sources configuration

# ---------------------------------------------------------------------------
# Tracked companies
# ---------------------------------------------------------------------------

COMPANIES = [
    "Deliverect",
    "Sunday",
    "Flipdish",
    "StoreKit",
    "UpMenu",
    "Restimo",
    "Restaumatic",
    "TheFork",
    "OpenTable",
    "Quandoo",
    "Tableo",
    "ResDiary",
    "Zenchef",
    "Eat App",
    "SevenRooms",
    "Otter",
    "TableQR",
    "MENU TIGER",
    "ChoiceQR",
    "Olo",
    "Lunchbox",
    "Owner.com",
]

PRIORITY_COMPANIES = [
    "Olo",
    "Lunchbox",
    "Owner.com",
]

DELIVERY_ECOSYSTEM_COMPANIES = [
    "DoorDash",
    "Uber Eats",
    "Deliveroo",
    "Wolt",
    "Glovo",
    "Just Eat Takeaway",
    "Prosus",
    "Bolt",
]

# ---------------------------------------------------------------------------
# Search keyword groups
# ---------------------------------------------------------------------------

KEYWORD_GROUPS = {
    "company_direct": [
        "Deliverect",
        "Sunday app restaurant",
        "sundayapp restaurant",
        "Flipdish",
        "StoreKit restaurant",
        "UpMenu restaurant",
        "Restimo",
        "Restaumatic",
        "TheFork restaurant",
        "OpenTable restaurant",
        "Quandoo restaurant",
        "Tableo restaurant",
        "ResDiary",
        "Zenchef",
        "Eat App restaurant",
        "eatapp restaurant",
        "SevenRooms",
        "Otter restaurant delivery",
        "tryotter restaurant",
        "TableQR",
        "MENU TIGER restaurant",
        "menutiger",
        "ChoiceQR",
        "choiceqr restaurant",
        "Olo restaurant ordering",
        "Lunchbox restaurant ordering",
        "Owner.com restaurant ordering",
        "Owner.com restaurants",
    ],
    "delivery_ecosystem": [
        "DoorDash restaurant ordering",
        "DoorDash menu integration",
        "DoorDash ordering integration",
        "Uber Eats restaurant ordering",
        "Uber Eats QR ordering",
        "Uber Eats menu integration",
        "Deliveroo restaurant ordering",
        "Deliveroo table ordering",
        "Deliveroo menu integration",
        "Wolt restaurant ordering",
        "Wolt table ordering",
        "Wolt menu integration",
        "Glovo restaurant ordering",
        "Glovo menu integration",
        "Just Eat Takeaway restaurant ordering",
        "Just Eat Takeaway menu integration",
        "Prosus restaurant commerce",
        "Prosus restaurant ordering",
        "Bolt restaurant ordering",
        "Bolt food delivery",
        "Bolt table ordering",
        "Bolt restaurant reservations",
    ],
    "topics": [
        "restaurant tech funding",
        "foodtech startup investment",
        "restaurant tech Series A",
        "restaurant tech seed round",
        "foodtech acquisition",
        "restaurant software partnership",
        "AI restaurant technology features",
        "restaurant POS integration",
        "QR ordering restaurant technology",
        "restaurant reservations platform",
        "delivery management restaurant software",
        "restaurant loyalty CRM software",
        "hospitality tech startup",
        "restaurant enterprise deal",
        "restaurant tech product launch",
        "restaurant tech expansion",
        "restaurant management software company",
        "restaurant SaaS platform",
        "hospitality technology AI",
        "QR ordering",
        "table ordering",
        "restaurant AI",
        "voice ordering",
        "restaurant automation",
        "restaurant commerce",
        "digital ordering",
        "restaurant middleware",
        "ordering orchestration",
        "menu synchronization",
        "restaurant integrations",
        "restaurant digital transformation",
        "AI drive thru",
        "first-party ordering",
    ],
}

# Flat list of all queries (used by Google News RSS)
ALL_QUERIES = [q for group in KEYWORD_GROUPS.values() for q in group]

# ---------------------------------------------------------------------------
# Tier 1 — Major international media (primary sources)
# ---------------------------------------------------------------------------

TIER1_DOMAINS = [
    # Global tech & business
    "techcrunch.com",
    "bloomberg.com",
    "reuters.com",
    "forbes.com",
    "cnbc.com",
    "ft.com",
    "businessinsider.com",
    "fortune.com",
    "wired.com",
    "fastcompany.com",
    "theverge.com",
    "economist.com",
    "wsj.com",
    "washingtonpost.com",
    "nytimes.com",
    "newsweek.com",
    "observer.com",
    # European media
    "sifted.eu",
    "euronews.com",
    "euractiv.com",
    "theguardian.com",
    "dailymail.co.uk",
    "thetimes.co.uk",
    "politico.com",
    "cybernews.com",
]

# Domains known to publish US-centric content — kept minimal since we now
# want articles about tracked companies regardless of geography
US_ONLY_DOMAINS: set = set()

# ---------------------------------------------------------------------------
# Tier 2 — Startup / tech ecosystem portals
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
    "crunchbase.com",
    "news.crunchbase.com",
    "morningbrew.com",
    "itlogs.com",
    # Additional ecosystem portals
    "startupreporter.eu",
    "pitchbook.com",
    "thenextweb.com",
    "restauranttechnologynews.com",
    "thesaasnews.com",
    # UK startup / tech
    "uktech.news",
    "techround.co.uk",
    "startups.co.uk",
    "pathfounders.com",
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
    "forbes.cz",
    "forbes.pl",
    "forbes.ro",
    "forbes.sk",
    "netokracija.com",
    "bebeez.eu",
    "technews180.com",
    "start-up.ro",
    "friss-hirek.hu",
    "er10.kz",
    "www.innowacje.newseria.pl",
    "czechcrunch.cz",
    "lupa.cz",
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
    "reuters.com": "International",
    "bloomberg.com": "International",
    "wsj.com": "USA",
    "nytimes.com": "USA",
    "washingtonpost.com": "USA",
    "forbes.com": "USA",
    "cnbc.com": "USA",
    "businessinsider.com": "USA",
    "fortune.com": "USA",
    "wired.com": "USA",
    "fastcompany.com": "USA",
    "theverge.com": "USA",
    "newsweek.com": "USA",
    "observer.com": "USA",
    "morningbrew.com": "USA",
    "crunchbase.com": "USA",
    "news.crunchbase.com": "USA",
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
    "forbes.pl": "Poland",
    "forbes.ro": "Romania",
    "forbes.sk": "Slovakia",
    "startitup.sk": "Slovakia",
    "businessinsider.com.pl": "Poland",
    "politico.com": "International",
    "euronews.com": "Europe",
    "euractiv.com": "Europe",
    "economist.com": "UK",
    "vestbee.com": "Europe",
    "itkey.media": "Europe",
    "techfundingnews.com": "International",
    "pitchbook.com": "USA",
    "thenextweb.com": "Netherlands",
    "restauranttechnologynews.com": "UK",
    "thesaasnews.com": "International",
    "pathfounders.com": "International",
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
    # All tracked companies (always relevant by definition)
    "deliverect", "sunday.app", "sundayapp", "flipdish", "storekit",
    "upmenu", "restimo", "restaumatic", "thefork", "opentable",
    "quandoo", "tableo", "resdiary", "zenchef", "eat app", "eatapp",
    "sevenrooms", "tryotter", "tableqr", "menutiger", "menu tiger",
    "choiceqr", "choice restaurant", "choice crm", "choice.app",
    "olo", "lunchbox", "owner.com", "owner com", "owner restaurants",
    "doordash", "uber eats", "ubereats", "deliveroo", "wolt", "glovo",
    "just eat takeaway", "just eat", "prosus", "bolt",
}

# Cutoff date — only articles published after this date are processed
CUTOFF_DATE = "2026-01-01"
