#!/bin/bash

# =============================================================================
# Webscout API Server - Auth Mode Runner
# This script builds and runs the Webscout API server with authentication enabled
# =============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.auth.yml"
CONTAINER_NAME="webscout-api-auth"
IMAGE_NAME="webscout-api:local"

echo -e "${BLUE}==============================================================================${NC}"
echo -e "${BLUE}Webscout API Server - Auth Mode Setup${NC}"
echo -e "${BLUE}==============================================================================${NC}"
echo ""

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}Error: Docker is not running. Please start Docker and try again.${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Docker is running${NC}"
}

# Function to clean up existing containers
cleanup() {
    echo -e "${YELLOW}Cleaning up existing containers...${NC}"
    docker-compose -f $COMPOSE_FILE down --remove-orphans 2>/dev/null || true
    docker container rm -f $CONTAINER_NAME 2>/dev/null || true
    echo -e "${GREEN}✓ Cleanup completed${NC}"
}

# Function to build the image
build_image() {
    echo -e "${YELLOW}Building Docker image with local code (includes AttributeError fix)...${NC}"
    docker build -f Dockerfile.local -t $IMAGE_NAME . || {
        echo -e "${RED}Error: Failed to build Docker image${NC}"
        exit 1
    }
    echo -e "${GREEN}✓ Docker image built successfully${NC}"
}

# Function to start the services
start_services() {
    echo -e "${YELLOW}Starting Webscout API server in auth mode...${NC}"
    docker-compose -f $COMPOSE_FILE up -d || {
        echo -e "${RED}Error: Failed to start services${NC}"
        exit 1
    }
    echo -e "${GREEN}✓ Services started successfully${NC}"
}

# Function to show status
show_status() {
    echo ""
    echo -e "${BLUE}Container Status:${NC}"
    docker-compose -f $COMPOSE_FILE ps
    echo ""
    
    # Wait a moment for the container to start
    sleep 5
    
    echo -e "${BLUE}Health Check:${NC}"
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ API is healthy and responding${NC}"
    else
        echo -e "${YELLOW}⚠ API is starting up... (this may take a moment)${NC}"
    fi
}

# Function to show logs
show_logs() {
    echo ""
    echo -e "${BLUE}Recent logs:${NC}"
    docker-compose -f $COMPOSE_FILE logs --tail=20 webscout-api
}

# Function to generate API key
generate_api_key() {
    echo ""
    echo -e "${BLUE}To generate an API key, run:${NC}"
    echo -e "${YELLOW}curl -X POST http://localhost:8000/v1/auth/generate-key \\${NC}"
    echo -e "${YELLOW}  -H \"Content-Type: application/json\" \\${NC}"
    echo -e "${YELLOW}  -d '{\"username\": \"testuser\", \"name\": \"Test Key\"}'${NC}"
}

# Function to show usage information
show_usage() {
    echo ""
    echo -e "${BLUE}==============================================================================${NC}"
    echo -e "${BLUE}Webscout API Server - Auth Mode${NC}"
    echo -e "${BLUE}==============================================================================${NC}"
    echo ""
    echo -e "${GREEN}Server URL:${NC} http://localhost:8000"
    echo -e "${GREEN}API Endpoint:${NC} http://localhost:8000/v1/chat/completions"
    echo -e "${GREEN}Documentation:${NC} http://localhost:8000/docs"
    echo -e "${GREEN}Health Check:${NC} http://localhost:8000/health"
    echo ""
    echo -e "${YELLOW}Authentication is ENABLED. You need to generate an API key to use the API.${NC}"
    generate_api_key
    echo ""
    echo -e "${BLUE}Useful commands:${NC}"
    echo -e "  ${YELLOW}docker-compose -f $COMPOSE_FILE logs -f${NC}     # View logs"
    echo -e "  ${YELLOW}docker-compose -f $COMPOSE_FILE down${NC}        # Stop services"
    echo -e "  ${YELLOW}docker exec -it $CONTAINER_NAME bash${NC}        # Shell into container"
    echo ""
}

# Main execution
main() {
    echo -e "${GREEN}Starting Webscout API Server setup...${NC}"
    echo ""
    
    check_docker
    cleanup
    build_image
    start_services
    show_status
    show_logs
    show_usage
    
    echo -e "${GREEN}==============================================================================${NC}"
    echo -e "${GREEN}Setup completed successfully!${NC}"
    echo -e "${GREEN}==============================================================================${NC}"
}

# Run main function
main "$@"
