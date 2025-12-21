import argparse
import pandas as pd
from pymongo import MongoClient, ReplaceOne
from pymongo.errors import BulkWriteError

from config import Config, normalize_partner
from utils import split_category_path, path_slash, parent_path_slash, utc_now_naive, print_table, print_json

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
    col = db["categories"]

    df = pd.read_parquet(args.parquet)
    df["partner"] = df["Partner_Name"].map(normalize_partner)
    df["category_id"] = df["Category_ID"].astype(str)

    cnt = df.groupby(["partner","category_id"]).size().reset_index(name="total_products")
    rep = df.groupby(["partner","category_id"])["Category_FullPathName"].first().reset_index()
    cats = cnt.merge(rep, on=["partner","category_id"], how="left")

    now = utc_now_naive()
    ops = []
    for row in cats.itertuples(index=False):
        parts = split_category_path(row.Category_FullPathName)
        doc_id = f"{row.partner}_{row.category_id}"
        doc = {
            "_id": doc_id,
            "partner": row.partner,
            "category_id": row.category_id,
            "name": parts[-1] if parts else None,
            "path": path_slash(parts),
            "path_array": parts,
            "level": int(len(parts)),
            "parent_path": parent_path_slash(parts),
            "metadata": {"total_products": int(row.total_products), "last_updated": now},
        }
        ops.append(ReplaceOne({"_id": doc_id}, doc, upsert=True))
        if len(ops) >= args.batch:
            _flush(col, ops); ops = []
    if ops:
        _flush(col, ops)

    total = col.count_documents({})
    dist = list(col.aggregate([{"$group": {"_id": "$level", "cnt": {"$sum": 1}}}, {"$sort": {"_id": 1}}]))
    dist_rows = [{"level": d["_id"], "categories_cnt": d["cnt"]} for d in dist]

    sample_root = list(col.find({"level": 1}).sort("metadata.total_products", -1).limit(1))
    sample_lvl4 = list(col.find({"level": 4}).sort("metadata.total_products", -1).limit(1))
    sample_deep = list(col.find().sort("level", -1).sort("metadata.total_products", -1).limit(1))

    print("Загрузка categories")
    print("Общее количество категорий:", total)
    print_table("Распределение по уровням", dist_rows, [("level","level"),("categories_cnt","categories_cnt")])

    ids = []
    if sample_root: ids.append(sample_root[0]["_id"])
    if sample_lvl4: ids.append(sample_lvl4[0]["_id"])
    if sample_deep: ids.append(sample_deep[0]["_id"])

    print("\n_ID документов для анализа")
    for x in ids:
        print("  ", x)

    if sample_root:
        print_json("Пример документа (level=1)", {k: sample_root[0].get(k) for k in ["_id","partner","category_id","name","path","path_array","level","parent_path","metadata"]})
    if sample_lvl4:
        print_json("Пример документа (level=4)", {k: sample_lvl4[0].get(k) for k in ["_id","partner","category_id","name","path","path_array","level","parent_path","metadata"]})
    if sample_deep:
        print_json("Пример документа (макс. глубина)", {k: sample_deep[0].get(k) for k in ["_id","partner","category_id","name","path","path_array","level","parent_path","metadata"]})

if __name__ == "__main__":
    main()
