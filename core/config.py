import os
from dotenv import load_dotenv


def load():
    load_dotenv()
    return {
        "host": os.getenv("HOST", "0.0.0.0"),
        "port": int(os.getenv("PORT", "24705")),
        "debug": os.getenv("DEBUG", "false").lower() == "true",
        "baseurl": os.getenv("BASEURL", "http://fluxnet.hidenfree.com:24705"),
        "secret": os.getenv("SECRET", "devsecret"),
    }
