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

# Expose the port
EXPOSE 9090

# Command to run the application
CMD ["gunicorn", "--bind", "0.0.0.0:9090", "api_gateway.wsgi:application"]



