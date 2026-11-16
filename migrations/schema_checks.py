"""Adopt tables created by the retired request-time schema helper, without DML.

Keep the expected definitions in each revision, independent of application models.
An existing but incompatible table must stop deployment, never be dropped or stamped.
Offline SQL is for fresh tables; adoption requires an online schema inspection.
"""
from alembic import context, op
import sqlalchemy as sa


def create_or_validate_table(name, *columns, indexes=()):
    expected = sa.Table(name, sa.MetaData(), *columns)
    bind = op.get_bind()
    if context.is_offline_mode() or not sa.inspect(bind).has_table(name):
        op.create_table(name, *columns)
        for index_name, column_names in indexes:
            op.create_index(index_name, name, list(column_names))
        return

    inspector = sa.inspect(bind)
    errors = []
    actual_columns = {column['name']: column for column in inspector.get_columns(name)}
    if set(actual_columns) != set(expected.columns.keys()):
        errors.append('column names')
    for column in expected.columns:
        actual = actual_columns.get(column.name)
        if actual is None:
            continue
        expected_type = column.type.compile(dialect=bind.dialect)
        actual_type = actual['type'].compile(dialect=bind.dialect)
        if (actual_type != expected_type or actual['nullable'] != column.nullable
                or actual.get('default') is not None):
            errors.append(f'column {column.name} type/nullability/default')
    if inspector.get_pk_constraint(name)['constrained_columns'] != list(expected.primary_key.columns.keys()):
        errors.append('primary key')
    expected_unique = {tuple(c.columns.keys()) for c in expected.constraints
                       if isinstance(c, sa.UniqueConstraint)}
    actual_unique = {tuple(c['column_names']) for c in inspector.get_unique_constraints(name)}
    if actual_unique != expected_unique:
        errors.append('unique constraints')
    expected_fks = {(tuple(c.columns.keys()), tuple(e.target_fullname for e in c.elements), c.ondelete)
                    for c in expected.foreign_key_constraints}
    actual_fks = {(tuple(c['constrained_columns']),
                   tuple(f"{c['referred_table']}.{col}" for col in c['referred_columns']),
                   c.get('options', {}).get('ondelete')) for c in inspector.get_foreign_keys(name)
                  if c.get('referred_schema') in (None, inspector.default_schema_name)}
    if (actual_fks != expected_fks
            or len(inspector.get_foreign_keys(name)) != len(expected_fks)):
        errors.append('foreign keys')
    actual_indexes = {(i['name'], tuple(i['column_names']), bool(i['unique']))
                      for i in inspector.get_indexes(name) if not i.get('duplicates_constraint')}
    expected_indexes = {(index_name, tuple(column_names), False) for index_name, column_names in indexes}
    if actual_indexes != expected_indexes:
        errors.append('indexes')
    if inspector.get_check_constraints(name):
        errors.append('unexpected check constraints')
    if errors:
        raise RuntimeError(f"Refusing to adopt existing {name}: incompatible {', '.join(errors)}. "
                           "No existing records were changed; review the schema before retrying.")
