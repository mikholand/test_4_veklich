import logging
import pymongo
import requests
import asyncio
import html
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandObject
from aiogram.enums.parse_mode import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
import os


load_dotenv()

MONGO_URI = os.getenv('MONGO_URI')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
API_URL = os.getenv('API_URL')


mongo_client = pymongo.MongoClient("mongodb://mongo:27017/")
db = mongo_client["messages_db"]
messages_collection = db["messages"]


bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


logging.basicConfig(level=logging.INFO)


def escape_html(text: str) -> str:
    return html.escape(text)

@dp.message(Command('start'))
async def send_welcome(message: types.Message):
    welcome_text = (
        f"Привет {message.from_user.full_name}!\n"
        "Ниже список команд для взаимодействия с ботом:\n"
        "/get <номер_страницы> - получить сообщения\n"
        "/post <сообщение> - отправить сообщение\n"
        "/clear - удалить все сообщения"
    )
    await message.reply(escape_html(welcome_text))


@dp.message(Command('get'))
async def get_messages(message: types.Message, command: CommandObject):
    args = command.args
    page = 1
    if args and args.isdigit():
        page = int(args)

    try:
        response = requests.get(f"{API_URL}messages/?page={page}&per_page=5")
        response.raise_for_status()
        data = response.json()

        messages = data.get("messages", [])
        total_pages = data.get("total_pages", 1)

        if not messages:
            await message.reply("Сообщения не найдены.")
            return

        messages_str = "\n".join(
            [f"{escape_html(msg['username'])}: {escape_html(msg['content'])}" for msg in messages]
        )

        navigation_text = f"Страница {data['page']}/{total_pages}"

        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Предыдущая", callback_data=f"get_{page - 1}")] if page > 1 else [],
            [types.InlineKeyboardButton(text="Следующая", callback_data=f"get_{page + 1}")] if page < total_pages else []
        ])

        await message.reply(f"{navigation_text}\n\n{messages_str}", reply_markup=keyboard)

    except requests.RequestException as e:
        logging.error(f"Error fetching messages: {e}")
        await message.reply("Ошибка при получении сообщений.")

@dp.callback_query()
async def handle_callback(callback_query: types.CallbackQuery):
    if callback_query.data.startswith('get_'):
        page = int(callback_query.data.split('_')[1])
        response = requests.get(f"{API_URL}messages/?page={page}&per_page=5")
        if response.status_code == 200:
            data = response.json()
            messages = data.get("messages", [])
            total_pages = data.get("total_pages", 1)
            
            messages_str = "\n".join(
                [f"{escape_html(msg['username'])}: {escape_html(msg['content'])}" for msg in messages]
            )
            
            navigation_text = f"Страница {data['page']}/{total_pages}"
            
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="Предыдущая", callback_data=f"get_{page - 1}")] if page > 1 else [],
                [types.InlineKeyboardButton(text="Следующая", callback_data=f"get_{page + 1}")] if page < total_pages else []
            ])

            await callback_query.message.edit_text(f"{navigation_text}\n\n{messages_str}", reply_markup=keyboard)
            await bot.answer_callback_query(callback_query.id)
        else:
            await bot.answer_callback_query(callback_query.id, text="Ошибка при получении сообщений.")


@dp.message(Command('post'))
async def post_message(message: types.Message, command: CommandObject):
    text = command.args
    if not text:
        await message.reply(escape_html("Используйте: /post <сообщение>"))
    else:
        username = message.from_user.username or message.from_user.full_name
        text = escape_html(text)
        message_data = {"username": username, "content": text}
        
        response = requests.post(f"{API_URL}message/", json=message_data)
        
        if response.status_code == 200:
            await message.reply("Сообщение отправлено.")
        else:
            await message.reply("Ошибка при отправке сообщения.")

@dp.message(Command('clear'))
async def clear_messages(message: types.Message):
    response = requests.delete(f"{API_URL}messages/")
    if response.status_code == 200:
        await message.reply("Все сообщения удалены.")
    else:
        await message.reply("Ошибка при удалении сообщений.")

async def main():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
