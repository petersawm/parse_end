import json
import uuid
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pika
import os

from utils import fetch_records_with_file_id

app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:3000",
    "https://question-parser.vercel.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def read_root():
    return {"Hello": "World"}

save_path = "/app/shared"


def send_message_to_file_queue(file_id: str):
    rabbitmq_host = os.getenv('RABBITMQ_HOST', 'localhost')
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=rabbitmq_host))
    channel = connection.channel()
    queue_name = 'files'
    channel.queue_declare(queue=queue_name)

    channel.basic_publish(exchange='',
                          routing_key=queue_name,
                          body=file_id)

    connection.close()


@app.post("/file")
async def receive_file(file: UploadFile):
    file_id = str(uuid.uuid4())

    with open(f"{save_path}/{file_id}", "wb") as f:
        f.write(await file.read())

    send_message_to_file_queue(file_id)
    return {"fileId": file_id}


@app.get("/file_status")
async def get_file_status(fileId: str):
    results = fetch_records_with_file_id(fileId)
    if len(results) == 0:
        return {'status': 'scheduled'}

    if len(results) < results[0][3]:
        return {'status': f'Processed {len(results)} of {results[0][3]} pages'}

    return {"status": "completed"}


@app.get("/file")
async def get_questions(fileId: str):
    results = fetch_records_with_file_id(fileId)
    page_by_page_results = []
    print(len(results))
    if len(results) == 0:
        return HTTPException(404, detail='Invalid fileId or file is still being parsed')

    if len(results) < results[0][3]:
        return HTTPException(100, detail=f'File is still being processed | completed {len(results)} of {results[0][3]} pages')

    for ind, result in enumerate(results):
        try:
            json_results = json.loads(result[5], strict=False)
            page_by_page_results.append(json_results)
        except:
            print(f'Error in parsing page {ind+1}')
            print(result[5])
            # page_by_page_results.append({"page_number": ind+1, "questions": []})
    return page_by_page_results
