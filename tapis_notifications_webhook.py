from fastapi import FastAPI, Body
from multiprocessing.connection import Client

app = FastAPI()

@app.post("/")
async def handle_notification(payload: dict = Body(...)):
    print(payload)
    conn = Client(('localhost', 9001), authkey=b'speakfriendandenter')
    conn.send(payload)
    conn.close()
    return {"status": "ok"}
