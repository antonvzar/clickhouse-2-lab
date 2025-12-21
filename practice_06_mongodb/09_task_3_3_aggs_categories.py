from pymongo import MongoClient
from config import Config
from utils import print_table, print_json

def main() -> None:
    cfg = Config()
    client = MongoClient(cfg.mongo_uri)
    db = client[cfg.db_name]
    col = db["categories"]

    print("3.3) Агрегации по categories")

    pipelineA = [
        {"$group": {"_id": {"partner": "$partner", "level": "$level"},
                    "categories_cnt": {"$sum": 1},
                    "products_sum": {"$sum": "$metadata.total_products"}}},
        {"$sort": {"_id.partner": 1, "_id.level": 1}},
    ]
    resA = list(col.aggregate(pipelineA))
    rowsA = [{"partner": r["_id"]["partner"], "level": r["_id"]["level"], "categories_cnt": r["categories_cnt"], "products_sum": r["products_sum"]} for r in resA]

    print("\n[Агрегация A] распределение категорий по уровням и партнерам")
    print_json("Pipeline", pipelineA)
    print_table("Результат", rowsA, [("partner","partner"),("level","level"),("categories_cnt","categories_cnt"),("products_sum","products_sum")])

    pipelineB = [
        {"$lookup": {"from": "categories", "localField": "path", "foreignField": "parent_path", "as": "children"}},
        {"$match": {"children": {"$size": 0}}},
        {"$project": {"partner": 1, "name": 1, "path": 1, "level": 1, "metadata.total_products": 1}},
        {"$sort": {"metadata.total_products": -1}},
        {"$limit": 10},
    ]
    resB = list(col.aggregate(pipelineB))
    rowsB = [{"partner": r.get("partner"), "level": r.get("level"), "path": r.get("path"), "total_products": r.get("metadata", {}).get("total_products")} for r in resB]

    print("\n[Агрегация B] категории-листья: топ-10 по total_products")
    print_json("Pipeline", pipelineB)
    print_table("Топ-10 листьев", rowsB, [("partner","partner"),("level","level"),("path","path"),("total_products","total_products")])

    depth = list(col.aggregate([{"$group": {"_id": None, "avg_level": {"$avg": "$level"}, "max_level": {"$max": "$level"}}}]))
    if depth:
        print("\nСредняя глубина (avg level):", round(depth[0]["avg_level"], 2))
        print("Максимальная глубина (max level):", depth[0]["max_level"])

if __name__ == "__main__":
    main()
