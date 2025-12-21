# practice_06_mongodb

## Установка

```powershell
pip install -U pymongo pandas pyarrow tabulate
```

## Настройки

По умолчанию:

- MONGO_URI = mongodb://root:rootpass@localhost:27017/admin
- MONGO_DB = ecom_catalog

Можно переопределить на всякий случай:

```powershell
$env:MONGO_URI="mongodb://USER:PASS@localhost:27017/admin"
$env:MONGO_DB="ecom_catalog"
```

## Запуск по порядку!

```powershell
python .\practice_06_mongodb\01_env_check.py

python .\practice_06_mongodb\02_task_1_1_analyze_parquet.py --parquet "data\ozon_inference_2025_10_17_offers_2025_10_17.pq"

python .\practice_06_mongodb\03_task_1_2_load_categories.py --parquet "data\ozon_inference_2025_10_17_offers_2025_10_17.pq"
python .\practice_06_mongodb\04_task_1_3_load_products.py   --parquet "data\ozon_inference_2025_10_17_offers_2025_10_17.pq"

python .\practice_06_mongodb\05_task_1_4_indexes.py

python .\practice_06_mongodb\06_task_2_1_categories_queries.py
python .\practice_06_mongodb\07_task_2_2_products_queries.py

python .\practice_06_mongodb\08_task_3_1_aggs_products.py
python .\practice_06_mongodb\09_task_3_3_aggs_categories.py
```
