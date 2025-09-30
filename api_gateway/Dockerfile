FROM python:3.11

# Set the working directory
WORKDIR /app

# Copy the requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project files
COPY . .
COPY .env .env

# Create gunicorn config
COPY gunicorn.conf.py .

# Expose the port
EXPOSE 9090

# Command to run the application with gunicorn config
CMD ["gunicorn", "--config", "gunicorn.conf.py", "api_gateway.wsgi:application"]