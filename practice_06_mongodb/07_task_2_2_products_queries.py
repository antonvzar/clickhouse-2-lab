from pymongo import MongoClient
from config import Config
from utils import extract_index_used_from_explain, print_table, print_json

def main() -> None:
    cfg = Config()
    client = MongoClient(cfg.mongo_uri)
    db = client[cfg.db_name]
    col = db["products"]

    print("2.2) Запросы к products")

    q1 = {"type": "Степлер строительный", "category.breadcrumbs.name": "Пневмоинструменты"}
    c1 = col.count_documents(q1)
    first1 = list(col.find(q1, {"_id": 1, "name": 1, "type": 1, "category.full_path": 1}).limit(3))
    idx1 = extract_index_used_from_explain(col.find(q1).explain())

    print("\n[Запрос 1] type='Степлер строительный' AND breadcrumbs.name contains 'Пневмоинструменты'")
    print("Количество документов:", c1)
    rows1 = [{"_id": d.get("_id"), "name": d.get("name"), "full_path": d.get('category',{}).get('full_path')} for d in first1]
    print_table("Примеры (до 3)", rows1, [("_id","_id"),("name","name"),("full_path","full_path")])
    print("Индекс из explain:", idx1)

    q2 = {"category.breadcrumbs.3": {"$exists": True}}
    c2 = col.count_documents(q2)
    first2 = list(col.find(q2, {"_id": 1, "name": 1, "category.breadcrumbs": 1}).limit(3))
    idx2 = extract_index_used_from_explain(col.find(q2).explain())

    print("\n[Запрос 2] товары на 4-м уровне (breadcrumbs[3] exists)")
    print("Количество документов:", c2)
    rows2 = [{"_id": d.get("_id"), "name": d.get("name"), "depth": len(d.get("category", {}).get("breadcrumbs", []))} for d in first2]
    print_table("Примеры (до 3)", rows2, [("_id","_id"),("name","name"),("depth","depth")])
    print("Индекс из explain:", idx2)

    pipeline3 = [
        {"$project": {"root": {"$arrayElemAt": ["$category.breadcrumbs", 0]}}},
        {"$group": {"_id": "$root.name", "cnt": {"$sum": 1}}},
        {"$sort": {"cnt": -1}},
    ]
    res3 = list(col.aggregate(pipeline3))
    rows3 = [{"root_category": r["_id"], "products_cnt": r["cnt"]} for r in res3]

    print("\n[Запрос 3] количество товаров в каждой категории 1-го уровня")
    print_json("Pipeline", pipeline3)
    print_table("Результат", rows3, [("root_category","root_category"),("products_cnt","products_cnt")])

if __name__ == "__main__":
    main()
