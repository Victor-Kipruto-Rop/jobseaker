from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from packages.database.sessions import SessionLocal
from packages.database.models.identity import User
from apps.api.app.core.security import resolve_session

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    result = resolve_session(db, request.cookies.get("jobseeker_session"))
    if not result:
        raise HTTPException(status_code=401, detail="Authentication required")
    return result[0]
