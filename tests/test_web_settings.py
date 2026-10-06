"""Settings contracts use disposable data, never real accounts or email delivery."""
import os
import unittest
from datetime import datetime, timedelta

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['TEST_MODE'] = 'true'
os.environ['OPENAI_API_KEY'] = ''
os.environ['SESSION_COOKIE_SECURE'] = 'false'

from app import app
from db import Base, SessionLocal, engine
from models import User, Tenant, PasswordResetToken
from authz import _RATE_BUCKETS


class WebSettingsTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(self.cleanup_database)
        Base.metadata.create_all(engine)
        _RATE_BUCKETS.clear()
        db = SessionLocal()
        tenant = Tenant(slug='settings-test', display_name='Settings test')
        db.add(tenant)
        db.flush()
        user = User(username='settings@example.com', tenant_id=tenant.id, role='viewer')
        user.set_pw('Old-password-123')
        other = User(username='other@example.com', tenant_id=tenant.id)
        other.set_pw('Other-password-123')
        db.add_all([user, other])
        db.commit()
        self.user_id = user.id
        with app.app_context():
            self.login_id = user.get_id()
        db.close()
        self.client = self.signed_in_client()
        response = self.client.get('/api/settings')
        self.assertEqual(response.status_code, 200)
        self.headers = {'X-CSRF-Token': response.json['csrf_token'], 'Origin': 'http://localhost'}

    def signed_in_client(self):
        client = app.test_client()
        with client.session_transaction() as s:
            s['_user_id'] = self.login_id
            s['_fresh'] = True
            s['tenant_slug'] = 'settings-test'
        return client

    def cleanup_database(self):
        SessionLocal.remove()
        Base.metadata.drop_all(engine)
        engine.dispose()

    def test_profile_fields_persist_and_escape_in_page(self):
        for field, value in [('full_name', '<b>My Name</b>'), ('work_address', '123 Example St\nSuite 2')]:
            result = self.client.patch('/api/settings/profile', json={'field': field, 'value': value}, headers=self.headers)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(self.signed_in_client().get('/api/settings').json['profile'][field], value)
        html = self.client.get('/settings-test/settings').get_data(as_text=True)
        self.assertIn('&lt;b&gt;My Name&lt;/b&gt;', html)
        self.assertNotIn('<b>My Name</b>', html)
        self.assertNotIn('Coming soon', html)
        self.assertNotIn('value="system"', html)

    def test_email_requires_password_and_rejects_duplicate_or_invalid_email(self):
        url = '/api/settings/profile'
        body = {'field': 'email', 'value': 'new@example.com'}
        self.assertEqual(self.client.patch(url, json=body, headers=self.headers).status_code, 400)
        body['current_password'] = 'Old-password-123'
        for value, code in [('bad', 400), ('OTHER@EXAMPLE.COM', 409), ('New@Example.com', 200)]:
            body['value'] = value
            self.assertEqual(self.client.patch(url, json=body, headers=self.headers).status_code, code)
        self.assertEqual(self.client.get('/api/settings').json['profile']['email'], 'new@example.com')

    def test_password_change_revokes_other_sessions_and_reset_links(self):
        stale = self.signed_in_client()
        db = SessionLocal()
        db.add(PasswordResetToken(user_id=self.user_id, token='test-reset', expires_at=datetime.utcnow() + timedelta(hours=1)))
        db.commit()
        db.close()
        body = {'current_password': 'wrong', 'new_password': 'New-password-123', 'confirm_password': 'New-password-123'}
        self.assertEqual(self.client.post('/api/settings/password', json=body, headers=self.headers).status_code, 400)
        body['current_password'] = 'Old-password-123'
        body['confirm_password'] = 'different'
        self.assertEqual(self.client.post('/api/settings/password', json=body, headers=self.headers).status_code, 400)
        body['confirm_password'] = body['new_password']
        self.assertEqual(self.client.post('/api/settings/password', json=body, headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get('/api/settings').status_code, 200)
        self.assertEqual(stale.get('/api/settings').status_code, 401)
        db = SessionLocal()
        self.assertTrue(db.get(User, self.user_id).check_pw('New-password-123'))
        self.assertTrue(db.query(PasswordResetToken).filter_by(token='test-reset').one().used)
        db.close()

    def test_preferences_persist_per_account_and_validate_atomically(self):
        body = {'theme': 'dark', 'email_new_applicant': True, 'site_badge': False}
        result = self.client.patch('/api/settings/preferences', json=body, headers=self.headers)
        self.assertEqual(result.status_code, 200)
        prefs = self.signed_in_client().get('/api/settings').json['preferences']
        for key, value in body.items():
            self.assertEqual(prefs[key], value)
        for invalid in [{'theme': 'system'}, {'site_badge': 'false'}, {'user_id': 2}, {'theme': 'light', 'unknown': True}]:
            self.assertEqual(self.client.patch('/api/settings/preferences', json=invalid, headers=self.headers).status_code, 400)
        self.assertEqual(self.client.get('/api/settings').json['preferences']['theme'], 'dark')
        db = SessionLocal()
        other = db.query(User).filter_by(username='other@example.com').one()
        with app.app_context():
            other_login = other.get_id()
        db.close()
        with self.client.session_transaction() as s:
            s['_user_id'] = other_login
        self.assertEqual(self.client.get('/api/settings').json['preferences']['theme'], 'light')

    def test_writes_require_csrf_and_authentication(self):
        url = '/api/settings/preferences'
        self.assertEqual(self.client.patch(url, json={'theme': 'dark'}).status_code, 403)
        self.assertEqual(self.client.patch(url, json={'theme': 'dark'}, headers={**self.headers, 'Origin': 'https://evil.invalid'}).status_code, 403)
        self.assertEqual(app.test_client().patch(url, json={'theme': 'dark'}).status_code, 401)
        self.assertEqual(self.client.patch('/api/settings/profile', json={'field': 'role', 'value': 'admin'}, headers=self.headers).status_code, 400)
        self.assertEqual(self.client.patch('/api/settings/profile', json={'field': [], 'value': 'admin'}, headers=self.headers).status_code, 400)


if __name__ == '__main__':
    unittest.main()
