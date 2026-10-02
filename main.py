import os
from dotenv import load_dotenv
from fastapi import FastAPI, Depends , Response
from starlette.middleware.sessions import SessionMiddleware
from app.routes import auth
from app.security.auth import get_current_user
from app.security.rbac import require_role
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.rate_limit import limiter
from app.routes import ui
from app.routes import documents
from app.routes import runs
from app.routes import audit

load_dotenv()

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SessionMiddleware, secret_key=os.environ["SESSION_SECRET"])
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(runs.router)
app.include_router(audit.router)
app.include_router(ui.router)
from fastapi.responses import RedirectResponse
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from starlette.requests import Request as StarletteRequest
from fastapi.responses import JSONResponse

@app.get("/")
def read_root():
    return RedirectResponse(url="/ui/login")

@app.head("/")
def health_check():
    return Response(status_code=200)

@app.get("/me")
def read_current_user(current_user: dict = Depends(get_current_user)):
    return current_user


@app.get("/admin-only")
def admin_only(current_user: dict = Depends(require_role("admin"))):
    return {"message": f"Welcome, admin user {current_user['id']}"}

@app.exception_handler(FastAPIHTTPException)
async def custom_401_handler(request: StarletteRequest, exc: FastAPIHTTPException):
    if exc.status_code == 401 and request.url.path.startswith("/ui"):
        return RedirectResponse(url="/ui/login?reason=session_expired")

    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/healthz")
@app.head("/healthz")
def healthz():
    return {"status": "ok"}