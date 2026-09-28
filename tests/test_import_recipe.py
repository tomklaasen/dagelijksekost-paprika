#!/usr/bin/env python3
"""Tests for the directions fallback policy in import_recipe.py.

Parsing a real page is covered by the dagelijksekost-scraper package; these tests only pin down
which source this script prefers.

Run with: uv run python -m unittest discover tests
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from import_recipe import scrape_directions

_payload = json.dumps({"recipeParts": [{"title": None, "instructions": [
    {"part": 1, "step": 1, "description": "Stap uit de payload.", "tip": None},
]}]})
PAGE_WITH_PAYLOAD    = f"<html><script>self.__next_f.push([1,{json.dumps(_payload)}])</script></html>"
PAGE_WITHOUT_PAYLOAD = "<html><body>geen payload</body></html>"


class FakeScraper:
    """Stands in for a recipe_scrapers scraper, which can only be built from a full page."""

    def __init__(self, instructions="Stap van de scraper."):
        self._instructions = instructions

    def instructions(self):
        if self._instructions is None:
            raise ValueError("no instructions in this page")
        return self._instructions


class ScrapeDirectionsTest(unittest.TestCase):
    def test_prefers_the_payload_over_the_json_ld_steps(self):
        directions = scrape_directions(FakeScraper(), PAGE_WITH_PAYLOAD)

        self.assertEqual("Stap uit de payload.", directions)

    def test_warns_and_falls_back_to_the_scraper_when_the_payload_is_missing(self):
        with self.assertLogs("import_recipe", level="WARNING"):
            directions = scrape_directions(FakeScraper(), PAGE_WITHOUT_PAYLOAD)

        self.assertEqual("Stap van de scraper.", directions)

    def test_returns_an_empty_string_when_the_scraper_fails(self):
        with self.assertLogs("import_recipe", level="WARNING"):
            directions = scrape_directions(FakeScraper(instructions=None), PAGE_WITHOUT_PAYLOAD)

        self.assertEqual("", directions)


if __name__ == "__main__":
    unittest.main()
