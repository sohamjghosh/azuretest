"""
Railway entry point - imports the FastAPI app from api.py
This helps Railway auto-detect FastAPI applications.
"""
from api import app

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
