"""Upgrade regressions for the production schema that was left at revision 0003."""
import io
import os
import re
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[1]


def config(output=None):
    cfg = Config(str(ROOT / 'alembic.ini'), output_buffer=output)
    cfg.set_main_option('script_location', str(ROOT / 'migrations'))
    return cfg


class MigrationUpgradeTests(unittest.TestCase):
    def test_postgres_upgrade_can_store_each_revision_before_advancing(self):
        output = io.StringIO()
        with patch.dict(os.environ, DATABASE_URL='postgresql://unused/unused'):
            command.upgrade(config(output), '0003_add_missing_prod_columns:head', sql=True)
        # PostgreSQL enforces Alembic's default VARCHAR(32), unlike SQLite.
        width = 32
        for statement in output.getvalue().split(';'):
            altered = re.search(r'ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR\((\d+)\)', statement)
            if altered:
                width = int(altered.group(1))
            revision = re.search(r"UPDATE alembic_version SET version_num='([^']+)'", statement)
            if revision:
                self.assertLessEqual(len(revision.group(1)), width,
                                     'Migration would exceed the PostgreSQL revision column width')

    def test_upgrade_from_0003_preserves_user_and_creates_settings_table(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            db_path = Path(directory) / 'upgrade.db'
            with patch.dict(os.environ, DATABASE_URL='sqlite:///' + db_path.as_posix()):
                command.upgrade(config(), '0003_add_missing_prod_columns')
                with closing(sqlite3.connect(db_path)) as db:
                    db.execute('INSERT INTO "user" (id,username,pw_hash,role,read_notification_ids) VALUES (1,?,?,?,NULL)',
                               ('migration@example.com', 'unchanged-hash', 'viewer'))
                    db.commit()
                command.upgrade(config(), 'head')
                command.upgrade(config(), 'head')  # repeated deployments are harmless
                with closing(sqlite3.connect(db_path)) as db:
                    self.assertEqual(db.execute('SELECT username,pw_hash,read_notification_ids FROM "user"').fetchone(),
                                     ('migration@example.com', 'unchanged-hash', '[]'))
                    self.assertEqual(db.execute('SELECT count(*) FROM user_settings').fetchone(), (0,))
                    self.assertEqual(db.execute('SELECT version_num FROM alembic_version').fetchone(), ('0005_user_settings',))
