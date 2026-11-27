import enum


class SourceMode(str, enum.Enum):
    SENSOR = "SENSOR"
    SIMULATION = "SIMULATION"


class NodeType(str, enum.Enum):
    """Multi-Node: MOTION = ESP32 do dao dong (telemetry/event); CARGO = ESP32 ham hang (chi topic cargo)."""
    MOTION = "MOTION"
    CARGO = "CARGO"


class MotionClass(str, enum.Enum):
    NORMAL = "NORMAL"
    HIGH_ROLL = "HIGH_ROLL"
    PERSISTENT_OFFSET = "PERSISTENT_OFFSET"
    AMPLITUDE_GROWTH = "AMPLITUDE_GROWTH"
    UNKNOWN = "UNKNOWN"
    FAULT = "FAULT"


# Lop phan loai THAT SU (svmg_class_t 0..3). UNKNOWN/FAULT la "khong ket luan", khong phai mot lop: hai mo hinh cung
# UNKNOWN KHONG duoc tinh la dong thuan (vd. firmware chua nap RF luon tra UNKNOWN).
CLASSIFIED_MOTION_CLASSES = frozenset({MotionClass.NORMAL, MotionClass.HIGH_ROLL, MotionClass.PERSISTENT_OFFSET,
                                       MotionClass.AMPLITUDE_GROWTH})


def is_classified_pair(rf, baseline) -> bool:
    """True khi CA HAI nhan la lop phan loai hop le -> cap duoc dua vao ty le dong thuan."""
    return rf in CLASSIFIED_MOTION_CLASSES and baseline in CLASSIFIED_MOTION_CLASSES


class AlarmLevel(str, enum.Enum):
    NORMAL = "NORMAL"
    CAUTION = "CAUTION"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlarmState(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ACKED = "ACKED"
    CLEARED = "CLEARED"


class AlarmLabel(str, enum.Enum):
    """Danh gia sau su viec (G4): canh bao do dung / sai / chua ro. Chi phuc vu danh gia, KHONG anh huong vong doi."""
    TRUE_ALARM = "TRUE_ALARM"
    FALSE_ALARM = "FALSE_ALARM"
    UNCLEAR = "UNCLEAR"


class CommandName(str, enum.Enum):
    set_profile = "set_profile"
    set_threshold = "set_threshold"
    calibrate_zero = "calibrate_zero"
    mute_alarm = "mute_alarm"
    start_voyage = "start_voyage"
    stop_voyage = "stop_voyage"
    restart_device = "restart_device"
    ack_alarm = "ack_alarm"  # backend -> thiet bi khi nguoi truc ACK tren dashboard (M1 de xuat A2); chi gui qua POST /alarms/{id}/ack


class CommandState(str, enum.Enum):
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"
    TIMEOUT = "TIMEOUT"


class Role(str, enum.Enum):
    OPERATOR = "OPERATOR"
    SUPERVISOR = "SUPERVISOR"
    ADMIN = "ADMIN"


class VoyageStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"


class DeviceState(str, enum.Enum):
    online = "online"
    offline = "offline"
