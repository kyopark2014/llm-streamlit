#!/bin/bash

# Agent Docker Run Script (for ARG-built images)
echo "🚀 Agent Docker Run Script"
echo "=================================="

# Check if image exists
if ! sudo docker images | grep -q "streamlit-app.*latest"; then
    echo "❌ Docker image 'streamlit-app:latest' not found."
    echo "   Please build the image first using:"
    echo "   ./build-docker-with-args.sh"
    exit 1
fi

# Stop and remove existing container if it exists
echo "🧹 Cleaning up existing container..."
sudo docker stop streamlit-app-container 2>/dev/null || true
sudo docker rm streamlit-app-container 2>/dev/null || true

# Run Docker container
echo ""
echo "🚀 Starting Docker container..."
sudo docker run -d \
    --platform linux/amd64 \
    --name streamlit-app-container \
    -p 8501:8501 \
    streamlit-app:latest

if [ $? -eq 0 ]; then
    echo "✅ Container started successfully!"
    echo ""
    echo "🌐 Access your application at: http://localhost:8501"
    echo ""
    echo "📊 Container status:"
    sudo sudo docker ps | grep streamlit-app-container
    echo ""
    echo "📝 To view logs: sudo docker logs streamlit-app-container"
    echo "🛑 To stop: sudo docker stop streamlit-app-container"
    echo "🗑️  To remove: sudo docker rm streamlit-app-container"
    echo ""
    echo "🔍 To test AWS credentials in container:"
    echo "   sudo docker exec -it streamlit-app-container aws sts get-caller-identity"
else
    echo "❌ Failed to start container"
    exit 1
fi 