"""Basisschema

Legt das Schema in einer leeren Datenbank an und übernimmt bestehende
Datenbanken aus der Zeit vor Alembic (ADR-0012): Vorhandene Tabellen bleiben
erhalten und werden auf den Stand dieser Revision gebracht. Das ersetzt die
früheren Sonderfall-Migrationen in `init-db`:

- `workdays`: UNIQUE(user_id, date) entfällt (mehrere Zeitfenster pro Tag),
  end_time wird nullable (laufendes Zeitfenster per "Anfang").
- `users`: Spalten start_date und start_balance (Startdatum mit Übertrag).

Revision ID: 0001
Revises:
Create Date: 2026-10-22 16:51:19.244248

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if 'settings' not in tables:
        op.create_table('settings',
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('value', sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint('key')
        )

    if 'users' not in tables:
        op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('weekly_hours', sa.Float(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('start_balance', sa.Float(), server_default='0', nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
        )
    else:
        _adopt_users(inspector)

    if 'absences' not in tables:
        op.create_table('absences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'date', name='uq_absence_user_date')
        )

    if 'workdays' not in tables:
        op.create_table('workdays',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    else:
        _adopt_workdays(inspector)

    indexes = {ix['name'] for ix in sa.inspect(op.get_bind()).get_indexes('workdays')}
    if 'ix_workdays_user_date' not in indexes:
        with op.batch_alter_table('workdays', schema=None) as batch_op:
            batch_op.create_index('ix_workdays_user_date', ['user_id', 'date'], unique=False)


def _adopt_users(inspector):
    columns = {c['name'] for c in inspector.get_columns('users')}
    with op.batch_alter_table('users', schema=None) as batch_op:
        if 'start_date' not in columns:
            batch_op.add_column(sa.Column('start_date', sa.Date(), nullable=True))
        if 'start_balance' not in columns:
            batch_op.add_column(
                sa.Column('start_balance', sa.Float(), server_default='0', nullable=False)
            )


def _adopt_workdays(inspector):
    has_unique = any(
        uc['name'] == 'uq_workday_user_date'
        for uc in inspector.get_unique_constraints('workdays')
    )
    end_time_required = any(
        c['name'] == 'end_time' and not c['nullable']
        for c in inspector.get_columns('workdays')
    )
    if not (has_unique or end_time_required):
        return
    # SQLite kann Constraints nicht per ALTER TABLE ändern: Batch-Mode baut die
    # Tabelle neu auf und übernimmt Daten und Indizes.
    with op.batch_alter_table('workdays', schema=None, recreate='always') as batch_op:
        if has_unique:
            batch_op.drop_constraint('uq_workday_user_date', type_='unique')
        if end_time_required:
            batch_op.alter_column('end_time', existing_type=sa.Time(), nullable=True)


def downgrade():
    with op.batch_alter_table('workdays', schema=None) as batch_op:
        batch_op.drop_index('ix_workdays_user_date')

    op.drop_table('workdays')
    op.drop_table('absences')
    op.drop_table('users')
    op.drop_table('settings')
