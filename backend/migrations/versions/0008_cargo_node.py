"""Multi-Node: bang cargo_telemetry (Cargo Node) + devices.node_type / parent_device_id

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('devices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('node_type', sa.String(length=32), nullable=False, server_default='MOTION'))
        batch_op.add_column(sa.Column('parent_device_id', sa.String(length=64), nullable=True))
        batch_op.create_index('ix_devices_parent_device_id', ['parent_device_id'], unique=False)
    op.create_table(
        'cargo_telemetry',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('device_id', sa.String(length=64), nullable=False),
        sa.Column('boot_id', sa.String(length=64), nullable=False),
        sa.Column('seq', sa.Integer(), nullable=False),
        sa.Column('uptime_ms', sa.Integer(), nullable=False),
        sa.Column('source_mode', sa.String(length=32), nullable=False),
        sa.Column('sensor_ok', sa.Boolean(), nullable=False),
        sa.Column('cargo_water_pct', sa.Float(), nullable=True),
        sa.Column('cargo_temp_c', sa.Float(), nullable=True),
        sa.Column('cargo_humidity_pct', sa.Float(), nullable=True),
        sa.Column('reported_parent_device_id', sa.String(length=64), nullable=True),
        sa.Column('server_rx_time', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('device_id', 'boot_id', 'seq', name='uq_cargo_dedup'),
    )
    op.create_index('ix_cargo_telemetry_device_id', 'cargo_telemetry', ['device_id'])
    op.create_index('ix_cargo_dev_rx', 'cargo_telemetry', ['device_id', 'server_rx_time'])


def downgrade() -> None:
    op.drop_index('ix_cargo_dev_rx', table_name='cargo_telemetry')
    op.drop_index('ix_cargo_telemetry_device_id', table_name='cargo_telemetry')
    op.drop_table('cargo_telemetry')
    with op.batch_alter_table('devices', schema=None) as batch_op:
        batch_op.drop_index('ix_devices_parent_device_id')
        batch_op.drop_column('parent_device_id')
        batch_op.drop_column('node_type')
