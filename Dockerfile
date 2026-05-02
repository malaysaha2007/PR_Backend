FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0

COPY requirements.txt .

RUN pip install --upgrade pip

# Install prebuilt dlib
RUN pip install dlib-bin

# Install face-recognition WITHOUT dependencies
RUN pip install face-recognition --no-deps

RUN pip install -r requirements.txt

COPY . .

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]