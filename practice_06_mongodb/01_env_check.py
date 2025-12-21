import platform
from pymongo import MongoClient
from config import Config
from utils import json_pretty

def main() -> None:
    cfg = Config()
    client = MongoClient(cfg.mongo_uri, serverSelectionTimeoutMS=5000)
    hello = client.admin.command("hello")

    print("=== 0) Проверка окружения ===")
    print("mongo_uri:", cfg.mongo_uri)
    print("db_name:", cfg.db_name)
    print("server:", hello.get("me"))
    print("version:", hello.get("version"))
    print("python:", platform.python_version())
    print("platform:", platform.platform())
    print("\nhello:")
    print(json_pretty(hello))

if __name__ == "__main__":
    main()
