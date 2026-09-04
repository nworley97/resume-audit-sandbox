"""Browser-based mobile product demo.

The page deliberately uses fictional, client-side data.  It is intended for
product walkthroughs and never bypasses tenant authentication or reads
candidate records from the database.
"""

import hmac
import os

from flask import Blueprint, abort, current_app, make_response, render_template


mobile_demo = Blueprint("mobile_demo", __name__)

# This fallback is only active on the Render dev branch (or under tests).  Set
# MOBILE_DEMO_SLUG on Render to rotate the link without changing the code.
DEV_MOBILE_DEMO_SLUG = "preview-61d7c4a9f2e8"


def _configured_demo_slug() -> str | None:
    configured = os.getenv("MOBILE_DEMO_SLUG", "").strip()
    if configured:
        return configured

    render_branch = os.getenv("RENDER_GIT_BRANCH", "").strip().casefold()
    test_mode = os.getenv("TEST_MODE", "").strip().casefold() in {"1", "true", "yes"}
    if render_branch == "dev" or test_mode or current_app.testing:
        return DEV_MOBILE_DEMO_SLUG
    return None


@mobile_demo.get("/mobile-demo/<slug>")
def show_mobile_demo(slug: str):
    expected_slug = _configured_demo_slug()
    if not expected_slug or not hmac.compare_digest(slug, expected_slug):
        abort(404)

    response = make_response(render_template("mobile_demo.html"))
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response
