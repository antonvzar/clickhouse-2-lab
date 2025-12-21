import argparse
import pandas as pd

from config import normalize_partner
from utils import split_category_path, print_table

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", required=True, help="Path to .parquet/.pq file")
    args = ap.parse_args()

    df = pd.read_parquet(args.parquet)
    required = ["Partner_Name","Category_ID","Category_FullPathName","Offer_ID","Offer_Name","Offer_Type"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"Missing columns in parquet: {missing}")

    df["partner"] = df["Partner_Name"].map(normalize_partner)
    df["category_id"] = df["Category_ID"].astype(str)
    df["offer_id"] = df["Offer_ID"].astype(str)
    df["offer_type"] = df["Offer_Type"].astype(str)

    unique_categories = int(df[["partner","category_id"]].drop_duplicates().shape[0])
    depths = df["Category_FullPathName"].map(lambda x: len(split_category_path(x)))
    max_depth = int(depths.max()) if len(depths) else 0

    top10 = (
        df.groupby(["partner","category_id"])["offer_id"]
          .count()
          .sort_values(ascending=False)
          .head(10)
          .reset_index(name="products_cnt")
          .to_dict(orient="records")
    )

    partners_per_offer = df.groupby("offer_id")["partner"].nunique()
    offers_multi_partner = int((partners_per_offer > 1).sum())

    unique_types = int(df["offer_type"].nunique())

    print("1.1) Анализ исходных данных")
    print("Уникальных категорий (partner+category_id):", unique_categories)
    print("Максимальная глубина вложенности категорий:", max_depth)
    print("Offer_ID у нескольких партнеров:", offers_multi_partner)
    print("Уникальных типов товаров (Offer_Type):", unique_types)

    print_table(
        "Топ-10 категорий по количеству товаров",
        top10,
        [("partner","partner"),("category_id","category_id"),("products_cnt","products_cnt")]
    )

if __name__ == "__main__":
    main()
