FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0

COPY requirements.txt .

RUN pip install --upgrade pip

# Prebuilt dlib
RUN pip install dlib-bin

# Install face-recognition without dependencies
RUN pip install face-recognition --no-deps

# 🔥 THIS LINE YOU MISSED
RUN pip install face-recognition-models

# Other dependencies
RUN pip install -r requirements.txt

COPY . .

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]