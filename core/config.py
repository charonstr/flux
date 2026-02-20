import os
from dotenv import load_dotenv


def load():
    load_dotenv()
    return {
        "host": os.getenv("HOST", "127.0.0.1"),
        "port": int(os.getenv("PORT", "5000")),
        "debug": os.getenv("DEBUG", "true").lower() == "true",
        "baseurl": os.getenv("BASEURL", "http://localhost:5000"),
        "secret": os.getenv("SECRET", "devsecret"),
    }
