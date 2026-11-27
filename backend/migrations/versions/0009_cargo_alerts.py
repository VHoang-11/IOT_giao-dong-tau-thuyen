"""Cảnh báo hầm hàng: cargo_hold_configs (cấu hình hầm/ngưỡng) + cargo_alerts (vòng đời ACK/CLEARED)

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'cargo_hold_configs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('device_id', sa.String(length=64), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('vessel_type', sa.String(length=64), nullable=True),
        sa.Column('cargo_type', sa.String(length=64), nullable=True),
        sa.Column('cargo_hold_depth_mm', sa.Float(), nullable=True),
        sa.Column('water_sensor_full_scale_mm', sa.Float(), nullable=True),
        sa.Column('sensor_calibrated', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('thresholds', sa.JSON(), nullable=True),
        sa.Column('updated_by', sa.String(length=64), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_cargo_hold_configs_device_id', 'cargo_hold_configs', ['device_id'], unique=True)
    op.create_table(
        'cargo_alerts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('device_id', sa.String(length=64), nullable=False),
        sa.Column('parent_device_id', sa.String(length=64), nullable=True),
        sa.Column('metric', sa.String(length=16), nullable=False),
        sa.Column('state', sa.String(length=32), nullable=False),
        sa.Column('level', sa.String(length=32), nullable=False),
        sa.Column('max_level', sa.String(length=32), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('peak_value', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=8), nullable=False),
        sa.Column('source_mode', sa.String(length=32), nullable=False),
        sa.Column('data_class', sa.String(length=24), nullable=False),
        sa.Column('threshold_warning', sa.Float(), nullable=True),
        sa.Column('threshold_critical', sa.Float(), nullable=True),
        sa.Column('threshold_version', sa.String(length=64), nullable=False),
        sa.Column('last_boot_id', sa.String(length=64), nullable=False),
        sa.Column('last_seq', sa.Integer(), nullable=False),
        sa.Column('opened_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('acked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acked_by', sa.String(length=64), nullable=True),
        sa.Column('cleared_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('escalated', sa.Boolean(), nullable=False),
    )
    op.create_index('ix_cargo_alerts_device_id', 'cargo_alerts', ['device_id'])
    op.create_index('ix_cargo_alerts_parent_device_id', 'cargo_alerts', ['parent_device_id'])
    op.create_index('uq_cargo_alert_open', 'cargo_alerts', ['device_id', 'metric'], unique=True,
                    sqlite_where=sa.text("state != 'CLEARED'"), postgresql_where=sa.text("state != 'CLEARED'"))


def downgrade() -> None:
    op.drop_index('uq_cargo_alert_open', table_name='cargo_alerts')
    op.drop_index('ix_cargo_alerts_parent_device_id', table_name='cargo_alerts')
    op.drop_index('ix_cargo_alerts_device_id', table_name='cargo_alerts')
    op.drop_table('cargo_alerts')
    op.drop_index('ix_cargo_hold_configs_device_id', table_name='cargo_hold_configs')
    op.drop_table('cargo_hold_configs')
