from pymongo import MongoClient
from config import Config
from utils import print_json

def main() -> None:
    cfg = Config()
    client = MongoClient(cfg.mongo_uri)
    db = client[cfg.db_name]

    categories = db["categories"]
    products = db["products"]

    categories.create_index([("path", "text")], name="idx_text_path")
    categories.create_index([("path_array", 1)], name="idx_path_array")
    categories.create_index([("partner", 1), ("level", 1)], name="idx_partner_level")
    categories.create_index([("metadata.total_products", -1)], name="idx_total_products")

    products.create_index([("partner", 1), ("category.id", 1)], name="idx_partner_categoryid")
    products.create_index([("category.breadcrumbs.name", 1)], name="idx_breadcrumbs_name")
    products.create_index([("type", 1), ("partner", 1)], name="idx_type_partner")
    products.create_index([("offer_id", 1)], name="idx_offer_id")

    idx_cat = list(categories.list_indexes())
    idx_prod = list(products.list_indexes())

    s_cat = db.command("collstats", "categories")
    s_prod = db.command("collstats", "products")

    def index_share_pct(stats):
        data_size = stats.get("size", 0) or 0
        index_size = stats.get("totalIndexSize", 0) or 0
        if data_size == 0:
            return None
        return 100.0 * (index_size / data_size)

    cat_pct = index_share_pct(s_cat)
    prod_pct = index_share_pct(s_prod)

    print("Индексы")
    print_json("db.categories.getIndexes()", idx_cat)
    print_json("db.products.getIndexes()", idx_prod)

    print("\nПроцент индексов от данных (indexShare):")
    print(f"  categories: dataSize={s_cat.get('size')} bytes, totalIndexSize={s_cat.get('totalIndexSize')} bytes, indexShare≈{(f'{cat_pct:.2f}%' if cat_pct is not None else 'n/a (dataSize=0)')}")
    print(f"  products:   dataSize={s_prod.get('size')} bytes, totalIndexSize={s_prod.get('totalIndexSize')} bytes, indexShare≈{(f'{prod_pct:.2f}%' if prod_pct is not None else 'n/a (dataSize=0)')}")

if __name__ == "__main__":
    main()
