import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.deps import NotAuthenticated
from app.routers import auth, dashboard, docs, feedback, institutions, recs, search, terms

app = FastAPI(title="사참위 권고 이행 모니터링")

app.add_middleware(SessionMiddleware, secret_key=os.environ["SESSION_SECRET"])
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.exception_handler(NotAuthenticated)
async def not_authenticated_handler(request, exc):
    return RedirectResponse("/login", status_code=303)


app.include_router(auth.router, tags=["auth"])
app.include_router(dashboard.router, tags=["dashboard"])
app.include_router(recs.router, prefix="/recs", tags=["recs"])
app.include_router(institutions.router, prefix="/institutions", tags=["institutions"])
app.include_router(terms.router, prefix="/terms", tags=["terms"])
app.include_router(docs.router, prefix="/docs", tags=["docs"])
app.include_router(feedback.router, tags=["feedback"])
app.include_router(search.router, tags=["search"])
