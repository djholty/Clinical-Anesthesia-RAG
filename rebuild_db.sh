#!/bin/bash
# Script to rebuild the ChromaDB database
# This fixes database corruption issues

echo "============================================================"
echo "   CHROMADB DATABASE REBUILD"
echo "============================================================"
echo ""
echo "⚠️  IMPORTANT: Stop the FastAPI server before running this script!"
echo "   Press Ctrl+C in the terminal running './start_server.sh'"
echo ""
read -p "Have you stopped the FastAPI server? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Please stop the FastAPI server first and try again."
    exit 1
fi

echo ""
echo "🔄 Rebuilding database from markdown files..."
echo ""

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run the rebuild script
python3 app/rebuild_database.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Database rebuild complete!"
    echo ""
    echo "📝 Next steps:"
    echo "   1. Restart the FastAPI server: ./start_server.sh"
    echo "   2. Test the RAG system with a question"
    echo "   3. Run a new evaluation to verify performance"
else
    echo ""
    echo "❌ Database rebuild failed. Check the error messages above."
    exit 1
fi

