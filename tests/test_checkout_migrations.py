"""Reproduce deployed tables ahead of Alembic, with real persisted checkout rows."""
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from models import Tenant
from subscription_models import CheckoutAttempt, CheckoutFulfillment

ROOT = Path(__file__).resolve().parents[1]


class CheckoutMigrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        url = 'sqlite:///' + (Path(self.directory.name) / 'migration.db').as_posix()
        # Optional real PostgreSQL run: isolate every test in its own disposable schema.
        postgres = os.environ.get('MIGRATION_TEST_DATABASE_URL')
        if postgres:
            parsed = sa.engine.make_url(postgres)
            if parsed.host not in ('127.0.0.1', 'localhost') or not parsed.database.startswith('migration_verification'):
                raise RuntimeError('Migration tests require a local migration_verification database')
            admin = sa.create_engine(postgres)
            schema = 'test_' + uuid.uuid4().hex
            with admin.begin() as connection:
                connection.execute(sa.schema.CreateSchema(schema))
            def cleanup():
                with admin.begin() as connection:
                    connection.execute(sa.schema.DropSchema(schema, cascade=True))
                admin.dispose()
            self.addCleanup(cleanup)
            url = parsed.update_query_dict({'options': '-csearch_path=' + schema}).render_as_string(hide_password=False)
        environment = patch.dict(os.environ, DATABASE_URL=url)
        environment.start()
        self.addCleanup(environment.stop)
        self.engine = sa.create_engine(url)
        self.addCleanup(self.engine.dispose)
        self.cfg = Config(str(ROOT / 'alembic.ini'))
        self.cfg.set_main_option('script_location', str(ROOT / 'migrations'))
        command.upgrade(self.cfg, '0005_user_settings')
        with self.engine.begin() as connection:
            connection.execute(Tenant.__table__.insert().values(id=1, slug='synthetic', display_name='Synthetic'))

    def create_legacy_tables(self, names=('checkout_fulfillment', 'checkout_attempt')):
        tables = [m.__table__ for m in (CheckoutFulfillment, CheckoutAttempt) if m.__tablename__ in names]
        for table in tables:
            table.create(self.engine)
        with self.engine.begin() as connection:
            if 'checkout_fulfillment' in names:
                connection.execute(CheckoutFulfillment.__table__.insert().values(
                    session_id='cs_preserved', tenant_id=1, kind='plan'))
            if 'checkout_attempt' in names:
                connection.execute(CheckoutAttempt.__table__.insert().values(
                    id='preserved', scope='signup:1', active_scope='signup:1',
                    session_id='cs_pending', parameters={'immutable': True}, signup={'pw_hash': 'synthetic-hash'}))

    def snapshot(self, names):
        with self.engine.connect() as connection:
            return {name: list(connection.execute(sa.text('SELECT * FROM ' + name)).mappings()) for name in names}

    def assert_upgrade_preserves(self, names):
        before = self.snapshot(names)
        command.upgrade(self.cfg, 'head')
        command.upgrade(self.cfg, 'head')
        self.assertEqual(before, self.snapshot(names))
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(sa.text('SELECT version_num FROM alembic_version')).scalar(),
                             '0007_checkout_attempt')
        with self.assertRaises(sa.exc.IntegrityError), self.engine.begin() as connection:
            connection.execute(CheckoutAttempt.__table__.insert().values(
                id='duplicate', scope='signup:1', active_scope='signup:1', parameters={}))

    def test_existing_tables_and_checkout_records_are_preserved(self):
        self.create_legacy_tables()
        self.assert_upgrade_preserves(('checkout_fulfillment', 'checkout_attempt', 'tenant'))

    def test_only_fulfillment_exists(self):
        self.create_legacy_tables(('checkout_fulfillment',))
        command.upgrade(self.cfg, 'head')
        self.assertEqual(self.snapshot(('checkout_fulfillment',))['checkout_fulfillment'][0]['session_id'], 'cs_preserved')
        self.assertTrue(sa.inspect(self.engine).has_table('checkout_attempt'))

    def test_only_attempt_exists(self):
        self.create_legacy_tables(('checkout_attempt',))
        self.assert_upgrade_preserves(('checkout_attempt', 'tenant'))

    def test_incompatible_columns_stop_without_changing_records(self):
        with self.engine.begin() as connection:
            connection.execute(sa.text('CREATE TABLE checkout_fulfillment (session_id VARCHAR(255) PRIMARY KEY, evidence TEXT)'))
            connection.execute(sa.text("INSERT INTO checkout_fulfillment VALUES ('cs_preserved', 'keep this')"))
        before = self.snapshot(('checkout_fulfillment', 'alembic_version'))
        with self.assertRaisesRegex(RuntimeError, 'Refusing to adopt existing checkout_fulfillment'):
            command.upgrade(self.cfg, 'head')
        self.assertEqual(before, self.snapshot(('checkout_fulfillment', 'alembic_version')))

    def test_missing_unique_constraint_blocks_adoption(self):
        self.create_legacy_tables(('checkout_fulfillment',))
        metadata = sa.MetaData()
        table = CheckoutAttempt.__table__.to_metadata(metadata)
        for constraint in list(table.constraints):
            if isinstance(constraint, sa.UniqueConstraint):
                table.constraints.remove(constraint)
        table.create(self.engine)
        with self.assertRaisesRegex(RuntimeError, 'unique constraints'):
            command.upgrade(self.cfg, 'head')

    def test_missing_foreign_key_blocks_adoption(self):
        table = sa.Table('checkout_fulfillment', sa.MetaData(),
                         sa.Column('session_id', sa.String(255), primary_key=True),
                         sa.Column('tenant_id', sa.Integer, nullable=False),
                         sa.Column('kind', sa.String(20), nullable=False),
                         sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
        table.create(self.engine)
        with self.assertRaisesRegex(RuntimeError, 'foreign keys'):
            command.upgrade(self.cfg, 'head')

    def test_wrong_timestamp_timezone_blocks_postgres_adoption(self):
        if self.engine.dialect.name != 'postgresql':
            self.skipTest('SQLite does not store timestamp timezone types')
        self.create_legacy_tables()
        with self.engine.begin() as connection:
            connection.execute(sa.text('ALTER TABLE checkout_fulfillment ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE'))
        before = self.snapshot(('checkout_fulfillment', 'checkout_attempt', 'alembic_version'))
        with self.assertRaisesRegex(RuntimeError, 'created_at'):
            command.upgrade(self.cfg, 'head')
        self.assertEqual(before, self.snapshot(('checkout_fulfillment', 'checkout_attempt', 'alembic_version')))
