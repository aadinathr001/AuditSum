from fastapi.templating import Jinja2Templates
from fastapi import Request

templates = Jinja2Templates(directory="templates")


def get_session_role(request: Request) -> str | None:
    return request.session.get("role")


templates.env.globals["get_session_role"] = get_session_role