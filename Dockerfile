FROM python:3.9

WORKDIR /app

RUN apt-get update && apt-get install -y \
    cmake \
    libgl1 \
    libglib2.0-0 \
    build-essential

COPY requirements.txt .

RUN pip install --upgrade pip

# install dlib binary (important)
RUN pip install dlib-bin


# install rest
RUN pip install -r requirements.txt

# install models
RUN pip install git+https://github.com/ageitgey/face_recognition_models

COPY . .

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]