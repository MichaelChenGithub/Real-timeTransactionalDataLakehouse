
---

# Design Doc Part 1: Pipeline Architecture & Data Flow

## 1. Architecture Overview

### 1.1 Objective

Build a high-throughput, low-latency **Kappa Architecture** Lakehouse. The pipeline ingests raw user interaction events, processes them in real-time for operational monitoring (The "Pulse"), and simultaneously archives raw history for strategic analysis (The "Diagnosis"), serving both needs from a unified **Apache Iceberg** storage layer.

### 1.2 Core Design Principles

* **SLA-Driven Engineering:**
* **Latency SLA:** Guarantee **< 60 seconds** data freshness for the Real-time Operational Dashboard.
* **Availability SLA:** Ensure T+1 Batch Datasets are ready by **09:00 AM daily** for strategic reporting.


* **Lambda-Free:** Use a single processing code path (Spark Structured Streaming) for both real-time ingestion and historical replay to guarantee metric consistency.
* **Decoupled Compute & Storage:** Use **Trino** as the serving layer to query **Iceberg** tables directly, avoiding data copying.
* **Schema Resilience:** Implement a "Header + Body" pattern to handle upstream schema drift without pipeline failure.

---

## 2. High-Level Data Flow Diagram

```mermaid
graph LR
    %% ==================== Styles ====================
    classDef source   fill:#e1f5fe, stroke:#01579b, stroke-width:2px, color:#000000
    classDef stream   fill:#fff3e0, stroke:#ff6f00, stroke-width:2px, color:#000000
    classDef batch    fill:#f3e5f5, stroke:#7b1fa2, stroke-width:2px, stroke-dasharray:5 5, color:#000000
    classDef storage  fill:#fff9c4, stroke:#fbc02d, stroke-width:2px, color:#000000
    classDef serving  fill:#e8f5e9, stroke:#2e7d32, stroke-width:2px, color:#000000

    %% ==================== 1. Sources & Ingestion ====================
    subgraph Sources["1. Sources & Ingestion"]
        direction TB
        EventGen[("Mock Event Gen")]:::source
        DimGen[("Mock Dim Gen")]:::source
        Kafka["Apache Kafka <br/> Topic: content_events"]:::source
        
        EventGen --> Kafka
    end

    %% ==================== 2. Processing Layer ====================
    subgraph Compute["2. Processing Layer"]
        direction TB
        SparkSS["Spark Structured Streaming<br/>(micro-batch)"]:::stream
        
        subgraph AirflowGroup["Airflow Orchestration"]
            direction TB
            
            DimJob["Spark Batch:<br/>Dim Updates (SCD2)"]:::batch
            SilverJob["Spark Batch:<br/>Event Enrichment"]:::batch
            CompactJob["Spark Batch:<br/>Compaction"]:::batch
        end
    end

    Kafka ==> SparkSS
    DimGen -.-> DimJob

    %% ==================== 3. Iceberg Lakehouse ====================
    subgraph Storage["3. Iceberg Lakehouse (MinIO/S3)"]
        direction TB
        spacer[" "]:::hidden
        Bronze["Bronze: raw_events<br/>(append-only)"]:::storage
        DimBronze["Dim Bronze: raw<br/>(snapshot)"]:::storage
        Silver["Silver: events_enriched<br/>(cleaned/sessionized)"]:::storage
        DimSilver["Dim Silver: users/videos<br/>(SCD Type 2)"]:::storage
        Gold["Gold: virality_state<br/>(MoR upsert)"]:::storage
    end

    %% ==================== 4. Data Flow ====================
    SparkSS -->|Append Head + Body| Bronze
    SparkSS -->|"MERGE upsert"| Gold
    
    DimJob -->|read| DimBronze
    DimJob -->|"write"| DimSilver
    
    SilverJob -->|write| Silver
    SilverJob -->|read| Bronze
    
    CompactJob -.->|optimize| Bronze
    CompactJob -.->|optimize| Gold

    %% ==================== 5. Serving Layer ====================
    subgraph Serving["4. Serving Layer"]
        direction TB
        Trino["Trino Query Engine"]:::serving
        Metabase["Metabase<br/>(Ops Dashboard)"]:::serving
        Grafana["Grafana<br/>(System Metrics)"]:::serving
    end

    Gold --> Trino
    Silver --> Trino
    DimSilver --> Trino
    
    Trino -->|"JDBC"| Metabase
    Trino -->|"JDBC"| Grafana


    %% ==================== Hot vs Cold Path ====================
    %% ==================== Hot vs Cold Path ====================
    %% HOT (Real-time streaming)
    linkStyle 0,1,3,4 stroke:#ff5722,stroke-width:3px

    %% COLD (Batch / Offline)
    linkStyle 2,5,6,7,8,9,10 stroke:#7b1fa2,stroke-width:2px,stroke-dasharray:5 5

    classDef hidden height:1px,fill:none,stroke:none,color:none;

```

