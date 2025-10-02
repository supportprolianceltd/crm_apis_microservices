Write-Host "🛑 Stopping all containers..."
docker stop $(docker ps -aq)

Write-Host "🧹 Removing all containers..."
docker rm $(docker ps -aq)

Write-Host "🗑 Removing all volumes..."
docker volume rm $(docker volume ls -q)

Write-Host "🔌 Removing all networks..."
docker network rm $(docker network ls -q)

Write-Host "🖼 Removing all images..."
docker rmi -f $(docker images -q)

Write-Host "🧼 Clearing Docker builder cache..."
docker builder prune -a -f

Write-Host "🗑 Deleting old Django migration files..."
Get-ChildItem -Recurse -Filter *.py | Where-Object { $_.FullName -match '\\migrations\\' -and $_.Name -ne '__init__.py' } | Remove-Item -Force
Get-ChildItem -Recurse -Filter *.pyc | Where-Object { $_.FullName -match '\\migrations\\' } | Remove-Item -Force

Write-Host "🌐 Recreating custom Docker network 'auth_service_default'..."
docker network create auth_service_default

Write-Host "🔨 Rebuilding docker containers..."
docker-compose build --no-cache

Write-Host "🚀 Starting containers..."
docker-compose up -d







lLINUX

echo "🛑 Stopping all containers..."
docker stop $(docker ps -aq)

echo "🧹 Removing all containers..."
docker rm $(docker ps -aq)

echo "🗑 Removing all volumes..."
docker volume rm $(docker volume ls -q)

echo "🔌 Removing all networks..."
docker network rm $(docker network ls -q)

echo "🖼 Removing all images..."
docker rmi -f $(docker images -q)

echo "🧼 Clearing Docker builder cache..."
docker builder prune -a -f

echo "🗑 Deleting old Django migration files..."
find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
find . -path "*/migrations/*.pyc" -delete

echo "🌐 Recreating custom Docker network 'auth_service_default'..."
docker network create auth_service_default

echo "🔨 Rebuilding docker containers..."
docker-compose build --no-cache

echo "🚀 Starting containers..."
docker-compose up -d
