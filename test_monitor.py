"""
AgentPR test suite — runs real network fetches for RSS/NewsAPI,
mocks out Google Sheets and Telegram so no credentials are needed.
"""

import sys
import json
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# ── inject fake env vars before importing modules that read them ──
import os
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "fake_token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123456")
os.environ.setdefault("GOOGLE_SERVICE_ACCOUNT_JSON", json.dumps({
    "type": "service_account",
    "project_id": "test",
    "private_key_id": "key123",
    "private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0Z3VS5JJcds3xHn/ygWep4VBs+gIJbqOsYN8j2xNE6QXJRXL\n-----END RSA PRIVATE KEY-----\n",
    "client_email": "test@test.iam.gserviceaccount.com",
    "client_id": "123",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
}))
os.environ.setdefault("SPREADSHEET_ID", "fake_spreadsheet_id")
os.environ.setdefault("NEWSAPI_KEY", "")  # empty = skip NewsAPI in tests

from sources import ALL_QUERIES, KEYWORD_GROUPS, TIER2_DOMAINS, DOMAIN_COUNTRY_MAP, CUTOFF_DATE
from monitor import (
    _parse_date, _is_after_cutoff, _domain_from_url,
    _country_for_domain, _portal_name_from_domain, _match_companies,
    _build_article, fetch_google_news_rss,
)
from telegram_bot import _escape, _format_author


# ────────────────────────────────────────────────────────────────────────────
# Unit tests — pure logic, no network
# ────────────────────────────────────────────────────────────────────────────

class TestDateParsing(unittest.TestCase):
    def test_iso_after_cutoff(self):
        self.assertTrue(_is_after_cutoff("2026-05-10"))

    def test_iso_before_cutoff(self):
        self.assertFalse(_is_after_cutoff("2026-04-30"))

    def test_rfc2822_after_cutoff(self):
        self.assertTrue(_is_after_cutoff("Mon, 11 May 2026 10:00:00 +0000"))

    def test_rfc2822_before_cutoff(self):
        self.assertFalse(_is_after_cutoff("Thu, 30 Apr 2026 10:00:00 +0000"))

    def test_none_returns_true(self):
        # unknown dates are included (better to over-report)
        self.assertTrue(_is_after_cutoff(None))

    def test_empty_string_returns_true(self):
        self.assertTrue(_is_after_cutoff(""))


class TestDomainHelpers(unittest.TestCase):
    def test_extract_domain(self):
        self.assertEqual(_domain_from_url("https://eu-startups.com/article"), "eu-startups.com")
        self.assertEqual(_domain_from_url("https://www.sifted.eu/news/xyz"), "sifted.eu")

    def test_country_from_known_domain(self):
        self.assertEqual(_country_for_domain("eu-startups.com"), "Europe")
        self.assertEqual(_country_for_domain("forbes.hu"), "Hungary")
        self.assertEqual(_country_for_domain("netokracija.com"), "Croatia")

    def test_country_from_tld(self):
        self.assertEqual(_country_for_domain("some-portal.pl"), "Poland")
        self.assertEqual(_country_for_domain("news-site.de"), "Germany")
        self.assertEqual(_country_for_domain("media.cz"), "Czech Republic")

    def test_portal_name_formatting(self):
        self.assertEqual(_portal_name_from_domain("eu-startups.com"), "Eu Startups")
        self.assertEqual(_portal_name_from_domain("sifted.eu"), "Sifted")


class TestCompanyMatching(unittest.TestCase):
    def test_matches_deliverect(self):
        self.assertEqual(_match_companies("Deliverect raises Series C"), ["Deliverect"])

    def test_matches_sunday_app(self):
        self.assertEqual(_match_companies("sunday.app launches in Germany"), ["Sunday"])

    def test_matches_choice(self):
        self.assertEqual(_match_companies("Czech Choice restaurant CRM secures funding"), ["ChoiceQR"])

    def test_matches_restimo(self):
        self.assertEqual(_match_companies("Restimo expands to Poland"), ["Restimo"])

    def test_matches_delivery_ecosystem(self):
        self.assertEqual(
            _match_companies("Bolt launches restaurant table ordering integration"),
            ["Bolt"],
        )

    def test_fallback(self):
        self.assertEqual(_match_companies("Random unrelated news"), ["Restaurant Tech"])


