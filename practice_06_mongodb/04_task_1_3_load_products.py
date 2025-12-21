import argparse
import pandas as pd
from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError

from config import Config, normalize_partner
from utils import split_category_path, path_slash, utc_now_naive, print_table, print_json

def _flush(col, ops):
    try:
        col.bulk_write(ops, ordered=False)
    except BulkWriteError as e:
        we = e.details.get("writeErrors", [])
        print("BulkWriteError:", len(we), "errors")
        if we:
            print("First error:", we[0].get("errmsg"))
        raise

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", required=True)
    ap.add_argument("--batch", type=int, default=2000)
    args = ap.parse_args()

    cfg = Config()
    client = MongoClient(cfg.mongo_uri)
    db = client[cfg.db_name]
    col = db["products"]

    df = pd.read_parquet(args.parquet)
    df["partner"] = df["Partner_Name"].map(normalize_partner)
    df["offer_id"] = df["Offer_ID"].astype(str)
    df["offer_name"] = df["Offer_Name"].astype(str)
    df["offer_type"] = df["Offer_Type"].astype(str)
    df["category_id"] = df["Category_ID"].astype(str)

    df = df.drop_duplicates(subset=["partner","offer_id"], keep="first")

    now = utc_now_naive()
    ops = []
    for row in df.itertuples(index=False):
        parts = split_category_path(row.Category_FullPathName)
        doc_id = f"{row.partner}_{row.offer_id}"
        breadcrumbs = [{"level": i+1, "name": name} for i, name in enumerate(parts)]
        doc_set = {
            "partner": row.partner,
            "offer_id": row.offer_id,
            "name": row.offer_name,
            "type": row.offer_type,
            "category": {
                "id": row.category_id,
                "name": parts[-1] if parts else None,
                "full_path": path_slash(parts),
                "breadcrumbs": breadcrumbs,
            },
            "updated_at": now,
        }
        ops.append(UpdateOne({"_id": doc_id}, {"$set": doc_set, "$setOnInsert": {"created_at": now}}, upsert=True))
        if len(ops) >= args.batch:
            _flush(col, ops); ops = []
    if ops:
        _flush(col, ops)

    total = col.count_documents({})

    top_types = list(col.aggregate([
        {"$group": {"_id": "$type", "cnt": {"$sum": 1}}},
        {"$sort": {"cnt": -1}},
        {"$limit": 5}
    ]))
    top_types_rows = [{"type": t["_id"], "cnt": t["cnt"]} for t in top_types]

    by_partner = list(col.aggregate([
        {"$group": {"_id": "$partner", "cnt": {"$sum": 1}}},
        {"$sort": {"cnt": -1}}
    ]))
    by_partner_rows = [{"partner": p["_id"], "cnt": p["cnt"]} for p in by_partner]

    sample = list(col.find({"category.breadcrumbs.3": {"$exists": True}}).limit(1)) or list(col.find().limit(1))
    sample_id = sample[0]["_id"] if sample else None

    print("Загрузка products")
    print("Общее количество товаров:", total)
    print_table("Топ-5 типов товаров", top_types_rows, [("type","type"),("cnt","cnt")])
    print_table("Распределение товаров по партнерам", by_partner_rows, [("partner","partner"),("cnt","cnt")])

    if sample_id:
        print("\n_ID документа товара:")
        print("  ", sample_id)
        print_json("Пример документа товара", sample[0])

if __name__ == "__main__":
    main()
