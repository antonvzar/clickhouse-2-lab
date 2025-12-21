from pymongo import MongoClient
from config import Config
from utils import explain_agg_time_ms, print_table, print_json

def main() -> None:
    cfg = Config()
    client = MongoClient(cfg.mongo_uri)
    db = client[cfg.db_name]
    col = db["products"]

    print("3.1) Агрегации по products")

    pipeline1 = [
        {"$group": {
            "_id": "$category.id",
            "count": {"$sum": 1},
            "category_name": {"$first": "$category.name"},
            "full_path": {"$first": "$category.full_path"},
        }},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    res1 = list(col.aggregate(pipeline1))
    time1 = explain_agg_time_ms(db, "products", pipeline1)
    rows1 = [{"category_id": r["_id"], "name": r["category_name"], "full_path": r["full_path"], "count": r["count"]} for r in res1]

    print("\n[Агрегация 1] Топ-10 категорий по количеству товаров")
    print_json("Pipeline", pipeline1)
    print_table("Таблица (10 строк)", rows1, [("category_id","category_id"),("name","name"),("full_path","full_path"),("count","count")])
    print("Время выполнения (explain):", (str(time1) + " ms") if time1 is not None else "n/a")
    if rows1:
        print("Самая большая категория:", rows1[0]["name"], "| category_id=", rows1[0]["category_id"], "| count=", rows1[0]["count"])

    pipeline2 = [
        {"$unwind": "$category.breadcrumbs"},
        {"$group": {"_id": {"level": "$category.breadcrumbs.level", "name": "$category.breadcrumbs.name"}, "cnt": {"$sum": 1}}},
        {"$sort": {"_id.level": 1, "cnt": -1}},
        {"$limit": 30},
    ]
    res2 = list(col.aggregate(pipeline2))
    rows2 = [{"level": r["_id"]["level"], "name": r["_id"]["name"], "cnt": r["cnt"]} for r in res2]

    print("\n[Агрегация 2] Иерархическая статистика по уровням (30 строк)")
    print_json("Pipeline", pipeline2)
    print_table("Таблица (30 строк)", rows2, [("level","level"),("name","name"),("cnt","cnt")])

    level_totals = list(col.aggregate([
        {"$unwind": "$category.breadcrumbs"},
        {"$group": {"_id": "$category.breadcrumbs.level", "cnt": {"$sum": 1}}},
        {"$sort": {"cnt": -1}},
    ]))
    if level_totals:
        print("\nУровень с максимальным количеством товаров:", level_totals[0]["_id"], "(cnt=", level_totals[0]["cnt"], ")")

    def top3(level: int):
        pipe = [
            {"$unwind": "$category.breadcrumbs"},
            {"$match": {"category.breadcrumbs.level": level}},
            {"$group": {"_id": "$category.breadcrumbs.name", "cnt": {"$sum": 1}}},
            {"$sort": {"cnt": -1}},
            {"$limit": 3},
        ]
        return list(col.aggregate(pipe))

    for lvl in (1,2,3):
        t = top3(lvl)
        if t:
            txt = ", ".join([f"{x['_id']} ({x['cnt']})" for x in t])
            print(f"Топ-3 категорий на уровне {lvl}: {txt}")

if __name__ == "__main__":
    main()
