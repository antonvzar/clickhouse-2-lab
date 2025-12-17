```text
# ЛР 3. ClickHouse + Prometheus + Grafana для e-commerce

Поднимаем стенд на **ClickHouse**, **Prometheus** и **Grafana**, грузим каталог интернет-магазина, строим материализованные представления, выполняем аналитические запросы, гоняем нагрузочный тест и смотрим мониторинг.

## 0. Что здесь есть

Архитектура:

- **ClickHouse** — основная БД (каталог + события)
- **Prometheus** — собирает технические метрики ClickHouse по `/metrics`
- **Grafana** — дашборды с бизнес-метриками и тех.метриками
- **Python** — скрипт `test.py` для нагрузочного тестирования

Структура проекта:

advanced-db-lab3/
├── docker-compose.yml
├── README.md
├── clickhouse/
│   ├── init.sql
│   └── conf.d/
│       └── prometheus.xml
├── grafana/
│   └── main-db.json
├── prometheus/
│   └── prometheus.yml
├── data/
│   └── 10ozon.csv      # каталог товаров (НЕ лежит в git)
└── test.py             # нагрузочный тест ClickHouse


Кину тебе готовый README, который можно почти как есть положить в репу и жить спокойно 😎
Он на русском, с командами и шагами «с нуля».

---

## 1. Предварительные требования

* Docker Desktop / Docker Engine + `docker compose`
* Python 3.10+
* `pip` для установки зависимостей

## 2. Подготовка данных

### 2.1. Каталог товаров (`data/10ozon.csv`)

CSV для каталога, структура (по колонкам):

| колонка в CSV | поле в БД   | пример    | комментарий                |
| ------------- | ----------- | --------- | -------------------------- |
| c1            | —           | `0`       | лишний столбец, игнорируем |
| c2            | offer_id    | `1724200` | ID товара                  |
| c3            | price       | `120.0`   | цена                       |
| c4            | seller_id   | `0`       | продавец                   |
| c5            | category_id | `40016`   | категория                  |
| c6            | vendor      | `Попурри` | бренд                      |

Первая строка — заголовок: `NULL,offer_id,price,seller_id,category_id,vendor`.

Файл положить в:

```text
./data/10ozon.csv
```

## 3. Docker-окружение

### 3.1. `docker-compose.yml`

В репозитории должен быть примерно такой `docker-compose.yml`:

```yaml
version: "3.8"

services:
  clickhouse:
    image: clickhouse/clickhouse-server:latest
    container_name: clickhouse
    ports:
      - "8123:8123" # HTTP
      - "9000:9000" # Native
      - "9363:9363" # Prometheus metrics
    volumes:
      - ./clickhouse/init.sql:/docker-entrypoint-initdb.d/init.sql
      - ./clickhouse/conf.d:/etc/clickhouse-server/conf.d
      - ./data:/var/lib/clickhouse/user_files
      - clickhouse-data:/var/lib/clickhouse
      - clickhouse-logs:/var/log/clickhouse-server
    ulimits:
      nofile:
        soft: 262144
        hard: 262144

  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
    depends_on:
      - clickhouse

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-data:/var/lib/grafana
    depends_on:
      - prometheus

volumes:
  clickhouse-data:
  clickhouse-logs:
  grafana-data:

```

### 3.2. Prometheus (`prometheus/prometheus.yml`)

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: "clickhouse"
    static_configs:
      - targets: ["clickhouse:9363"]
```

### 3.3. Prometheus-эндпоинт ClickHouse (`clickhouse/conf.d/prometheus.xml`)

```xml
<clickhouse>
    <prometheus>
        <endpoint>/metrics</endpoint>
        <port>9363</port>
        <metrics>true</metrics>
        <events>true</events>
        <asynchronous_metrics>true</asynchronous_metrics>
        <errors>true</errors>
    </prometheus>
</clickhouse>
```

---

## 4. Схема БД и материализованные представления

### 4.1. `clickhouse/init.sql`

