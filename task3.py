# import the necessary libraries.
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, window, sum
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, TimestampType

# Create a Spark session
spark = SparkSession.builder.appName("RideSharingAnalytics").getOrCreate()

# Define the schema for incoming JSON data
schema = StructType([
    StructField("trip_id", StringType(), True),
    StructField("driver_id", StringType(), True),
    StructField("distance_km", DoubleType(), True),
    StructField("fare_amount", DoubleType(), True),
    StructField("timestamp", StringType(), True)
])

# Read streaming data from socket
df = spark.readStream.format("socket").option("host", "localhost").option("port", 9999).load()

# Parse JSON data into columns using the defined schema
parsed_df = df.select(from_json(col("value"), schema).alias("data")).select("data.*")

# Convert timestamp column to TimestampType and add a watermark
with_watermark_df = parsed_df.withColumn("timestamp", col("timestamp").cast(TimestampType())) \
    .withWatermark("timestamp", "1 minute")

# Perform windowed aggregation: sum of fare_amount over a 5-minute window sliding by 1 minute
windowed_aggs = with_watermark_df.groupBy(
    window(col("timestamp"), "5 minutes", "1 minute")
).agg(sum("fare_amount").alias("total_fare"))

# Extract window start and end times as separate columns
final_df = windowed_aggs.select(
    col("window.start").alias("window_start"),
    col("window.end").alias("window_end"),
    col("total_fare")
)

# Define a function to write each batch to a CSV file with column names
def write_to_csv(batch_df, batch_id):
    # Save the batch DataFrame as a CSV file with headers included
    batch_df.write \
        .format("csv") \
        .mode("append") \
        .option("header", "true") \
        .save(f"outputs/task_3/batch_{batch_id}")

# Use foreachBatch to apply the function to each micro-batch
query = final_df.writeStream \
    .outputMode("update") \
    .foreachBatch(write_to_csv) \
    .start()

query.awaitTermination()