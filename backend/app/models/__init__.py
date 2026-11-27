from app.models.tables import (
    Alarm, AlarmEvent, AuditLog, CargoAlert, CargoHoldConfig, CargoTelemetry, Command, Device, DeviceConfigVersion, DeviceHealth, Telemetry, User,
    Voyage,
)

# Import o day de dang ky metadata cho Alembic/create_all va de cac module dung `from app.models import ...`
__all__ = ["Alarm", "AlarmEvent", "AuditLog", "CargoAlert", "CargoHoldConfig", "CargoTelemetry", "Command", "Device", "DeviceConfigVersion", "DeviceHealth",
           "Telemetry", "User", "Voyage"]
