from pymongo import MongoClient
from config import Config
from utils import extract_index_used_from_explain, print_table

def main() -> None:
    cfg = Config()
    client = MongoClient(cfg.mongo_uri)
    db = client[cfg.db_name]
    col = db["categories"]

    print("2.1) Запросы к categories")

    q1 = {"level": 1, "partner": "_ozon"}
    c1 = col.count_documents(q1)
    first1 = list(col.find(q1, {"name": 1, "metadata.total_products": 1, "path": 1}).limit(3))
    idx1 = extract_index_used_from_explain(col.find(q1).explain())

    print("\n[Запрос 1] level=1 AND partner='_ozon'")
    print("Количество документов:", c1)
    rows1 = [{"name": d.get("name"), "total_products": d.get("metadata", {}).get("total_products"), "path": d.get("path")} for d in first1]
    print_table("Первые 3 результата", rows1, [("name","name"),("total_products","total_products"),("path","path")])
    print("Индекс из explain:", idx1)

    q2 = {"path_array": "Строительство и ремонт"}
    c2 = col.count_documents(q2)
    first2 = list(col.find(q2, {"name": 1, "level": 1, "path": 1}).limit(3))
    idx2 = extract_index_used_from_explain(col.find(q2).explain())

    print("\n[Запрос 2] path_array содержит 'Строительство и ремонт'")
    print("Количество документов:", c2)
    rows2 = [{"name": d.get("name"), "level": d.get("level"), "path": d.get("path")} for d in first2]
    print_table("Первые 3 результата", rows2, [("name","name"),("level","level"),("path","path")])
    print("Индекс из explain:", idx2)

    top10 = list(col.find({}, {"name": 1, "path": 1, "metadata.total_products": 1})
                 .sort("metadata.total_products", -1).limit(10))
    idx3 = extract_index_used_from_explain(col.find().sort("metadata.total_products", -1).limit(10).explain())

    print("\n[Запрос 3] Топ-10 категорий по metadata.total_products")
    rows3 = [{"name": d.get("name"), "total_products": d.get("metadata", {}).get("total_products"), "path": d.get("path")} for d in top10]
    print_table("Топ-10", rows3, [("name","name"),("total_products","total_products"),("path","path")])
    print("Индекс из explain:", idx3)

if __name__ == "__main__":
    main()
