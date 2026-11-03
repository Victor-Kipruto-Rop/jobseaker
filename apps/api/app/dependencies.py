from packages.database.sessions import SessionLocal

def get_db():
    db=SessionLocal()
    try: yield db
    finally: db.close()
