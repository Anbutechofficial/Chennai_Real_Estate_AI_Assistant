import os
import uvicorn
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8010))
    host = os.getenv("HOST", "127.0.0.1")
    uvicorn.run("app.main:app", host=host, port=port, reload=True)