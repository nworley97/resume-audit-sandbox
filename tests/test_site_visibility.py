"""Hidden-site mode must block acquisition without locking out current customers."""
import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from flask import request

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['TEST_MODE'] = 'true'
os.environ['OPENAI_API_KEY'] = ''
os.environ['SESSION_COOKIE_SECURE'] = 'false'

from app import app
from authz import _RATE_BUCKETS
from db import Base, SessionLocal, engine
from models import JobDescription, PasswordResetToken, Tenant, User
from subscription_models import PendingSignup
from mobile_demo import DEV_MOBILE_DEMO_SLUG


class SiteVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.visibility = patch.dict(app.config, SITE_HIDDEN=True)
        self.visibility.start()
        self.addCleanup(self.visibility.stop)
        Base.metadata.create_all(engine)
        self.addCleanup(self.clean_database)
        _RATE_BUCKETS.clear()
        db = SessionLocal()
        tenant = Tenant(slug='hidden-test', display_name='Existing customer')
        db.add(tenant)
        db.flush()
        user = User(username='existing@example.com', tenant_id=tenant.id, role='admin')
        user.set_pw('Existing-password-123')
        db.add(user)
        db.flush()
        db.add(PasswordResetToken(user_id=user.id, token='existing-reset',
                                 expires_at=datetime.utcnow() + timedelta(hours=1)))
        db.add(JobDescription(code='OPEN', tenant_id=tenant.id, title='Existing job',
                              status='open', html='<p>Apply for this existing job.</p>'))
        db.commit()
        db.close()
        self.client = app.test_client()

    @staticmethod
    def clean_database():
        SessionLocal.remove()
        Base.metadata.drop_all(engine)
        engine.dispose()

    def login(self):
        response = self.client.post('/login', data={
            'username': 'existing@example.com', 'password': 'Existing-password-123'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/hidden-test/recruiter', response.location)

    def test_home_shows_login_without_marketing_or_signup(self):
        for host in ('https://alterasf.com', 'https://app.alterasf.com', 'https://resume-audit-sandbox.onrender.com'):
            response = self.client.get('/', base_url=host, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Sign in to your account', response.data)
            self.assertNotIn(b'Screen Faster', response.data)
            self.assertNotIn(b'/billing/signup', response.data)
            self.assertIn(b'name="robots" content="noindex', response.data)
            self.assertIn('noindex', response.headers['X-Robots-Tag'])
            self.assertIn('no-store', response.headers['Cache-Control'])

    def test_marketing_routes_and_demo_are_unavailable(self):
        for path in ('/about', '/product', '/pricing', '/contact', '/billing/pricing',
                     '/billing/enterprise', '/billing/notifications-demo',
                     '/mobile-demo/' + DEV_MOBILE_DEMO_SLUG):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertIn('noindex', response.headers['X-Robots-Tag'])
                response.close()
        with patch('resend.Emails.send') as send:
            self.assertEqual(self.client.post('/contact', json={'message': 'not sent'}).status_code, 404)
            send.assert_not_called()

    def test_direct_and_stale_registration_cannot_create_accounts_or_payments(self):
        with self.client.session_transaction() as state:
            state['signup_data'] = {'email': 'new@example.com', 'plan_tier': 'pro', 'password': 'stale'}
        with patch('billing_fulfillment.create_checkout') as checkout:
            for path in ('/billing/signup', '/billing/checkout'):
                for method in ('GET', 'POST'):
                    response = self.client.open(path, method=method, data={
                        'email': 'new@example.com', 'password': 'New-password-123',
                        'company_name': 'New company', 'plan_tier': 'free'})
                    self.assertEqual(response.status_code, 403)
                    self.assertIn(b'New registrations are temporarily unavailable', response.data)
            checkout.assert_not_called()
        db = SessionLocal()
        self.assertEqual(db.query(User).count(), 1)
        self.assertEqual(db.query(Tenant).count(), 1)
        self.assertEqual(db.query(PendingSignup).count(), 0)
        db.close()

    def test_existing_web_login_dashboard_settings_and_billing_work(self):
        self.login()
        for path in ('/', '/hidden-test/recruiter', '/hidden-test/settings', '/billing/account'):
            with self.subTest(path=path):
                response = self.client.get(path, follow_redirects=True)
                self.assertEqual(response.status_code, 200)
                self.assertIn('noindex', response.headers['X-Robots-Tag'])
        self.assertEqual(self.client.get('/api/settings').status_code, 200)

    def test_existing_mobile_login_and_jobs_work(self):
        self.assertEqual(self.client.post('/api/mobile/auth/login', json={
            'email': 'existing@example.com', 'password': 'Existing-password-123'}).status_code, 200)
        self.assertEqual(self.client.get('/api/mobile/auth/me').status_code, 200)
        self.assertEqual(self.client.get('/api/mobile/hidden-test/jobs').status_code, 200)

    def test_password_recovery_and_direct_applications_remain_available(self):
        for path in ('/forgot-password', '/reset-password/existing-reset', '/hidden-test/jobs',
                     '/hidden-test/apply/OPEN', '/apply/OPEN', '/privacy', '/terms'):
            with self.subTest(path=path):
                with self.client.get(path, follow_redirects=True) as response:
                    self.assertEqual(response.status_code, 200)
                    self.assertIn('noindex', response.headers['X-Robots-Tag'])

    def test_payment_callbacks_and_webhooks_still_reach_their_handlers(self):
        # These endpoints must stay reachable for previously opened/paid checkouts.
        for path, method in (('/billing/payment-success', 'GET'), ('/billing/payment-cancel', 'GET'),
                             ('/billing/api/check-account-status', 'GET'), ('/billing/webhooks/stripe', 'POST')):
            with app.test_request_context(path, method=method):
                endpoint = request.endpoint
            with patch.dict(app.view_functions, {endpoint: lambda: ('existing payment handler', 200)}):
                self.assertEqual(self.client.open(path, method=method).data, b'existing payment handler')

    def test_robots_allows_reading_noindex_and_assets_errors_are_excluded(self):
        response = self.client.get('/robots.txt')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b'User-agent: *\nDisallow:\n')
        for path in ('/static/img/favicon.ico', '/not-a-real-page', '/billing/signup'):
            with self.client.get(path) as resource:
                self.assertIn('noindex', resource.headers['X-Robots-Tag'])

    def test_disabling_mode_restores_marketing_and_signup(self):
        app.config['SITE_HIDDEN'] = False
        for path in ('/', '/pricing', '/billing/signup'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('X-Robots-Tag', response.headers)
        self.assertIn(b'/billing/signup', self.client.get('/login').data)
