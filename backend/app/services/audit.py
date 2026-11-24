"""Nhat ky kiem toan: ghi ai lam gi, luc nao. Chi them, khong sua/xoa."""
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import AuditLog

log = logging.getLogger("svmg.audit")


def audit(db: Session, actor: str, action: str, target: Optional[str] = None,
          detail: Optional[dict[str, Any]] = None) -> AuditLog:
    """Them 1 dong audit vao session (caller commit cung transaction voi thay doi chinh)."""
    row = AuditLog(actor=actor, action=action, target=target, detail=detail)
    db.add(row)
    log.info("audit", extra={"actor": actor, "action": action, "target": target})
    return row
