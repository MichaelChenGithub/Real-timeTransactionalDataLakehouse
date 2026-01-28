import sys
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *

def create_spark_session():
    return SparkSession.builder \
        .appName("IcebergLakehouseStreaming") \
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
        .config("spark.sql.catalog.lakehouse", "org.apache.iceberg.spark.SparkCatalog") \
        .config("spark.sql.catalog.lakehouse.type", "hadoop") \
        .config("spark.sql.catalog.lakehouse.warehouse", "s3a://warehouse/") \
        .getOrCreate()

def main():
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    # 0. Check Namespace exists
    spark.sql("CREATE NAMESPACE IF NOT EXISTS lakehouse.ods")

    # 1. Define Schema
    json_schema = StructType([
        StructField("event_id", StringType()),
        StructField("event_type", StringType()),
        StructField("event_timestamp", LongType()),
        StructField("order_id", StringType()),
        StructField("user_id", StringType()),
        StructField("total_amount", DoubleType()),
        StructField("currency", StringType()),
        StructField("payment_method", StringType()),
        StructField("items", ArrayType(StructType([
            StructField("sku", StringType()),
            StructField("quantity", IntegerType()),
            StructField("unit_price", DoubleType()),
            StructField("category", StringType())
        ]))),
        StructField("current_status", StringType())
    ])

    # 2. Read from Kafka
    print("Connecting to Kafka...")
    kafka_stream = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "kafka:29092") \
        .option("subscribe", "orders") \
        .option("startingOffsets", "earliest") \
        .option("maxOffsetsPerTrigger", "5000") \
        .load()

    # 3. Parse JSON
    parsed_stream = kafka_stream \
        .select(from_json(col("value").cast("string"), json_schema).alias("data"), col("timestamp").alias("kafka_ts")) \
        .select("data.*", "kafka_ts")

    # 4. Write to Iceberg (ODS Layer)
    print("Starting Streaming Query to Iceberg (lakehouse.ods.orders_raw)...")
    
    query = parsed_stream.writeStream \
        .format("iceberg") \
        .outputMode("append") \
        .trigger(processingTime="5 seconds") \
        .option("checkpointLocation", "s3a://checkpoints/orders_raw_v1") \
        .option("fanout-enabled", "true") \
        .toTable("lakehouse.ods.orders_raw")

    query.awaitTermination()

if __name__ == "__main__":
    main()