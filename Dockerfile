FROM python:3.9

WORKDIR /app

# Install system dependencies (VERY IMPORTANT for face_recognition)
RUN apt-get update && apt-get install -y \
    cmake \
    libgl1 \
    libglib2.0-0 \
    build-essential

COPY . .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]