---

## 3. Component Design Details

### 3.1 Source & Ingestion Layer

* **Component:** Python Event Generator & Apache Kafka.
* **Topic:** `content_events`
* **Partition Strategy:** Partition by `video_id`.
* **Rationale:** The Real-time Dashboard is **Content-Centric** (Viral Velocity). Partitioning by `video_id` ensures all interactions (likes, shares) for a specific video land in the same Kafka partition, minimizing Shuffle overhead.



### 3.2 Stream Processing Layer (The Core)

* **Engine:** Apache Spark Structured Streaming (Micro-batch Mode).
* **Trigger Interval:** 10-30 seconds.
* **Logic:** The `foreachBatch` pattern is used to split the stream into two write paths:
* **Stream A (Bronze):** Append-only raw logs with "Header + Body" schema for full fidelity.
* **Stream B (Gold):** Stateful Upsert (`MERGE INTO`) to maintain the real-time "Viral Score" of videos.



### 3.3 Dimension Management (Airflow + Spark Batch)

* **Workflow:**
1. **Initialization:** A one-time batch job loads initial `dim_users` and `dim_videos` (10k users, 1k videos) into Iceberg.
2. **Daily Updates (SCD Type 1/2):**
* Airflow triggers a Python Generator script to simulate "Profile Updates" (e.g., User changes country, Video gets banned).
* Spark Batch Job reads these updates and performs `MERGE INTO` on the Iceberg Dimension tables.




* **Purpose:** Enables Trino to join real-time metrics with rich metadata (e.g., "Viral Velocity by *Video Category*").

### 3.4 Serving Layer

* **Engine:** Trino (PrestoSQL).
* **Connection:** **JDBC (Java Database Connectivity)**.
* *Note:* JDBC acts as the standard bridge allowing Metabase to send SQL queries to Trino and retrieve result sets for visualization.


* **Clients:**
* **Metabase:** Queries Gold + Dims for Business Ops.
* **Grafana:** Queries System Metrics (Lag, Latency).



---

## 4. Engineering Trade-offs & Decisions

### 4.1 Kappa vs. Lambda Architecture

* **Decision:** **Kappa Architecture**.
* **Trade-off:**
* *Pros:* Single codebase (Spark SS) ensures metric consistency between Real-time and Replay.
* *Cons:* Historical replay can be slower than dedicated batch engines.
* *Mitigation:* Heavy historical analysis (Retention) is offloaded to the **Silver Layer** (Batch) which is optimized via daily compaction.



### 4.2 Sessionization Strategy

* **Decision:** Moved Sessionization to **Batch Layer (T+1)**.
* **Trade-off:**
* We sacrificed *Real-time Session Metrics* (not critical for Content Ops).
* We gained **Resource Efficiency** (saved ~40% RAM by avoiding State Store) and **Accuracy** (better handling of late-arriving events).



### 4.3 SLA Definition

* **Real-time (Gold):** < 1 min latency. Achieved via Spark Streaming Micro-batches + Iceberg Merge-on-Read.
* **Batch (Silver/Dims):** T+1 Availability. Achieved via Airflow scheduling to ensure data consistency for morning reports.

---

## 5. Infrastructure Stack (Docker)

| Service | Container Name | Port | Role |
| --- | --- | --- | --- |
| **Kafka** | `kafka` | 9092 | Event message bus. |
| **Spark** | `spark-master` | 7077 | Stream processing & Batch Jobs. |
| **Trino** | `trino` | 8080 | Distributed SQL query engine. |
| **MinIO** | `minio` | 9000 | Object storage (S3). |
| **Metabase** | `metabase` | 3030 | BI Dashboard (JDBC Client). |
| **Airflow** | `airflow-webserver` | 8081 | Workflow Orchestration. |
| **Spark** | Spark UI | 4040 | Application monitoring and debugging |
| **Spark** | Thrift Server (optional) | 10000 | SQL access for BI tools |