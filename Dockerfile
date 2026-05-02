# Use official Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements-cloud.txt

# Expose port
EXPOSE 5000

# Run app
CMD ["python", "cloud_server.py"]