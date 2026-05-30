#!/usr/bin/env python3
"""Tests pinning the public-web-deploy force-route corpus (ADR public-web-deploy).

Positive corpus: phrasings of public-deploy intent that MUST force-route to
`public-web-deploy`. Negative corpus: idiomatic phrasings that overlap on
low-specificity trigger words ("go live", "static site", "use my domain",
"set up https", "make it public", "public website") but mean something else,
and MUST NOT force-route to `public-web-deploy`.

Low-specificity idiom triggers are gated by a POSITIVE companion-word
requirement (a deploy/host term must sit near the trigger), not a blocklist —
this is what keeps the negative corpus falling through. The corpus is the
contract: if a phrase fails, fix the trigger/guard, do not drop the case.
See `adr/public-web-deploy.md`.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "pre-route.py"


def _route(phrase: str) -> dict:
    """Invoke pre-route.py CLI and parse JSON output."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--request", phrase, "--json-compact"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"pre-route.py exited {proc.returncode}: {proc.stderr}"
    return json.loads(proc.stdout)


# Positive corpus: every phrase MUST force-route to public-web-deploy.
POSITIVE_CORPUS = [
    # Required true positives from the task spec
    "put my website online",
    "deploy my site to my domain",
    "set up nginx for my public site",
    "host this static site publicly",
    "put this online",
    # Idiom triggers WITH a deploy companion in-window (must survive the gate)
    "set up https on my public nginx site",
    "host a website for the domain model handbook",
    "deploy website for the domain expertise portal",
    "deploy website from this repo to my domain",
    "use my domain to deploy this site from the repo",
    "host a website on my vps with nginx",
    "host a website for my domain online",
    "go live with this website on a droplet",
    "host a website publicly with caddy",
    "deploy website to the internet with nginx",
    "point my domain at this site and go live",
    # "deploy site/website" is unambiguous on its own (not companion-gated)
    "deploy my site",
    "deploy my site to vercel",
    "deploy my site to netlify",
    "deploy my site to fly.io",
    "go live on fly.io",
    "set up https for my public website",
    "go live with our launch website on cloudflare",
    "use my domain to host the site publicly",
    # site-TYPE nouns (blog/docs/app) are legit deploy targets, must NOT suppress
    "deploy my blog website to my domain",
    "deploy my docs website to my domain",
    "deploy my app website to my domain",
    # verb-only idiom triggers confirmed by a plain "site"/"website" companion
    "set up https for my website",
    "go live with my website",
    "use my domain for my website",
    # "make ... public" deploy family (trigger "make public")
    "make my website public",
    "make my site public",
    "make this website public",
    # managed static hosting (GitHub/GitLab/Cloudflare Pages) is in scope
    "make my website public on github pages",
    "make my website public on gitlab pages with a custom domain",
    "make my website public on cloudflare pages",
    # common deploy-target nouns (portfolio/homepage/landing page)
    "set up https for my portfolio",
    "make my portfolio public",
    "make my homepage public",
    "go live with my portfolio",
    "deploy my landing page",
    "deploy my landing page to vercel",
    "host my landing page online",
]


# Negative corpus: every phrase MUST NOT force-route to public-web-deploy.
NEGATIVE_CORPUS = [
    # Required false cases from the task spec
    "use my domain knowledge to design the schema",
    "go live on twitch",
    "set up https certificate validation in the test suite",
    "deploy the website unit tests",
    "make it public on npm",
    # "make ... public" visibility ops (code/package/repo), not a web deploy
    "make the repo public",
    "make this method public",
    "make the class public",
    "make website repo public on github",
    "make website code public",
    "make this package public on npm",
    "make this gist public",
    # "static site" without deploy intent (edit/build/discuss)
    "add search to this static site",
    "fix the CSS on my static site",
    "write docs for this static site",
    "review this static site architecture",
    "how do static sites compare to dynamic sites",
    "optimize images on my static site",
    "migrate this blog to a static site",
    # "go live" / "public website" idioms without deploy intent
    "go live with this presentation",
    "go live on youtube",
    "make the copy better on my public website",
    "review accessibility of my public website",
    # generic companions (server/production/publish) must NOT satisfy the gate
    "go live with the launch deck on production",
    "set up https docs for the server team",
    "make it public and publish the report",
    "static site generation in production CI",
    # high-specificity triggers with local/test/store intent (skill not_for)
    "host a website locally for testing",
    "host a website on localhost for QA",
    "website online store checkout bug",
    # companion-overload: an overloaded companion (public/domain/cloudflare/https)
    # near a build/edit/discuss verb must still fall through (defense-in-depth)
    "compare static site generators for public docs",
    "cloudflare static site caching bug",
    "set up https examples for the public api docs",
    "review this public website for domain model terminology",
    # last-word prefix overmatch ("deploy site" matches "deploy sitemap/sitecore")
    "public website sitemap generation",
    "deploy sitecore upgrade",
    "deploy sitemap.xml to the repo",
    # site maintenance with a web companion nearby (build/edit/debug, not publish)
    "cloudflare static site image optimization",
    "cloudflare static site analytics setup",
    "static site performance tuning on my domain",
    "static site content audit on my domain",
    # "work on an already-public site" (no deploy companion) must fall through
    "translate my public site to spanish",
    "localize my public site for germany",
    "rebrand my public site",
    "add a cookie banner to my public site",
    "retheme the deploy site",
    "update the deploy site branding",
    "public site localization plan",
    # localization with a deploy companion (domain) nearby still falls through
    "translate my public site on my domain to spanish",
    "localize my public site on my domain for germany",
    # "landing page" / "portfolio" content work (no deploy companion) falls through
    "edit my landing page",
    "write copy for my landing page",
    "redesign the landing page",
    "rebrand my portfolio site",
]


@pytest.mark.parametrize("phrase", POSITIVE_CORPUS)
def test_positive_corpus_force_routes_to_public_web_deploy(phrase: str) -> None:
    """Each public-deploy phrasing must force-route to public-web-deploy."""
    result = _route(phrase)
    assert result["skill"] == "public-web-deploy", (
        f"phrase {phrase!r} routed to skill={result.get('skill')!r}, expected public-web-deploy. full result: {result}"
    )
    assert result["match_type"] == "force_route", (
        f"phrase {phrase!r} matched with match_type={result.get('match_type')!r}, "
        f"expected force_route. full result: {result}"
    )


@pytest.mark.parametrize("phrase", NEGATIVE_CORPUS)
def test_negative_corpus_does_not_force_route_to_public_web_deploy(phrase: str) -> None:
    """Each idiomatic phrasing must not force-route to public-web-deploy."""
    result = _route(phrase)
    is_force_route = result.get("skill") == "public-web-deploy" and result.get("match_type") == "force_route"
    assert not is_force_route, f"phrase {phrase!r} incorrectly force-routed to public-web-deploy. full result: {result}"
