import enum


class SourceMode(str, enum.Enum):
    SENSOR = "SENSOR"
    SIMULATION = "SIMULATION"


class MotionClass(str, enum.Enum):
    NORMAL = "NORMAL"
    HIGH_ROLL = "HIGH_ROLL"
    PERSISTENT_OFFSET = "PERSISTENT_OFFSET"
    AMPLITUDE_GROWTH = "AMPLITUDE_GROWTH"
    UNKNOWN = "UNKNOWN"
    FAULT = "FAULT"


class AlarmLevel(str, enum.Enum):
    NORMAL = "NORMAL"
    CAUTION = "CAUTION"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlarmState(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ACKED = "ACKED"
    CLEARED = "CLEARED"


class CommandName(str, enum.Enum):
    set_profile = "set_profile"
    set_threshold = "set_threshold"
    calibrate_zero = "calibrate_zero"
    mute_alarm = "mute_alarm"
    start_voyage = "start_voyage"
    stop_voyage = "stop_voyage"
    restart_device = "restart_device"


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
