"""Origin guard for cookie-authenticated browser requests; no live session."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
from urllib.parse import urlsplit

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from live_validate import guarded_route


class BrowserGuard(unittest.TestCase):
    def test_foreign_origins_are_aborted_before_authenticated_fetch(self):
        for url in ('https://external.invalid/image','http://lab.invalid/d/x',
                    'https://lab.invalid:444/d/x','https://lab.invalid.external.invalid/'):
            route=Mock()
            route.request.url=url
            guarded_route(route,urlsplit('https://lab.invalid'),'test-placeholder')
            route.abort.assert_called_once_with()
            route.fetch.assert_not_called()
            route.fulfill.assert_not_called()
            route.continue_.assert_not_called()

    def test_same_origin_continues_without_buffering_or_injected_credentials(self):
        route=Mock()
        route.request.url='https://lab.invalid/api/query'
        route.request.headers={'authorization':'stale-placeholder','accept':'application/json'}
        guarded_route(route,urlsplit('https://lab.invalid'),'test-placeholder')
        route.abort.assert_not_called()
        route.continue_.assert_called_once_with()
        route.fetch.assert_not_called()
        route.fulfill.assert_not_called()
