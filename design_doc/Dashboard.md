
---

# Design Doc : Dashboard Design & Metrics

## 1. Overview

This document defines the visualization layer served by **Trino**. I implement a "Dual-Dashboard" strategy:

1. **Metabase:** Business-facing dashboards for Operations (Real-time) and Strategy (Batch).
2. **Grafana:** Technical dashboard for Data Engineering to monitor pipeline health.

---

## 2. Metabase: Real-time Ops Dashboard ("The Pulse")

* **Primary Source:** `lakehouse.gold.virality_state` (Iceberg MoR)
* **Secondary Source:** `lakehouse.dims.dim_videos` (Iceberg CoW - Fast Batch Update)
* **Update Frequency:** 1 minute (Auto-refresh)
* **Target Audience:** Content Operations, Trust & Safety

### 2.1 Layout Strategy (Command Center)

Designed for large-screen monitoring. Focuses on "Anomaly Detection" and "Immediate Action".

```text
+---------------------------------------------------------------+
|  [ Alert Banner: "Gaming" Category Cold Start Critical! ]     |
+-----------------------+-----------------------+---------------+
| 1. Viral Velocity     | 2. Fresh Supply Ratio | 3. Cold Start |
| (Scatter Plot)        | (Line Chart)          | (Gauge)       |
| "Star Finder"         | Supply/Demand Balance | RecSys Health |
+-----------------------+-----------------------+---------------+
| 4. Top Trending Videos Table (Enriched with Category/Region)  |
| Video ID | Category | Region | Velocity | Views  | Action     |
| v_1023   | Beauty   | US     | 9.8      | 50k    | [Boost]    |
+---------------------------------------------------------------+

```

### 2.2 Metric Specifications & Query Logic

| Metric Section | Visual | Definition & Logic | Business Action |
| --- | --- | --- | --- |
| **1. Viral Velocity**<br><br>(Explosion Monitor) | **Scatter Plot**<br><br>• X: Velocity<br><br>• Y: Acceleration<br><br>• Size: Total Views | **Formula:** `(Likes*5 + Shares*10) / Impressions`<br><br>**Acceleration:** `Current_Vel - 5min_Ago_Vel`<br><br><br>*Why Scatter Plot?* Instantly separates "Steady Hits" from "Exploding Supernovas" (High Velocity + High Acceleration). | **Discovery:**<br><br>Identify viral content early to manually inject into the "Hero Pool" or audit for bot activity. |
| **2. Fresh Supply Ratio**<br><br>(Inventory Health) | **Line Chart**<br><br>• Series A: Today<br><br>• Series B: Yesterday | **Formula:**<br><br>`Count(Videos Approved < 1h) / Count(Active Users 10m) * 1000`<br><br><br>*Logic:* Measures the number of fresh videos available per 1,000 active users. | **Supply Control:**<br><br>• **Low:** Supply shortage. Action: Relax moderation or recycle evergreen content.<br><br>• **High:** Oversupply. Action: Tighten moderation standards. |
| **3. Cold Start Health**<br><br>(RecSys Diagnostic) | **Gauge Chart**<br><br>• Red: <10%<br><br>• Yellow: 10-30%<br><br>• Green: >30% | **Formula:** `% of new videos (age < 1h) with > 100 views`<br><br><br>*Logic:* Proxy for Recommendation System health. | **System Diagnostic:**<br><br>If Red, the RecSys pipeline is likely blocked. Alert ML Engineers. |
| **4. Trending Table**<br><br>(Enriched Details) | **Table** | **Query Logic (Broadcast Join):**<br><br>`SELECT f.video_id, d.category, d.region, f.velocity`<br><br>`FROM gold.virality_state f`<br><br>`JOIN dims.dim_videos d ON f.video_id = d.video_id`<br><br>`ORDER BY f.velocity DESC LIMIT 50` | **Ops Execution:**<br><br>Provides the metadata context (Category, Region) needed for Ops to make boosting/banning decisions. |


### 2.3 Architectural Note: Read-Time Joins
Instead of denormalizing dimension data (e.g., `category`, `author_region`) into the streaming event log, we utilize a **Star Schema** approach with **Read-Time Joins** in Trino. This allows for:

* **Flexibility:** Metadata updates (e.g., a video re-categorization) are reflected immediately without re-processing the stream.
* **Efficiency:** We leverage **Broadcast Joins** in Trino, where the smaller dimension tables or filtered fact results are efficiently distributed across workers to minimize network shuffle.
---

## 3. Metabase: Strategic Analysis Dashboard ("The Diagnosis")

* **Source:** `lakehouse.silver.events_enriched` (Iceberg CoW)
* **Update Frequency:** Daily (T+1)
* **Target Audience:** Product Managers, Data Scientists

### 3.1 Layout & Metrics

| Metric Section | Visual | Definition & Logic | Business Action |
| --- | --- | --- | --- |
| **Quality Attribution**<br><br>(Content/User Fit) | **Heatmap**<br><br>• X: Duration Bin<br><br>• Y: Category<br><br>• Color: Completion Rate | **Formula:** `Avg(watch_time / video_duration)`<br><br>Bins: 0-15s, 15-60s, >60s<br><br><br>*Logic:* Correlates content length and type with user patience. | **Algo Tuning:**<br><br>Example: If long "Humor" videos have low completion, downrank them in the algorithm. |
| **Creator Retention**<br><br>(Ecosystem Health) | **Cohort Table** | **Formula:** Creators active in Month M who returned to upload in M+1.<br><br><br>*Logic:* Measures the sustainability of the supply side. | **Incentive Strategy:**<br><br>Drop in retention triggers "Creator Fund" bonuses or gamification campaigns. |

---

## 4. Grafana: Unified System Health Dashboard ("The Engine Room")

* **Source:** Prometheus (Kafka Exporter, Spark Metrics), Trino (Iceberg Metadata)
* **Update Frequency:** Real-time (10s - 1min)
* **Target Audience:** Data Engineers, SRE

### 4.1 Pipeline Performance (Ingestion & Compute)

| Metric | Visualization | Query / Source | Operational Significance |
| --- | --- | --- | --- |
| **E2E Data Latency** | **Stat Panel** (Big Number) | `SELECT now() - max(event_ts) FROM gold` | **SLA Check:** Must be < 60s. High latency renders the Ops dashboard useless. |
| **Kafka Consumer Lag** | **Time Series** | `kafka_consumergroup_lag > 0` (Prometheus) | **Backpressure:** Rising lag indicates Spark Executors cannot keep up with input rate. Scale out required. |
| **Iceberg Commit Duration** | **Time Series** | `commit_duration_ms` (Spark Metrics) | **Metadata Bloat:** Spikes > 5s indicate S3 throttling or too many metadata files. |

### 4.2 Storage Health (Compaction Monitoring)

* **Goal:** Monitor the "Small File Problem" and ensure Airflow Compaction Jobs are effective.
* **Source:** Trino Query on Iceberg Metadata Tables (`lakehouse.gold$files`).

| Metric | Visualization | Query Logic | Operational Significance |
| --- | --- | --- | --- |
| **Avg File Size** | **Gauge** | `SELECT avg(file_size_in_bytes) FROM "gold$files"` | **Target:** ~128MB.<br><br>**Critical:** If < 1MB, Compaction is failing. Read performance will degrade significantly. |
| **Active Data Files** | **Time Series** | `SELECT count(*) FROM "gold$files"` | **Trend:** Should show a "Sawtooth" pattern (rising during streaming, dropping after compaction). Linear growth indicates failure to expire snapshots. |

---







