import secrets
import uuid
from datetime import timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.ratelimit import rate_limit
from app.core.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_refresh_token,
    verify_password,
)
from app.models import Profile, Role, User, UserSession
from app.models.base import as_utc, utcnow
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "pp_refresh"
STATE_COOKIE = "pp_oauth_state"
COOKIE_PATH = "/api/v1/auth"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


async def _issue(
    db: AsyncSession, response: Response, user: User, request: Request, family: str | None = None
) -> tuple[TokenOut, UserSession]:
    s = get_settings()
    raw = new_refresh_token()
    sess = UserSession(
        user_id=user.id,
        family_id=family or uuid.uuid4().hex,
        token_hash=hash_token(raw),
        expires_at=utcnow() + timedelta(days=s.refresh_token_ttl_days),
        user_agent=(request.headers.get("user-agent") or "")[:255],
    )
    db.add(sess)
    user.last_login_at = utcnow()
    await db.flush()
    response.set_cookie(
        REFRESH_COOKIE, raw,
        max_age=s.refresh_token_ttl_days * 86400, httponly=True, secure=s.cookie_secure,
        samesite="lax", path=COOKIE_PATH,
    )
    access = create_access_token(user.id, user.role.name, user.role.scopes)
    return TokenOut(
        access_token=access, expires_in=s.access_token_ttl_minutes * 60, user=UserOut.of(user)
    ), sess


async def _student_role(db: AsyncSession) -> Role:
    role = await db.scalar(select(Role).where(Role.name == "student"))
    if role is None:
        raise HTTPException(500, "Roles not seeded; run `python -m app.seed`")
    return role


@router.post(
    "/register", response_model=TokenOut, status_code=201,
    dependencies=[Depends(rate_limit(10, 3600, "register"))],
)
async def register(body: RegisterIn, request: Request, response: Response,
                   db: AsyncSession = Depends(get_db)):
    email = body.email.lower()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(
        email=email, full_name=body.full_name.strip(),
        password_hash=hash_password(body.password), role=await _student_role(db),
    )
    user.profile = Profile()
    db.add(user)
    await db.flush()
    out, _ = await _issue(db, response, user, request)
    await db.commit()
    return out


@router.post("/login", response_model=TokenOut,
             dependencies=[Depends(rate_limit(20, 900, "login"))])
async def login(body: LoginIn, request: Request, response: Response,
                db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == body.email.lower()))
    # Same error for unknown email and wrong password (no account enumeration)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")
    out, _ = await _issue(db, response, user, request)
    await db.commit()
    return out


@router.post("/refresh", response_model=TokenOut)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    raw = request.cookies.get(REFRESH_COOKIE)
    fail = HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    if not raw:
        raise fail
    sess = await db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(raw)))
    if sess is None:
        raise fail
    if sess.revoked_at is not None:
        # Reuse of a rotated token => likely theft. Kill the whole family.
        await db.execute(
            update(UserSession)
            .where(UserSession.family_id == sess.family_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )
        await db.commit()
        response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)
        raise fail
    if as_utc(sess.expires_at) <= utcnow():
        raise fail
    user = await db.get(User, sess.user_id)
    if user is None or not user.is_active:
        raise fail
    sess.revoked_at = utcnow()
    out, new_sess = await _issue(db, response, user, request, family=sess.family_id)
    sess.replaced_by_id = new_sess.id
    await db.commit()
    return out


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        sess = await db.scalar(
            select(UserSession).where(UserSession.token_hash == hash_token(raw))
        )
        if sess:
            await db.execute(
                update(UserSession)
                .where(UserSession.family_id == sess.family_id, UserSession.revoked_at.is_(None))
                .values(revoked_at=utcnow())
            )
            await db.commit()
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)
    response.status_code = 204
    return response


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut.of(user)


# ---------------- Google OAuth2 ----------------


@router.get("/providers")
async def providers():
    return {"google": {"enabled": True, "mock": get_settings().google_mock_mode}}


@router.get("/google/login")
async def google_login():
    s = get_settings()
    state = secrets.token_urlsafe(24)
    if s.google_mock_mode:
        target = f"{COOKIE_PATH}/google/callback?" + urlencode({"code": "mock", "state": state})
    else:
        target = GOOGLE_AUTH_URL + "?" + urlencode({
            "client_id": s.google_client_id,
            "redirect_uri": s.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
        })
    resp = RedirectResponse(target, status_code=302)
    resp.set_cookie(STATE_COOKIE, state, max_age=600, httponly=True, secure=s.cookie_secure,
                    samesite="lax", path=COOKIE_PATH)
    return resp


async def _google_identity(code: str) -> dict:
    s = get_settings()
    if s.google_mock_mode:
        # MOCK MODE: no GOOGLE_CLIENT_ID configured. Signs in a fixed demo identity.
        return {"sub": "mock-google-0001", "email": "google.demo@preppath.dev",
                "name": "Google Demo (mock)", "email_verified": True}
    async with httpx.AsyncClient(timeout=10) as client:
        tok = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code, "client_id": s.google_client_id,
            "client_secret": s.google_client_secret, "redirect_uri": s.google_redirect_uri,
            "grant_type": "authorization_code",
        })
        if tok.status_code != 200:
            raise HTTPException(400, "Google token exchange failed")
        info = await client.get(GOOGLE_USERINFO_URL, headers={
            "Authorization": f"Bearer {tok.json()['access_token']}"})
        if info.status_code != 200:
            raise HTTPException(400, "Google userinfo failed")
        return info.json()


@router.get("/google/callback")
async def google_callback(code: str, state: str, request: Request,
                          db: AsyncSession = Depends(get_db)):
    s = get_settings()
    expected = request.cookies.get(STATE_COOKIE)
    if not expected or not secrets.compare_digest(expected, state):
        return RedirectResponse(f"{s.frontend_url}/login?error=oauth_state", status_code=302)
    ident = await _google_identity(code)
    if not ident.get("email_verified"):
        return RedirectResponse(f"{s.frontend_url}/login?error=email_unverified", status_code=302)

    email = ident["email"].lower()
    user = await db.scalar(select(User).where(User.google_sub == ident["sub"]))
    if user is None:
        user = await db.scalar(select(User).where(User.email == email))
        if user is not None:
            user.google_sub = ident["sub"]  # link verified Google identity to existing account
        else:
            user = User(email=email, full_name=ident.get("name") or email.split("@")[0],
                        google_sub=ident["sub"], role=await _student_role(db))
            user.profile = Profile()
            db.add(user)
            await db.flush()
    if not user.is_active:
        return RedirectResponse(f"{s.frontend_url}/login?error=disabled", status_code=302)

    resp = RedirectResponse(f"{s.frontend_url}/auth/callback", status_code=302)
    await _issue(db, resp, user, request)
    resp.delete_cookie(STATE_COOKIE, path=COOKIE_PATH)
    await db.commit()
    return resp
