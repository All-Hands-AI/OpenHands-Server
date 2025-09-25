from fastapi import APIRouter
from fastapi.responses import RedirectResponse


router = APIRouter(prefix="/", tags=["Auth"])


@router.get("/login")
def login() -> RedirectResponse:
    """Redirect into the login flow - not intended for use in a fetch request."""
    return RedirectResponse("/oauth/callback")


@router.get("/oauth/callback")
def oauth_callback() -> RedirectResponse:
    return RedirectResponse("/")


@router.get("/logout")
def logout():
    raise NotImplementedError()


@router.get("/me")
def me():
    raise NotImplementedError()
