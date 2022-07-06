from fastapi import FastAPI, Body
from multiprocessing.connection import Client
from config import server_config

app = FastAPI()

@app.post("/")
async def handle_notification(payload: dict = Body(...)):
    print(payload)
    conn = Client(('localhost', server_config['message_port']), authkey=b'speakfriendandenter')
    conn.send(payload)
    conn.close()
    return {"status": "ok"}
