# AdTechMetrics.md

## Overview

This document outlines the key performance indicators (KPIs) tracked in the Real-time AdTech Lakehouse. The metrics are categorized by their data source layer, demonstrating the distinct analytical roles of the **Accumulating Snapshot Fact Table (Gold)** and the **Transaction Fact Table (Silver)**.

---

## 1. Executive & Performance Metrics (Source: Gold Layer)

**Table:** `lakehouse.gold.ad_performance_state`
**Grain:** Per Impression (Unified Lifecycle)
**Use Case:** Real-time Dashboard (Metabase), Financial Reporting, Campaign Optimization.

### 💰 Financials (The "Money" Metrics)

| Metric | Definition | SQL Logic (Simplified) | Business Value |
| --- | --- | --- | --- |
| **Real-time ROAS** | **Return on Ad Spend.** Revenue generated per dollar spent. | `SUM(revenue) / SUM(cost)` | The north star metric for advertisers. Determines if a campaign is profitable. |
| **Total Revenue (GTV)** | Total value of conversions attributed to ads. | `SUM(revenue)` | Measures top-line growth. |
| **Total Cost (Spend)** | Total amount spent on bids. | `SUM(cost)` | Budget control and pacing monitoring. |
| **CPA (Cost Per Action)** | Average cost to acquire one conversion. | `SUM(cost) / SUM(is_converted)` | Critical for performance marketing (e.g., App Installs). |
| **eCPM** | Effective Cost Per Mille (1000 impressions). | `(SUM(cost) / COUNT(*)) * 1000` | Standard metric for comparing inventory cost across platforms. |

### 📈 Performance (The "Funnel" Metrics)

| Metric | Definition | SQL Logic (Simplified) | Business Value |
| --- | --- | --- | --- |
| **CTR (Click-Through Rate)** | % of impressions that resulted in a click. | `AVG(is_clicked)` | Measures creative (ad image/video) effectiveness. |
| **CVR (Conversion Rate)** | % of clicks that resulted in a conversion. | `SUM(is_converted) / SUM(is_clicked)` | Measures landing page and product offer effectiveness. |
| **Impression Volume** | Total number of ads served. | `COUNT(*)` | Measures scale and delivery speed. |
| **Attribution Lag** | Average time from ad view to purchase. | `AVG(conversion_time - impression_time)` | Helps set lookback windows (e.g., 1 day vs 7 days). |

---

## 2. Advanced Behavioral & Engineering Metrics (Source: Silver Layer)

**Table:** `lakehouse.silver.ad_events`
**Grain:** Per Event (Time-Series Log)
**Use Case:** User Journey Analysis, Fraud Detection, ML Feature Engineering, System Health.

### 👥 User Journey (The "People" Metrics)

| Metric | Definition | SQL Logic (Concept) | Business Value |
| --- | --- | --- | --- |
| **Effective Frequency** | Avg number of impressions a user sees before converting. | `COUNT(IMPRESSION) WHERE time < conversion_time GROUP BY user` | Optimization. Avoids over-exposure (wasting budget) or under-exposure. |
| **Path Analysis** | Sequence of ad formats seen (e.g., Video -> Banner -> Buy). | `collect_list(event_type) OVER (PARTITION BY user ORDER BY time)` | Attribution Modeling (Multi-touch). Determines which ad format assists conversion. |
| **Unique Reach** | Total unique users reached over a time period. | `COUNT(DISTINCT user_id)` | Brand Awareness. How many *people* did we touch? |

### 🛡️ Security & Quality (The "Trust" Metrics)

| Metric | Definition | SQL Logic (Concept) | Business Value |
| --- | --- | --- | --- |
| **IVT Rate (Invalid Traffic)** | % of events flagged as bot/fraudulent. | `COUNT(*) WHERE ip IN (blacklist) OR click_spam_detected` | **Fraud Detection.** Advertisers demand refunds for bot clicks. |
| **Click Injection Rate** | Clicks happening suspiciously fast after impression (< 500ms). | `COUNT(*) WHERE (click_ts - imp_ts) < 500ms` | Identifies bot farms attempting to steal attribution. |
| **Orphan Click Rate** | Clicks that cannot be joined to an Impression. | `COUNT(click) WHERE impression_id IS NULL` | Data Quality / Integration issues debug. |

### ⚙️ Engineering Health (The "System" Metrics)

| Metric | Definition | SQL Logic (Concept) | Business Value |
| --- | --- | --- | --- |
| **End-to-End Latency** | Time from user action to data available in Lakehouse. | `AVG(ingest_ts - event_timestamp)` | **SLA Monitoring.** Ensures Real-time Bidding (RTB) decisions are based on fresh data. |
| **Late Arrival Rate** | % of events arriving > 1 hour late. | `COUNT(*) WHERE (ingest - event) > 1 hour` | Determines the reliability of real-time dashboards vs T+1 reports. |

---

### 📝 Summary of Data Model Strategy

* **Gold Layer Strategy:** Uses **Merge-on-Read (Upsert)** to maintain the *latest state*. This simplifies queries for "Current Performance" metrics (ROAS, CTR) by eliminating the need for complex self-joins.
* **Silver Layer Strategy:** Uses **Append-Only** storage to preserve the *sequence of events*. This enables complex time-series analysis (Frequency, Fraud) that requires granular history which is flattened in the Gold layer.

