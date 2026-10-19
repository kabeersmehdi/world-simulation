"""The one place the tool touches the network. Tests inject a fake instead."""

import urllib.request

class NotConfigured(Exception):
    """An optional source has no key or backend. The runner reports it as skipped, not failed."""


USER_AGENT = "Mozilla/5.0 (world-simulation research tool; +https://github.com/kabeersmehdi/world-simulation)"


def fetch_text(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")