```sql
CREATE DATABASE IF NOT EXISTS ecom;

USE ecom;

CREATE TABLE IF NOT EXISTS ecom_offers
(
    snapshot_date Date DEFAULT today(),        -- дата снимка каталога
    offer_id      UInt64,
    price         Float64,
    seller_id     UInt64,
    category_id   UInt32,
    vendor        String
)
ENGINE = ReplacingMergeTree(snapshot_date)
PARTITION BY toYYYYMM(snapshot_date)
ORDER BY (category_id, offer_id);

CREATE TABLE IF NOT EXISTS raw_events
(
    Hour            DateTime,
    DeviceTypeName  LowCardinality(String),
    ApplicationName LowCardinality(String),
    OSName          LowCardinality(String),
    ProvinceName    LowCardinality(String),
    ContentUnitID   UInt64
)
ENGINE = MergeTree
PARTITION BY toDate(Hour)
ORDER BY (Hour, ContentUnitID);

-- Каталог товаров
INSERT INTO ecom_offers (offer_id, price, seller_id, category_id, vendor)
SELECT
    offer_id,
    price,
    seller_id,
    category_id,
    vendor
FROM file('/data/EcomOffer.parquet', 'Parquet');

-- Сырые события
INSERT INTO raw_events (Hour, DeviceTypeName, ApplicationName, OSName, ProvinceName, ContentUnitID)
SELECT
    Hour,
    DeviceTypeName,
    ApplicationName,
    OSName,
    ProvinceName,
    ContentUnitID
FROM file('/data/RawEvent.parquet', 'Parquet');

CREATE MATERIALIZED VIEW IF NOT EXISTS catalog_by_category_mv
ENGINE = SummingMergeTree
PARTITION BY category_id
ORDER BY category_id
AS
SELECT
    category_id,
    count() AS offers_cnt
FROM ecom_offers
GROUP BY category_id;

CREATE MATERIALIZED VIEW IF NOT EXISTS catalog_by_brand_mv
ENGINE = SummingMergeTree
PARTITION BY vendor
ORDER BY (vendor, category_id)
AS
SELECT
    vendor,
    category_id,
    count() AS offers_cnt
FROM ecom_offers
GROUP BY vendor, category_id;

CREATE MATERIALIZED VIEW IF NOT EXISTS offer_events_mv
ENGINE = SummingMergeTree
PARTITION BY toDate(Hour)
ORDER BY (offer_id)
AS
SELECT
    toDate(r.Hour) AS event_date,
    e.offer_id     AS offer_id,
    e.category_id  AS category_id,
    e.vendor       AS vendor,
    count()        AS events_cnt
FROM raw_events AS r
INNER JOIN ecom_offers AS e
    ON r.ContentUnitID = e.offer_id
GROUP BY event_date, offer_id, category_id, vendor;

SELECT
    category_id,
    offers_cnt
FROM catalog_by_category_mv
ORDER BY offers_cnt DESC
LIMIT 20;

SELECT
    category_id,
    count() AS offers_cnt
FROM ecom_offers
GROUP BY category_id
ORDER BY offers_cnt DESC
LIMIT 20;

SELECT
    vendor,
    sum(offers_cnt) AS offers_cnt
FROM catalog_by_brand_mv
GROUP BY vendor
ORDER BY offers_cnt DESC
LIMIT 30;

SELECT
    category_id,
    avg(offers_cnt) AS avg_offers_per_brand
FROM
(
    SELECT
        category_id,
        vendor,
        count() AS offers_cnt
    FROM ecom_offers
    GROUP BY category_id, vendor
)
GROUP BY category_id
ORDER BY avg_offers_per_brand DESC;

SELECT
    category_id,
    avg(offers_cnt) AS avg_offers_per_brand
FROM catalog_by_brand_mv
GROUP BY category_id
ORDER BY avg_offers_per_brand DESC;

SELECT
    o.offer_id,
    o.category_id,
    o.vendor,
    o.price
FROM ecom_offers AS o
LEFT JOIN
(
    SELECT DISTINCT ContentUnitID AS offer_id
    FROM raw_events
) AS e USING (offer_id)
WHERE e.offer_id IS NULL;

SELECT
    o.offer_id,
    o.category_id,
    o.vendor,
    o.price
FROM ecom_offers AS o
LEFT JOIN
(
    SELECT DISTINCT offer_id
    FROM offer_events_mv
) AS ev USING (offer_id)
WHERE ev.offer_id IS NULL;

```

