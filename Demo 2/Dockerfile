# Use the official lightweight Python image
FROM python:3.12-slim

# Allow statements and log messages to immediately appear in the Cloud Run logs
ENV PYTHONUNBUFFERED 1
ENV PORT 8080

# Create and change to the app directory 
WORKDIR /app

# Copy application code
COPY . ./

# Install dependencies and clean up cache
RUN pip install --no-cache-dir -r requirements.txt

# Install Gunicorn
RUN pip install gunicorn

# Expose the port where the application listens
EXPOSE 8080

# Command to run Gunicorn
#CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
CMD exec gunicorn --bind :${PORT:-8080} --workers 2 --threads 8 --timeout 1800 main:app