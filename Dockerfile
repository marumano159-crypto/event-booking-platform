# Use an official lightweight Python image
FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
# Added timeout and retries to handle unstable network connections
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt

# Copy the rest of your application code
COPY . .

# Expose the port Uvicorn runs on
EXPOSE 8000

# Command to run the application when the container starts
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]