"""devices: phien ban dac trung thiet bi bao cao; device_configs: ly do thiet bi tu choi

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('devices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('feature_schema_version', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('preprocessing_version', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('feature_count', sa.Integer(), nullable=True))
    with op.batch_alter_table('device_configs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('rejected_reason', sa.String(length=256), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('device_configs', schema=None) as batch_op:
        batch_op.drop_column('rejected_reason')
    with op.batch_alter_table('devices', schema=None) as batch_op:
        batch_op.drop_column('feature_count')
        batch_op.drop_column('preprocessing_version')
        batch_op.drop_column('feature_schema_version')
