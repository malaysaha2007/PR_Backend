FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    cmake \
    build-essential

COPY requirements.txt .

RUN pip install --upgrade pip

# Install dlib separately (lighter way)
RUN pip install dlib-bin

RUN pip install -r requirements.txt

COPY . .

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]