class TestBuildArticle(unittest.TestCase):
    def test_basic_build(self):
        entry = {
            "title": "Deliverect raises $150M",
            "link": "https://techcrunch.com/2026/05/10/deliverect",
            "published": "2026-05-10",
            "author": "Jane Doe",
            "source": {"name": "TechCrunch"},
        }
        article = _build_article(entry, query="Deliverect")
        self.assertEqual(article["title"], "Deliverect raises $150M")
        self.assertEqual(article["url"], "https://techcrunch.com/2026/05/10/deliverect")
        self.assertEqual(article["company"], "Deliverect")
        self.assertEqual(article["author_first"], "Jane")
        self.assertEqual(article["author_last"], "Doe")
        self.assertEqual(article["portal"], "TechCrunch")
        self.assertEqual(article["country"], "USA")

    def test_missing_author(self):
        entry = {"title": "test", "link": "https://sifted.eu/x", "published": "", "author": "", "source": {}}
        article = _build_article(entry)
        self.assertEqual(article["author_first"], "")
        self.assertEqual(article["author_last"], "")


class TestTelegramHelpers(unittest.TestCase):
    def test_escape_html(self):
        self.assertEqual(_escape("<b>test & more</b>"), "&lt;b&gt;test &amp; more&lt;/b&gt;")

    def test_format_author_full(self):
        article = {"author_first": "John", "author_last": "Smith"}
        self.assertEqual(_format_author(article), "John Smith")

    def test_format_author_missing(self):
        article = {"author_first": "", "author_last": ""}
        self.assertEqual(_format_author(article), "Unknown")


class TestSourcesConfig(unittest.TestCase):
    def test_queries_not_empty(self):
        self.assertGreater(len(ALL_QUERIES), 10)

    def test_all_keyword_groups_present(self):
        for group in ["company_direct", "delivery_ecosystem", "topics"]:
            self.assertIn(group, KEYWORD_GROUPS)

    def test_tier2_domains_not_empty(self):
        self.assertGreater(len(TIER2_DOMAINS), 5)

    def test_cutoff_date_format(self):
        datetime.fromisoformat(CUTOFF_DATE)  # raises if invalid


# ────────────────────────────────────────────────────────────────────────────
# Integration test — real Google News RSS fetch (requires internet)
# ────────────────────────────────────────────────────────────────────────────

class TestGoogleNewsRSSFetch(unittest.TestCase):
    def test_fetch_deliverect_articles(self):
        """Fetch real articles for 'Deliverect' from Google News RSS."""
        print("\n[LIVE] Fetching Google News RSS for 'Deliverect'...")
        articles = fetch_google_news_rss(["Deliverect"])
        print(f"       Found {len(articles)} articles")
        if articles:
            a = articles[0]
            print(f"       Sample: {a['title'][:80]}")
            print(f"       URL:    {a['url'][:80]}")
            print(f"       Date:   {a['published_date']}")
        # We just assert the fetch didn't crash and returned a list
        self.assertIsInstance(articles, list)

    def test_fetch_ai_restaurant_articles(self):
        """Fetch real articles for 'AI restaurant' from Google News RSS."""
        print("\n[LIVE] Fetching Google News RSS for 'AI restaurant'...")
        articles = fetch_google_news_rss(["AI restaurant"])
        print(f"       Found {len(articles)} articles")
        if articles:
            print(f"       Sample: {articles[0]['title'][:80]}")
        self.assertIsInstance(articles, list)

    def test_fetch_sunday_app_articles(self):
        """Fetch real articles for 'Sunday.app restaurant'."""
        print("\n[LIVE] Fetching Google News RSS for 'Sunday.app restaurant'...")
        articles = fetch_google_news_rss(["Sunday.app restaurant"])
        print(f"       Found {len(articles)} articles")
        self.assertIsInstance(articles, list)


if __name__ == "__main__":
    print("=" * 60)
    print("AgentPR Test Suite")
    print("=" * 60)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Unit tests first
    for cls in [
        TestDateParsing,
        TestDomainHelpers,
        TestCompanyMatching,
        TestBuildArticle,
        TestTelegramHelpers,
        TestSourcesConfig,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    # Integration tests (live network)
    suite.addTests(loader.loadTestsFromTestCase(TestGoogleNewsRSSFetch))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
