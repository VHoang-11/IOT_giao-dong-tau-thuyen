"""telemetry: them muc nuoc, nhiet do, do am ham hang (GPIO 35 & DHT22 GPIO 4)

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('telemetry', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cargo_water_pct', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('cargo_temp_c', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('cargo_humidity_pct', sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('telemetry', schema=None) as batch_op:
        batch_op.drop_column('cargo_humidity_pct')
        batch_op.drop_column('cargo_temp_c')
        batch_op.drop_column('cargo_water_pct')
