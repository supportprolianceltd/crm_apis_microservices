# Project Management / Task Tracking App

A full-stack task management system with Django REST Framework backend and React frontend, integrated with an existing auth-service.

## Features

- **Task Management**: Create, assign, and track tasks with status updates
- **Daily Reports**: Submit daily progress reports with detailed updates
- **Comments**: Collaborative commenting on tasks
- **User Management**: Integration with existing auth-service
- **Real-time Updates**: Automatic status and progress tracking

## Tech Stack

### Backend
- Django & Django REST Framework
- PostgreSQL
- JWT Authentication (via auth-service)
- Docker

### Frontend
- React (Vite)
- Custom CSS (no Tailwind)
- Axios for API calls

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Node.js 18+ (for local frontend development)

### Running with Docker

1. Clone the repository and navigate to the project directory

2. Start all services:
```bash
docker-compose up --build