# README for API Gateway

This project is an API Gateway built using Django. It serves as a microservice that routes requests to various backend services, providing a unified interface for clients.

## Project Structure

- **api_gateway/**: Contains the main Django application files.
  - `__init__.py`: Marks the directory as a Python package.
  - `asgi.py`: ASGI configuration for handling asynchronous requests.
  - `settings.py`: Configuration settings for the Django project.
  - `urls.py`: URL routing for the application.
  - `wsgi.py`: WSGI configuration for serving HTTP requests.

- **gateway/**: Contains the application logic for the API Gateway.
  - `__init__.py`: Marks the directory as a Python package.
  - `admin.py`: Registers models with the Django admin site.
  - `apps.py`: Configuration for the `gateway` application.
  - `migrations/`: Contains migration files for the database.
  - `models.py`: Defines data models for the application.
  - `tests.py`: Contains test cases for the application.
  - `views.py`: Contains view functions for handling requests.

- **manage.py**: Command-line utility for interacting with the Django project.

- **Dockerfile**: Instructions to build a Docker image for the API Gateway service.

- **docker-compose.yml**: Defines services, networks, and volumes for running the application.

## Running the Project

To run the API Gateway service, you can use Docker. Make sure you have Docker and Docker Compose installed on your machine.

1. Build the Docker image:
   ```
   docker-compose build
   ```

2. Start the services:
   ```
   docker-compose up
   ```

The API Gateway will be accessible at `http://localhost:9090`.

## Environment Variables

- `DEBUG`: Set to `True` for development. Change to `False` in production.

## License

This project is licensed under the MIT License. See the LICENSE file for details.