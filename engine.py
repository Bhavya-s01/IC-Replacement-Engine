"""Core orchestration engine."""

from __future__ import annotations

import logging
import time
import sys
import os
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CATEGORIES, all_category_slugs
from database import Database
from models import Component
from plugins.base import PluginBase

log = logging.getLogger(__name__)


class IngestionEngine:
    def __init__(self, db=None):
        self.db = db or Database()
        self._plugins = {}

    def register_plugin(self, plugin):
        self._plugins[plugin.name] = plugin
        log.info("Registered plugin: %s", plugin.name)

    def remove_plugin(self, name):
        if name in self._plugins:
            del self._plugins[name]

    def list_plugins(self):
        return list(self._plugins.keys())

    def _get_plugin(self, name=None):
        if name:
            if name not in self._plugins:
                raise RuntimeError(f"Plugin '{name}' not registered.")
            return self._plugins[name]
        if not self._plugins:
            raise RuntimeError("No plugins registered.")
        return next(iter(self._plugins.values()))

    def scrape_category(self, category_slug, *, plugin_name=None, max_pages=None, dry_run=False):
        plugin = self._get_plugin(plugin_name)

        cat = CATEGORIES.get(category_slug)
        if not cat:
            log.error("Unknown category: %s", category_slug)
            return 0

        log.info("Starting ingestion for [%s] via plugin [%s]", cat.name, plugin.name)
        start = time.time()

        components = plugin.scrape_category(category_slug, max_pages=max_pages)
        elapsed = time.time() - start

        log.info("Scraped %d components in %.1f s", len(components), elapsed)

        if dry_run:
            log.info("DRY RUN - not saving to database.")
            for c in components[:5]:
                log.info("  %s", c)
            return len(components)

        count = self.db.bulk_upsert(components)
        log.info("Stored %d components in database.", count)
        return count

    def scrape_all(self, *, plugin_name=None, max_pages=None, categories=None):
        slugs = categories or all_category_slugs()
        results = {}

        for slug in slugs:
            try:
                count = self.scrape_category(slug, plugin_name=plugin_name, max_pages=max_pages)
                results[slug] = count
            except Exception as exc:
                log.error("Failed to scrape %s: %s", slug, exc, exc_info=True)
                results[slug] = 0

        log.info("=== Ingestion complete ===")
        for slug, cnt in results.items():
            log.info("  %-20s : %6d components", slug, cnt)
        log.info("  TOTAL              : %6d", sum(results.values()))
        return results

    def status(self):
        return self.db.count_by_category()

    def search(self, **kwargs):
        return self.db.search(**kwargs)

    def close(self):
        self.db.close()
