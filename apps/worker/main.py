from redis import Redis
from rq import Queue,Worker
import os
def main():
    conn=Redis.from_url(os.getenv("REDIS_URL","redis://localhost:6379/0"))
    Worker([Queue(x,connection=conn) for x in ("default","ai","email","discovery")],connection=conn).work()
if __name__=="__main__": main()
