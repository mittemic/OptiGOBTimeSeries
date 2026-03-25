# Use official Python image
FROM python:3.11-slim

WORKDIR /app

# Copy dependency file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run the application
CMD ["streamlit", "run", "app.py"]