import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://root:rootpass@localhost:27017/admin")
    db_name: str = os.getenv("MONGO_DB", "ecom_catalog")

def normalize_partner(x: str) -> str:
    if x is None:
        return "_unknown"
    s = str(x).strip().lower().replace(" ", "_")
    if not s.startswith("_"):
        s = "_" + s
    return s
