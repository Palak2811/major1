from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import decode_access_token
from app.models import User

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None:
        raise unauthorized
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.PyJWTError:
        raise unauthorized from None
    user = await db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise unauthorized
    return user


def require_scopes(*required: str) -> Callable:
    """401 if not authenticated, 403 if authenticated but missing a scope.

    Scopes are read from the user's *current* role in the DB, so demoting a user
    takes effect immediately rather than when their access token expires.
    """

    async def checker(user: User = Depends(get_current_user)) -> User:
        granted = set(user.role.scopes or [])
        missing = [s for s in required if s not in granted]
        if missing:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, f"Missing required scope(s): {', '.join(missing)}"
            )
        return user

    return checker
