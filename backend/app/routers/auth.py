from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.db import get_db
from app.core.security import create_access_token, get_current_user, require_role
from app.models import User
from app.models.enums import Role
from app.schemas.auth import PasswordChange, TokenOut, UserCreate, UserOut, UserUpdate
from app.services import auth as svc

router = APIRouter(tags=["auth"])


@router.post("/api/v1/auth/login", response_model=TokenOut)
async def login(request: Request, form: OAuth2PasswordRequestForm = Depends(),
                db: Session = Depends(get_db)) -> TokenOut:
    """Dang nhap (form: username, password) -> JWT. Dung duoc voi nut Authorize cua /docs."""
    ip = request.client.host if request.client else "?"
    try:
        # scrypt co chu y ton ~50-100ms CPU: chay ngoai event loop de khong chan request/WebSocket khac
        user = await run_in_threadpool(svc.authenticate, db, form.username, form.password, ip)
    except svc.TooManyAttempts as e:
        raise HTTPException(429, str(e), headers={"Retry-After": str(e.retry_after)})
    except svc.AuthFailed as e:
        raise HTTPException(401, str(e), headers={"WWW-Authenticate": "Bearer"})
    token, expires_in = create_access_token(user.username)
    return TokenOut(access_token=token, expires_in=expires_in, username=user.username, role=user.role)


@router.get("/api/v1/auth/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/api/v1/auth/change-password", status_code=204)
async def change_password(body: PasswordChange, user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)) -> Response:
    try:
        await run_in_threadpool(svc.change_own_password, db, user, body.old_password, body.new_password)
    except svc.AuthFailed as e:
        raise HTTPException(400, str(e))
    except svc.InvalidInput as e:
        raise HTTPException(422, str(e))
    return Response(status_code=204)


# ---------- quan ly nguoi dung (Admin) ----------

@router.get("/api/v1/users", response_model=list[UserOut])
async def list_users(_: User = Depends(require_role(Role.ADMIN)), db: Session = Depends(get_db)) -> list[User]:
    return list(db.scalars(select(User).order_by(User.username)))


@router.post("/api/v1/users", response_model=UserOut, status_code=201)
async def create_user(body: UserCreate, admin: User = Depends(require_role(Role.ADMIN)),
                      db: Session = Depends(get_db)) -> User:
    try:
        return await run_in_threadpool(svc.create_user, db, admin.username, body.username, body.password, body.role)
    except svc.UserConflict as e:
        raise HTTPException(409, str(e))
    except svc.InvalidInput as e:
        raise HTTPException(422, str(e))


@router.patch("/api/v1/users/{user_id}", response_model=UserOut)
async def update_user(user_id: int, body: UserUpdate, admin: User = Depends(require_role(Role.ADMIN)),
                      db: Session = Depends(get_db)) -> User:
    try:
        return await run_in_threadpool(svc.update_user, db, admin.username, user_id, body.role,
                                       body.is_active, body.password)
    except svc.UserNotFound as e:
        raise HTTPException(404, str(e))
    except svc.UserConflict as e:
        raise HTTPException(409, str(e))
    except svc.InvalidInput as e:
        raise HTTPException(422, str(e))
