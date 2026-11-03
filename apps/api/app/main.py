from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apps.api.app.core.config import get_settings
from apps.api.app.lifespan import lifespan
from apps.api.app.api.v1.router import router
from apps.api.app.health.routes import router as health_router

s=get_settings()
app=FastAPI(title="JobSeeker Intelligence",version="0.2.0",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=s.allowed_origins,allow_credentials=True,allow_methods=["GET","POST","PATCH","DELETE"],allow_headers=["Authorization","Content-Type","X-Request-ID"])
app.include_router(health_router)
app.include_router(router,prefix="/api/v1")
@app.get("/")
def root(): return {"name":"JobSeeker Intelligence","version":"0.2.0","docs":"/docs"}
