from pyspark.sql import SparkSession

def main():
    print("🚀 Starting REAL Pure S3A Debug Test (Hijacking spark_catalog)...")
    
    spark = SparkSession.builder \
        .appName("PureS3Debug") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.iceberg.spark.SparkCatalog") \
        .config("spark.sql.catalog.spark_catalog.type", "hadoop") \
        .config("spark.sql.catalog.spark_catalog.warehouse", "s3a://warehouse/") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "admin") \
        .config("spark.hadoop.fs.s3a.secret.key", "password") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.endpoint.region", "us-east-1") \
        .getOrCreate()

    # 測試寫入 S3 (注意：我們現在用 spark_catalog 了，所以不需要指定 catalog name，或是直接寫路徑)
    try:
        print("1️⃣  Attempting to write to 's3a://warehouse/test_hijack'...")
        data = [("Alice", 1), ("Bob", 2)]
        df = spark.createDataFrame(data, ["name", "age"])
        
        # 直接寫入 MinIO 路徑
        df.write.mode("overwrite").parquet("s3a://warehouse/test_hijack")
        print("✅ Write Successful!")
    except Exception as e:
        print("❌ Write Failed!")
        print(e)
        return

    # 測試讀取
    try:
        print("2️⃣  Attempting to read back...")
        spark.read.parquet("s3a://warehouse/test_hijack").show()
        print("✅ Read Successful!")
    except Exception as e:
        print("❌ Read Failed!")
        print(e)

if __name__ == "__main__":
    main()