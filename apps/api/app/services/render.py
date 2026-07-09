"""Markdown → HTML with a strict sanitize allowlist.

THIS IS A SECURITY BOUNDARY, not a formatting nicety. Release HTML is injected
raw into the embed widget, which runs inside *other companies' apps*. A stored
XSS here is a supply-chain attack on every customer (ARCHITECTURE §9). So:

  markdown --(markdown-it)--> HTML --(nh3 allowlist)--> stored body_html

We sanitize at WRITE time (see Release.body_html) so the read path — widget
feed, public site — never has to trust or re-clean anything.
"""

from __future__ import annotations

import nh3
from markdown_it import MarkdownIt

# Deliberately conservative. No raw HTML passthrough, no <script>/<style>,
# no <img> onerror surface beyond src/alt, links forced to safe schemes.
_ALLOWED_TAGS = {
    "p", "br", "hr",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "em", "del", "code", "pre", "blockquote",
    "ul", "ol", "li",
    "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
}

_ALLOWED_ATTRS = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
    "td": {"align"},
    "th": {"align"},
}

# `commonmark` preset = no inline HTML. We still sanitize afterward as
# defense-in-depth (two independent layers, both must be defeated).
_md = MarkdownIt("commonmark", {"html": False, "linkify": True, "typographer": True})


def render_markdown(md_text: str) -> str:
    """Render untrusted markdown to safe, storable HTML."""
    raw_html = _md.render(md_text or "")
    return nh3.clean(
        raw_html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        url_schemes={"http", "https", "mailto"},
        link_rel="noopener nofollow noreferrer",  # every rendered link is hardened
    )
