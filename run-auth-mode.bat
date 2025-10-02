@echo off
REM =============================================================================
REM Webscout API Server - Auth Mode Runner (Windows)
REM This script builds and runs the Webscout API server with authentication enabled
REM =============================================================================

setlocal enabledelayedexpansion

REM Configuration
set COMPOSE_FILE=docker-compose.auth.yml
set CONTAINER_NAME=webscout-api-auth
set IMAGE_NAME=webscout-api:local

echo ==============================================================================
echo Webscout API Server - Auth Mode Setup
echo ==============================================================================
echo.

REM Check if Docker is running
echo Checking Docker status...
docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running. Please start Docker and try again.
    pause
    exit /b 1
)
echo ✓ Docker is running

REM Clean up existing containers
echo.
echo Cleaning up existing containers...
docker-compose -f %COMPOSE_FILE% down --remove-orphans >nul 2>&1
docker container rm -f %CONTAINER_NAME% >nul 2>&1
echo ✓ Cleanup completed

REM Build the image
echo.
echo Building Docker image with local code (includes AttributeError fix)...
docker build -f Dockerfile.local -t %IMAGE_NAME% .
if errorlevel 1 (
    echo ERROR: Failed to build Docker image
    pause
    exit /b 1
)
echo ✓ Docker image built successfully

REM Start the services
echo.
echo Starting Webscout API server in auth mode...
docker-compose -f %COMPOSE_FILE% up -d
if errorlevel 1 (
    echo ERROR: Failed to start services
    pause
    exit /b 1
)
echo ✓ Services started successfully

REM Show status
echo.
echo Container Status:
docker-compose -f %COMPOSE_FILE% ps

REM Wait a moment for the container to start
echo.
echo Waiting for services to start...
timeout /t 5 /nobreak >nul

REM Health check
echo.
echo Health Check:
curl -f http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo ⚠ API is starting up... (this may take a moment)
) else (
    echo ✓ API is healthy and responding
)

REM Show recent logs
echo.
echo Recent logs:
docker-compose -f %COMPOSE_FILE% logs --tail=20 webscout-api

REM Show usage information
echo.
echo ==============================================================================
echo Webscout API Server - Auth Mode
echo ==============================================================================
echo.
echo Server URL: http://localhost:8000
echo API Endpoint: http://localhost:8000/v1/chat/completions
echo Documentation: http://localhost:8000/docs
echo Health Check: http://localhost:8000/health
echo.
echo Authentication is ENABLED. You need to generate an API key to use the API.
echo.
echo To generate an API key, run:
echo curl -X POST http://localhost:8000/v1/auth/generate-key ^
echo   -H "Content-Type: application/json" ^
echo   -d "{\"username\": \"testuser\", \"name\": \"Test Key\"}"
echo.
echo Useful commands:
echo   docker-compose -f %COMPOSE_FILE% logs -f     # View logs
echo   docker-compose -f %COMPOSE_FILE% down        # Stop services
echo   docker exec -it %CONTAINER_NAME% bash        # Shell into container
echo.
echo ==============================================================================
echo Setup completed successfully!
echo ==============================================================================

pause
