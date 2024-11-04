# Use official Python image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libmariadb-dev-compat \
    libmariadb-dev \
    libopencv-dev \
    python3-opencv \
    libjpeg-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt /app/

# Copy the project files
COPY . /app/

# Run setup.py to apply migrations and load initial data
RUN python setup.py

# Expose the port and start the application with run.py
EXPOSE 8000
CMD ["python", "run.py"]
