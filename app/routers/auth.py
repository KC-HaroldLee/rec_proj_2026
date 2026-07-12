import hashlib

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.db import get_conn
from app.templates_env import templates

router = APIRouter()


@router.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html", {})


@router.post("/login")
def login_submit(request: Request, auth_name: str = Form(...), password: str = Form(...)):
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    with get_conn() as conn:
        row = conn.execute(
            'SELECT auth_id, auth_name FROM "AUTH" WHERE auth_name = %s AND password_hash = %s',
            (auth_name, password_hash),
        ).fetchone()

    if not row:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "이름 또는 비밀번호가 올바르지 않습니다."},
            status_code=401,
        )

    request.session["auth_id"] = row["auth_id"]
    request.session["auth_name"] = row["auth_name"]
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
