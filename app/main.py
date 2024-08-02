from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import pymongo
import redis
import json

app = FastAPI()

# Настройка MongoDB
mongo_client = pymongo.MongoClient("mongodb://mongo:27017/")
db = mongo_client["messages_db"]
messages_collection = db["messages"]

templates = Jinja2Templates(directory="templates")

# Настройка Redis
redis_client = redis.StrictRedis(host='redis', port=6379, db=0, decode_responses=True)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Настройка статических файлов
app.mount("/static", StaticFiles(directory="static"), name="static")

class Message(BaseModel):
    username: str
    content: str

def message_serializer(message):
    return {
        "id": str(message["_id"]),
        "username": message["username"],
        "content": message["content"],
    }

@app.get("/", response_class=HTMLResponse)
async def get_home(request: Request, page: int = 1, per_page: int = 5):
    try:
        cache_key = f"messages_page_{page}"
        cached_messages = redis_client.get(cache_key)

        if cached_messages:
            messages = json.loads(cached_messages)
            total_count = len(messages)
            total_pages = (total_count + per_page - 1) // per_page
            print("Messages fetched from cache")
        else:
            skip = (page - 1) * per_page
            messages = [message_serializer(msg) for msg in messages_collection.find().sort("_id", -1).skip(skip).limit(per_page)]
            total_count = messages_collection.count_documents({})
            total_pages = (total_count + per_page - 1) // per_page

            redis_client.set(cache_key, json.dumps(messages))
            print("Messages fetched from database and cached")

        return templates.TemplateResponse("index.html", {
            "request": request,
            "messages": messages,
            "page": page,
            "total_pages": total_pages
        })
    except Exception as e:
        print(f"Error in get_home: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.post("/api/v1/message/")
async def create_message(
    request: Request,
    username: str = Form(None),
    content: str = Form(None)
):
    # Если данные поступают в виде формы
    if username and content:
        new_message = {"username": username, "content": content}
    else:
        # Если данные поступают через JSON
        try:
            data = await request.json()
            username = data.get("username")
            content = data.get("content")
            if username is None or content is None:
                raise HTTPException(status_code=400, detail="Username and content are required")
            new_message = {"username": username, "content": content}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON data: {e}")

    # Создание нового сообщения и добавление в базу данных
    messages_collection.insert_one(new_message)
    redis_client.flushdb()  # Очистка кэша при добавлении нового сообщения

    # Перенаправление на главную страницу после успешного создания сообщения
    return RedirectResponse(url="/", status_code=303)

@app.get("/api/v1/messages/")
async def get_messages(page: int = 1, per_page: int = 5):
    try:
        skip = (page - 1) * per_page
        messages = [message_serializer(msg) for msg in messages_collection.find().sort("_id", -1).skip(skip).limit(per_page)]
        total_count = messages_collection.count_documents({})
        total_pages = (total_count + per_page - 1) // per_page

        return {
            "messages": messages,
            "page": page,
            "total_pages": total_pages
        }
    except Exception as e:
        print(f"Error in get_messages: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.delete("/api/v1/messages/")
async def clear_messages():
    try:
        messages_collection.delete_many({})
        redis_client.flushdb()  # Очистка кэша при удалении всех сообщений
        return {"message": "All messages have been deleted"}
    except Exception as e:
        print(f"Error in clear_messages: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
