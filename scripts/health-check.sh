#!/bin/bash
#
# Health Check Script for LLM Infrastructure
# 
# This script checks the health of all infrastructure components
# and provides actionable diagnostic information.
#
# Usage: ./health-check.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Load environment variables if .env exists
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

echo "=================================="
echo "LLM Infrastructure Health Check"
echo "=================================="
echo ""

# Function to check if a service is running
check_service() {
    local service_name=$1
    local container_name=$2
    
    echo -n "Checking $service_name... "
    
    if docker ps --format '{{.Names}}' | grep -q "^${container_name}$"; then
        echo -e "${GREEN}✓ Running${NC}"
        return 0
    else
        echo -e "${RED}✗ Not Running${NC}"
        return 1
    fi
}

# Function to check service health endpoint
check_health_endpoint() {
    local service_name=$1
    local url=$2
    local expected_code=${3:-200}
    
    echo -n "Checking $service_name health endpoint... "
    
    response_code=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    
    if [ "$response_code" == "$expected_code" ]; then
        echo -e "${GREEN}✓ Healthy (HTTP $response_code)${NC}"
        return 0
    elif [ "$response_code" == "000" ]; then
        echo -e "${RED}✗ Unreachable${NC}"
        return 1
    else
        echo -e "${YELLOW}⚠ Unexpected response (HTTP $response_code)${NC}"
        return 1
    fi
}

# Function to check GPU availability
check_gpus() {
    echo -n "Checking GPU availability... "
    
    if ! command -v nvidia-smi &> /dev/null; then
        echo -e "${RED}✗ nvidia-smi not found${NC}"
        return 1
    fi
    
    gpu_count=$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l)
    
    if [ "$gpu_count" -gt 0 ]; then
        echo -e "${GREEN}✓ $gpu_count GPU(s) detected${NC}"
        nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv,noheader | while IFS=',' read -r index name mem_used mem_total; do
            echo "  GPU $index: $name - $mem_used / $mem_total"
        done
        return 0
    else
        echo -e "${RED}✗ No GPUs detected${NC}"
        return 1
    fi
}

# Function to check Docker
check_docker() {
    echo -n "Checking Docker... "
    
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}✗ Docker not found${NC}"
        return 1
    fi
    
    if ! docker ps &> /dev/null; then
        echo -e "${RED}✗ Docker daemon not accessible${NC}"
        echo "  Try: sudo systemctl start docker"
        return 1
    fi
    
    echo -e "${GREEN}✓ Docker running${NC}"
    return 0
}

# Function to check disk space
check_disk_space() {
    echo -n "Checking disk space... "
    
    if [ -z "$MODEL_BASE_PATH" ]; then
        echo -e "${YELLOW}⚠ MODEL_BASE_PATH not set${NC}"
        return 1
    fi
    
    available=$(df -BG "$MODEL_BASE_PATH" | tail -1 | awk '{print $4}' | sed 's/G//')
    
    if [ "$available" -gt 50 ]; then
        echo -e "${GREEN}✓ ${available}GB available${NC}"
        return 0
    elif [ "$available" -gt 20 ]; then
        echo -e "${YELLOW}⚠ ${available}GB available (low)${NC}"
        return 1
    else
        echo -e "${RED}✗ ${available}GB available (critical)${NC}"
        return 1
    fi
}

# Function to check network connectivity
check_networks() {
    echo -n "Checking Docker networks... "
    
    llm_net_exists=$(docker network ls | grep -c "llm_net" || echo "0")
    n8n_net_exists=$(docker network ls | grep -c "n8n_net" || echo "0")
    
    if [ "$llm_net_exists" -gt 0 ] && [ "$n8n_net_exists" -gt 0 ]; then
        echo -e "${GREEN}✓ Networks configured${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠ Networks not found${NC}"
        echo "  Run: docker-compose up -d"
        return 1
    fi
}

# Main health checks
echo "=== System Checks ==="
check_docker
docker_ok=$?

check_gpus
gpus_ok=$?

check_disk_space
disk_ok=$?

check_networks
networks_ok=$?

echo ""
echo "=== Service Checks ==="

check_service "Router" "router"
router_ok=$?

check_service "PostgreSQL" "postgres"
postgres_ok=$?

check_service "n8n" "n8n"
n8n_ok=$?

echo ""
echo "=== Health Endpoint Checks ==="

if [ $router_ok -eq 0 ]; then
    check_health_endpoint "Router" "http://localhost:8000/health"
    router_health_ok=$?
else
    router_health_ok=1
fi

echo ""
echo "=== Model Container Checks ==="

# Check for running model containers
model_containers=$(docker ps --filter "network=llm_net" --format '{{.Names}}' | grep -v "router" || echo "")

if [ -z "$model_containers" ]; then
    echo -e "${YELLOW}⚠ No model containers running${NC}"
    echo "  (This is normal if models are started on-demand)"
    models_ok=0
else
    echo "Running model containers:"
    models_ok=0
    for container in $model_containers; do
        echo -n "  $container... "
        if docker exec "$container" curl -s -f http://localhost:8000/health > /dev/null 2>&1; then
            echo -e "${GREEN}✓${NC}"
        else
            echo -e "${RED}✗${NC}"
            models_ok=1
        fi
    done
fi

echo ""
echo "=== Summary ==="
echo ""

all_ok=0

if [ $docker_ok -eq 0 ] && [ $gpus_ok -eq 0 ] && [ $router_ok -eq 0 ]; then
    echo -e "${GREEN}✓ Core infrastructure is healthy${NC}"
else
    echo -e "${RED}✗ Core infrastructure has issues${NC}"
    all_ok=1
fi

if [ $disk_ok -ne 0 ]; then
    echo -e "${YELLOW}⚠ Disk space is low${NC}"
fi

if [ $postgres_ok -ne 0 ] || [ $n8n_ok -ne 0 ]; then
    echo -e "${YELLOW}⚠ Automation services need attention${NC}"
fi

echo ""
echo "=== Diagnostic Information ==="
echo ""

if [ $all_ok -ne 0 ]; then
    echo "Common issues and fixes:"
    echo ""
    
    if [ $docker_ok -ne 0 ]; then
        echo "Docker not running:"
        echo "  sudo systemctl start docker"
        echo ""
    fi
    
    if [ $router_ok -ne 0 ]; then
        echo "Router not running:"
        echo "  docker-compose up -d router"
        echo "  Check logs: docker logs router"
        echo ""
    fi
    
    if [ $gpus_ok -ne 0 ]; then
        echo "GPUs not detected:"
        echo "  Install NVIDIA drivers: ubuntu-drivers install"
        echo "  Install NVIDIA Container Toolkit:"
        echo "    distribution=$(. /etc/os-release;echo \$ID\$VERSION_ID)"
        echo "    curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -"
        echo "    curl -s -L https://nvidia.github.io/nvidia-docker/\$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list"
        echo "    sudo apt update && sudo apt install -y nvidia-container-toolkit"
        echo "    sudo systemctl restart docker"
        echo ""
    fi
    
    if [ $disk_ok -ne 0 ]; then
        echo "Low disk space:"
        echo "  Check model directory: du -sh $MODEL_BASE_PATH"
        echo "  Remove unused models: rm -rf $MODEL_BASE_PATH/unused-model"
        echo "  Clean Docker: docker system prune -a"
        echo ""
    fi
fi

echo "For more help, see: docs/troubleshooting.md"
echo ""

# Exit with error code if any checks failed
exit $all_ok
