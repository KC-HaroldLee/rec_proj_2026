from fastapi import Request


class NotAuthenticated(Exception):
    """세션에 로그인 정보가 없을 때 발생. main.py의 exception_handler가 /login으로 리다이렉트한다."""


def require_login(request: Request) -> dict:
    auth_id = request.session.get("auth_id")
    if not auth_id:
        raise NotAuthenticated()
    return {"auth_id": auth_id, "auth_name": request.session.get("auth_name")}
