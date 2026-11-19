"""Temporary public-site closure without interrupting existing account workflows."""
import os

from flask import Response, current_app, redirect, render_template, request, url_for
from flask_login import current_user


MARKETING_ENDPOINTS = frozenset({
    'about', 'product_page', 'contact_page', 'pricing_page',
    'billing.pricing', 'billing.enterprise', 'billing.notifications_demo',
    'mobile_demo.show_mobile_demo',
})
REGISTRATION_ENDPOINTS = frozenset({'billing.signup', 'billing.checkout'})


def install_site_visibility(app):
    app.config['SITE_HIDDEN'] = os.getenv('SITE_HIDDEN', 'false').strip().lower() in {'1', 'true', 'yes'}

    @app.context_processor
    def visibility_context():
        return {'site_hidden': current_app.config['SITE_HIDDEN']}

    @app.before_request
    def restrict_public_site():
        if not current_app.config['SITE_HIDDEN']:
            return None
        if request.endpoint in REGISTRATION_ENDPOINTS:
            # Block both form display and direct submissions, including old checkout sessions.
            # Payment callbacks/webhooks remain available to honor payments already opened.
            return render_template('site_unavailable.html', registration=True), 403
        if request.endpoint in MARKETING_ENDPOINTS:
            return render_template('site_unavailable.html', registration=False), 404
        if request.endpoint == 'home' and not current_user.is_authenticated:
            return redirect(url_for('login'))

    @app.after_request
    def exclude_from_search(response):
        if current_app.config['SITE_HIDDEN']:
            # Applies to HTML, PDFs, assets, redirects, and errors on every served hostname.
            response.headers['X-Robots-Tag'] = 'noindex, nofollow, noarchive, nosnippet'
            if response.mimetype == 'text/html' or 300 <= response.status_code < 400:
                response.headers['Cache-Control'] = 'private, no-store, max-age=0'
        return response

    @app.get('/robots.txt')
    def robots_txt():
        # Crawlers must fetch URLs to see noindex; Disallow: / prevents de-indexing.
        return Response('User-agent: *\nDisallow:\n', mimetype='text/plain')
