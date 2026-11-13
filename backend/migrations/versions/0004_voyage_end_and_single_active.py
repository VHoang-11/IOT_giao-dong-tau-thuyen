"""voyage: ended_by + moi thiet bi chi co 1 chuyen ACTIVE (partial unique index)

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('voyages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ended_by', sa.String(length=64), nullable=True))
    op.create_index('uq_voyage_one_active_per_device', 'voyages', ['device_id'], unique=True,
                    sqlite_where=sa.text("status = 'ACTIVE'"), postgresql_where=sa.text("status = 'ACTIVE'"))


def downgrade() -> None:
    op.drop_index('uq_voyage_one_active_per_device', table_name='voyages')
    with op.batch_alter_table('voyages', schema=None) as batch_op:
        batch_op.drop_column('ended_by')