---

## 5. Запуск контейнеров

Из корня проекта:

```bash
docker compose up -d
```

Проверка:

```bash
docker ps
# clickhouse, prometheus, grafana должны быть в статусе Up
```

Проверить ClickHouse HTTP:

* http://localhost:8123/ping -> должно вернуть `Ok.`
* Также, можно протестить через - **Prometheus:** [http://localhost:9090](http://localhost:9090) - там будет видно, что сервер поднят

---

## 6. Загрузка данных в ClickHouse

Подключение к серверу:

```bash
docker exec -it clickhouse clickhouse-client
```

### 6.1. Каталог (`10ozon.csv`)

```sql
USE ecom;

SET input_format_with_names_use_header = 0;

INSERT INTO ecom_offers (offer_id, price, seller_id, category_id, vendor)
SELECT
    toUInt64(c2)  AS offer_id,
    toFloat64(c3) AS price,
    toUInt64(c4)  AS seller_id,
    toUInt32(c5)  AS category_id,
    c6            AS vendor
FROM file('10ozon.csv', 'CSV')
WHERE c2 != 'offer_id';
```

Проверка:

```sql
SELECT count() FROM ecom_offers;
SELECT * FROM ecom_offers LIMIT 5;

SELECT * FROM catalog_by_category_mv LIMIT 5;
SELECT * FROM catalog_by_brand_mv LIMIT 5;
```

## 7. Аналитические запросы (для отчёта и сравнения raw vs MV)

Все запросы выполняются в `clickhouse-client` в базе `ecom`. Поэтому не стоит забывать перемещаться в `ecom`, если выходили из `ClickHouse`

```sql
USE ecom;
```

### 7.1. Топ-20 категорий по количеству товаров

Через MV:

```sql
SELECT
    category_id,
    offers_cnt
FROM catalog_by_category_mv
ORDER BY offers_cnt DESC
LIMIT 20;
```

По сырым данным:

```sql
SELECT
    category_id,
    count() AS offers_cnt
FROM ecom_offers
GROUP BY category_id
ORDER BY offers_cnt DESC
LIMIT 20;
```

### 7.2. Топ-30 брендов по количеству товаров

Через MV:

```sql
SELECT
    vendor,
    sum(offers_cnt) AS offers_cnt
FROM catalog_by_brand_mv
GROUP BY vendor
ORDER BY offers_cnt DESC
LIMIT 30;
```

По сырым данным:

```sql
SELECT
    vendor,
    count() AS offers_cnt
FROM ecom_offers
GROUP BY vendor
ORDER BY offers_cnt DESC
LIMIT 30;
```

### 7.3. Среднее количество товаров по брендам в категориях

Через MV:

```sql
SELECT
    category_id,
    avg(offers_cnt) AS avg_offers_per_brand
FROM catalog_by_brand_mv
GROUP BY category_id
ORDER BY avg_offers_per_brand DESC;
```

По сырым данным:

```sql
SELECT
    category_id,
    avg(offers_per_brand) AS avg_offers_per_brand
FROM
(
    SELECT
        category_id,
        vendor,
        count() AS offers_per_brand
    FROM ecom_offers
    GROUP BY category_id, vendor
)
GROUP BY category_id
ORDER BY avg_offers_per_brand DESC;
```

### 7.4. Товары без пользовательских событий

Через сырые события:

```sql
SELECT
    o.offer_id,
    o.category_id,
    o.vendor,
    o.price
FROM ecom_offers AS o
LEFT JOIN
(
    SELECT DISTINCT ContentUnitID AS offer_id
    FROM raw_events
) AS e
    ON o.offer_id = e.offer_id
WHERE e.offer_id IS NULL;
```

Через MV `offer_events_mv`:

```sql
SELECT
    o.offer_id,
    o.category_id,
    o.vendor,
    o.price
FROM ecom_offers AS o
LEFT JOIN offer_events_mv AS ev
    ON o.offer_id = ev.offer_id
WHERE ev.offer_id IS NULL;
```

---

## 8. Нагрузочное тестирование (Python `test.py`)

### 8.1. Заведение пользователя для тестов

В ClickHouse можно создать отдельного юзера без пароля:

```sql
CREATE USER IF NOT EXISTS benchmark IDENTIFIED WITH no_password;
GRANT SELECT ON ecom.* TO benchmark;
```

### 8.2. Установка зависимостей

В корне проекта:

```bash
pip install clickhouse-driver python-docx
```

### 8.3. Логика `test.py`

Скрипт:

* подключается к ClickHouse (`localhost:9000`, БД `ecom`, пользователь `benchmark` без пароля);
* выполняет набор SQL-запросов (raw и через MV);
* для каждого запроса делает `ITERATIONS` прогонов;
* считает `min / mean / max` времени выполнения;
* пишет результаты:
  * в консоль;
  * в файл `clickhouse_load_test_YYYYMMDD_HHMMSS.txt` (и `.docx`, если установлен `python-docx`).

Запуск:

```bash
python test.py
```

Во время работы скрипта в Grafana удобно смотреть, как меняются QPS, латентность и использование памяти.

---

## 9. Grafana и Prometheus: настройка мониторинга

### 9.1. Доступ

* **Grafana:** [http://localhost:3000](http://localhost:3000)
  логин/пароль по умолчанию: `admin` / `admin` (при первом входе попросит сменить пароль, можно оставить прежними)
* **Prometheus:** [http://localhost:9090](http://localhost:9090)
* **ClickHouse HTTP:** [http://localhost:8123](http://localhost:8123)

### 9.2. Data sources в Grafana

**Prometheus**

1. `Configuration -> Data sources -> Add data source`.
2. Тип: `Prometheus`.
3. URL: `http://prometheus:9090`.
4. `Save & Test`.

**ClickHouse**

1. `Configuration -> Data sources -> Add data source`.
2. Тип: `ClickHouse`.
3. Есть `ClickHouse` нет - заходим `Connections -> Add new connection -> Вводим ClickHouse -> устанавливаем` и назад на 1 пункт
4. Server address: `clickhouse`
5. Server port: `9000`
6. Protocol: `Native`
7. Username: `benchmark` (или `default`)
8. Password: пустой, если не задан
9. Default database: `ecom`
10. `Save & Test`.

### 9.3. Дашборд бизнес-метрик (ClickHouse)

Создать новый Dashboard -> **Add new panel**.

1. **Top categories**

   * Data source: `clickhouse`

   * SQL:

     ```sql
     SELECT
         category_id,
         offers_cnt
     FROM catalog_by_category_mv
     ORDER BY offers_cnt DESC
     LIMIT 20;
     ```

   * Viz: `Bar chart`

   * Title: `Top-20 categories by number of offers`.

2. **Top brands**

   ```sql
   SELECT
       vendor,
       sum(offers_cnt) AS offers_cnt
   FROM catalog_by_brand_mv
   GROUP BY vendor
   ORDER BY offers_cnt DESC
   LIMIT 30;
   ```

   Viz: `Bar chart`, Title: `Top-30 brands by number of offers`.

3. **Catalog coverage**

   ```sql
   SELECT
       countIf(ev.offer_id IS NOT NULL) AS offers_with_events,
       count()                          AS total_offers,
       offers_with_events / total_offers AS coverage_ratio
   FROM ecom_offers AS o
   LEFT JOIN offer_events_mv AS ev
       ON o.offer_id = ev.offer_id;
   ```

   Viz: `Stat`, Unit: `Percent (0–1)`, Title: `Catalog coverage`.

4. **Events by device type** (если есть `raw_events`):

   ```sql
   SELECT
       DeviceTypeName,
       count() AS events_cnt
   FROM raw_events
   GROUP BY DeviceTypeName
   ORDER BY events_cnt DESC;
   ```

   Viz: `Bar chart` или `Pie chart`, Title: `Events by device type`.

### 9.4. Дашборд технических метрик (Prometheus)

Каждая панель — отдельный график (datasource: `prometheus`).

1. **QPS (Queries per second)**

   ```promql
   rate(ClickHouseProfileEvents_Query[1m])
   ```

   Viz: `Time series`, Title: `QPS (queries per second)`.

2. **Average query latency**

   ```promql
   rate(ClickHouseProfileEvents_QueryTimeMicroseconds[1m])
   /
   rate(ClickHouseProfileEvents_Query[1m])
   / 1e6
   ```

   Viz: `Time series`, Title: `Average query latency (s)`.

3. **Memory usage**

   ```promql
   ClickHouseAsynchronousMetrics_MemoryResident
   ```

   (или другая подходящая `…Memory…` метрика)

   Viz: `Time series`, Unit: `bytes`, Title: `ClickHouse memory usage`.

Дополнительно можно добавить:

```promql
ClickHouseMetrics_Query
```

как число активных запросов (Title: `Active queries`).

---

## 10. Остановка и повторный запуск

Аккуратно выключить, не потеряв данные:

```bash
docker compose stop
# или
docker compose down
```

Запустить снова:

```bash
docker compose up -d
```

Полный ресет БД (данные будут потеряны):

```bash
docker compose down -v
```

---

## 11. Плюсы ClickHouse для e-commerce

Почему ClickHouse хорошо подходит под аналитическую задачу маркетплейса/интернет-магазина:

1. **Колонночное хранение и сжатие**

   * Данные лежат по столбцам, а не по строкам -> сканируется только нужные колонки (например, `category_id`, `price`, `vendor`) без чтения всего ряда
   * Сильная компрессия (RLE, LZ4, ZSTD) позволяет хранить кучу гигабайт логов и каталога относительно дёшево по диску

2. **Очень быстрые агрегации по большим объёмам**

   * Типичные e-commerce запросы: «топ категорий», «топ брендов», «конверсия по устройствам» - это всё `GROUP BY`/`ORDER BY` по десяткам миллионов строк
   * ClickHouse оптимизирован именно под такие OLAP-запросы и работает на порядки быстрее, чем классические row-store БД

3. **Materialized Views и агрегирующие таблицы**

   * Можно заранее считать агрегации (по категориям, брендам, товарам, дням, каналам трафика) и хранить их в отдельной таблице с движком `SummingMergeTree`
   * Для дашбордов и отчётов запросы по MV выполняются за миллисекунды, даже при очень большой «сырой» таблице

4. **Масштабирование и горизонтальный рост**

   * Есть распределённые таблицы (`Distributed`), шардинг и репликация
   * Это позволяет держать аналитику по всему каталогу, логам показов/кликов, корзинам и заказам в одной системе и масштабировать кластер по мере роста бизнеса

5. **Богатый SQL и простота интеграции**

   * Нормальный SQL-диалект (JOIN, подзапросы, оконные функции, массивы, JSON)
   * драйверы для Python, Go, Java, BI-инструменты (Grafana, Superset, Metabase и т.п.)
   * Легко подключить к существующей аналитической инфраструктуре

В контексте этой лабы это проявляется в том, что:

* ClickHouse спокойно проглатывает десятки миллионов строк каталога и событи
* MV дают мгновенные ответы на бизнес-запросы
* через Prometheus/Grafana видно, как он себя ведёт под нагрузкой

---

