"""alarm identity: (device_id, boot_id, alarm_id) thay cho alarm_id unique

Bang `alarms` chua tung duoc ghi o 0001 (chi M3-03 moi ghi), nen drop + create la an toan.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def _enums():
    lvl = sa.Enum('NORMAL', 'CAUTION', 'WARNING', 'CRITICAL', name='alarmlevel', native_enum=False, length=32)
    state = sa.Enum('ACTIVE', 'ACKED', 'CLEARED', name='alarmstate', native_enum=False, length=32)
    cls = sa.Enum('NORMAL', 'HIGH_ROLL', 'PERSISTENT_OFFSET', 'AMPLITUDE_GROWTH', 'UNKNOWN', 'FAULT',
                  name='motionclass', native_enum=False, length=32)
    src = sa.Enum('SENSOR', 'SIMULATION', name='sourcemode', native_enum=False, length=32)
    return lvl, state, cls, src


def _common_columns():
    lvl, state, cls, src = _enums()
    return [
        sa.Column('device_id', sa.String(length=64), nullable=False),
        sa.Column('voyage_id', sa.String(length=64), nullable=True),
        sa.Column('state', state, nullable=False),
        sa.Column('level', lvl, nullable=False),
        sa.Column('max_level', lvl, nullable=False),
        sa.Column('motion_class', cls, nullable=True),
        sa.Column('source_mode', src, nullable=False),
        sa.Column('opened_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('acked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acked_by', sa.String(length=64), nullable=True),
        sa.Column('cleared_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('escalated', sa.Boolean(), nullable=False),
        sa.Column('label', sa.String(length=16), nullable=True),
    ]


def upgrade() -> None:
    op.drop_table('alarms')
    op.create_table(
        'alarms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alarm_id', sa.String(length=64), nullable=False),
        sa.Column('boot_id', sa.String(length=64), nullable=False),
        sa.Column('last_seq', sa.Integer(), nullable=False),
        *_common_columns(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('device_id', 'boot_id', 'alarm_id', name='uq_alarm_identity'),
    )
    with op.batch_alter_table('alarms', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_alarms_alarm_id'), ['alarm_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_alarms_device_id'), ['device_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_alarms_voyage_id'), ['voyage_id'], unique=False)


def downgrade() -> None:
    op.drop_table('alarms')
    op.create_table(
        'alarms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alarm_id', sa.String(length=64), nullable=False),
        *_common_columns(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('alarm_id'),
    )
    with op.batch_alter_table('alarms', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_alarms_device_id'), ['device_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_alarms_voyage_id'), ['voyage_id'], unique=False)
