# Используйте официальный образ Python
FROM python:3.10-slim

# Установите рабочую директорию
WORKDIR /app

# Скопируйте файлы зависимостей
COPY requirements.txt .

# Установите зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Скопируйте остальные файлы приложения
COPY . .

# Запуск бота
CMD ["python", "bot.py"]
