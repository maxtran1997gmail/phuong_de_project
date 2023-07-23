import time
import datetime
from uuid import *
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from uuid import * 
import time_uuid
import json


scala_version = '2.12'  #TODO: Ensure this is correct
spark_version = '3.0.1'
packages = [
    f'org.apache.spark:spark-sql-kafka-0-10_{scala_version}:{spark_version}',
    'org.apache.kafka:kafka-clients:3.3.1',
    'com.datastax.spark:spark-cassandra-connector_2.12:3.1.0',
    'mysql:mysql-connector-java:8.0.28'
    
]

spark = SparkSession.builder\
   .master("local")\
   .appName("kafka-example")\
   .config("spark.jars.packages", ",".join(packages))\
   .getOrCreate()


    #.config("spark.jars.packages", "") \
    

def process_timeuuid(df):
    spark_time = df.select('create_time').collect()
    normal_time = []
    for i in range(len(spark_time)):
        a = time_uuid.TimeUUID(bytes = UUID(spark_time[i][0]).bytes).get_datetime().strftime('%Y-%m-%d %H:%M:%S')
        normal_time.append(a)
    spark_timeuuid = []
    for i in range(len(spark_time)):
        spark_timeuuid.append(spark_time[i][0])
    time_data = spark.createDataFrame(zip(spark_timeuuid,normal_time),['create_time','ts'])
    result = df.join(time_data,['create_time'],'inner').drop(df.ts)
    result = result.select('create_time','ts','bid','job_id','campaign_id','custom_track','group_id','publisher_id')
    result = result.withColumn("Date", to_date("ts")) \
                   .withColumn("Hour", hour("ts"))
    return result

def process_click_data(df):
    temp = process_timeuuid(df)
    clicks_data = temp.filter(temp.custom_track == 'click')
    clicks_data = clicks_data.na.fill(0)
    cte1 = clicks_data.select("create_time", "ts", "Date", "Hour", "bid", "job_id", "campaign_id", "group_id", "publisher_id")
    clicks_output = cte1.groupBy("Date", "Hour", "job_id", "publisher_id", "campaign_id", "group_id") \
        .agg(sum("bid").alias("spend_hour"), count("create_time").alias("clicks"), avg("bid").alias("bid_set"))
    return clicks_output

def process_conversion_data(df):
    temp = process_timeuuid(df)
    conversions_data = temp.filter(temp.custom_track == 'conversion')
    conversions_data = conversions_data.na.fill(0)
    cte1 = conversions_data.select("create_time", "ts", "Date", "Hour", "bid", "job_id", "campaign_id", "group_id", "publisher_id")
    conversions_output = cte1.groupBy("Date", "Hour", "job_id", "publisher_id", "campaign_id", "group_id") \
        .agg(count("create_time").alias("conversion"))
    return conversions_output

def process_qualified_data(df):
    temp = process_timeuuid(df)
    qualifieds_data = temp.filter(temp.custom_track == 'qualified')
    qualifieds_data = qualifieds_data.na.fill(0)
    cte1 = qualifieds_data.select("create_time", "ts", "Date", "Hour", "bid", "job_id", "campaign_id", "group_id", "publisher_id")
    qualifieds_output = cte1.groupBy("Date", "Hour", "job_id", "publisher_id", "campaign_id", "group_id") \
        .agg(count("create_time").alias("qualified"))
    return qualifieds_output

def process_unqualified_data(df):
    temp = process_timeuuid(df)
    unqualifieds_data = temp.filter(temp.custom_track == 'unqualified')
    unqualifieds_data = unqualifieds_data.na.fill(0)
    cte1 = unqualifieds_data.select("create_time", "ts", "Date", "Hour", "bid", "job_id", "campaign_id", "group_id", "publisher_id")
    unqualifieds_output = cte1.groupBy("Date", "Hour", "job_id", "publisher_id", "campaign_id", "group_id") \
        .agg(count("create_time").alias("unqualified"))
    return unqualifieds_output

def company_data_from_mysql():
    df = spark.read \
    .format("jdbc") \
    .option("driver","com.mysql.cj.jdbc.Driver") \
    .option("url", "jdbc:mysql://localhost:3307/data_engineering") \
    .option("dbtable", "company") \
    .option("user", "root") \
    .option("password", "admin") \
    .load()
    company_data = df.select(df.id, df.company_id)
    company_data = company_data.withColumnRenamed("id", "job_id")
    return company_data

def process_result(df):
    print('------------------Processing click data------------------')
    clicks_output = process_click_data(df)
    print('------------------Processing conversion data------------------')
    conversions_output = process_conversion_data(df)
    print('------------------Processing qualified data------------------')
    qualifieds_output = process_qualified_data(df)
    print('------------------Processing unqualified data------------------')
    unqualifieds_output = process_unqualified_data(df)
    print('------------------Processing cassandra data------------------')
    cassandra_output = clicks_output.join(conversions_output, ['job_id','publisher_id','campaign_id','group_id','Date','Hour'],'full') \
                 .join(qualifieds_output, ['job_id','publisher_id','campaign_id','group_id','Date','Hour'],'full') \
                 .join(unqualifieds_output, ['job_id','publisher_id','campaign_id','group_id','Date','Hour'],'full')
    cassandra_output = cassandra_output.withColumn("sources",lit("Cassandra"))
    print('------------------Processing company data------------------')
    company_data = company_data_from_mysql()
    print('------------------Processing result data------------------')
    result = cassandra_output.join(company_data, cassandra_output.job_id == company_data.job_id, 'left')
    result = result.drop(company_data.job_id)
    return result

def main(mysql_latest):
    print('------------------Retrieve data from Cassandra------------------')
    df = spark.read.format("org.apache.spark.sql.cassandra").options(table="tracking", keyspace="Study_Data_Engineer").load().where(col("ts") >= mysql_latest)
    print('------------------Processing data------------------')
    result = process_result(df)
    result = result.na.fill(0)
    result.show(truncate=False)
    print('------------------Writing data into Kafka Topic------------------')
    
    df = result.selectExpr(
        "CAST(job_id AS STRING)",
        "CAST(publisher_id AS STRING)",
        "CAST(campaign_id AS STRING)",
        "CAST(group_id AS STRING)",
        "CAST(Date AS STRING)",
        "CAST(Hour AS STRING)",
        "CAST(spend_hour AS STRING)",
        "CAST(clicks AS STRING)",
        "CAST(bid_set AS STRING)",
        "CAST(conversion AS STRING)",
        "CAST(qualified AS STRING)",
        "CAST(unqualified AS STRING)",
        "CAST(sources AS STRING)",
        "CAST(company_id AS STRING)"
    )
    df.selectExpr("to_json(struct(*)) AS value") \
    .write.format("kafka").option("kafka.bootstrap.servers", "localhost:9092").option("topic", "json_data").save()
    return print('------------------Finished------------------')
    
def retrieve_cassandra_latest_time():
    df1 = spark.read.format("org.apache.spark.sql.cassandra").options(table="tracking", keyspace="Study_Data_Engineer").load()
    df1 = process_timeuuid(df1)
    cassandra_time = df1.select("ts").orderBy(desc("ts")).collect()[0][0]
    if cassandra_time == None:
        cassandra_time = '2000-01-01 00:00:00'
    return cassandra_time

def retrieve_mysql_latest_time():
    sql = """(Select MAX(latest_time_modified) from result) A"""
    mysql_time = spark.read \
                .format("jdbc") \
                .option("driver","com.mysql.cj.jdbc.Driver") \
                .option("url", "jdbc:mysql://localhost:3307/data_engineering") \
                .option("dbtable", sql) \
                .option("user", "root") \
                .option("password", "admin") \
                .load()
    mysql_latest = mysql_time.collect()[0][0].strftime("%Y-%m-%d %H:%M:%S")
    if mysql_time is None : 
        mysql_latest = '2000-01-01 00:00:00'
    return mysql_latest

while True :
    time_start = datetime.datetime.now()
    cassandra_latest = retrieve_cassandra_latest_time()
    mysql_latest = retrieve_mysql_latest_time()
    if cassandra_latest > mysql_latest:
        main(mysql_latest)     
    else :
        print('No data found')
    time_end = datetime.datetime.now()
    print('----------Take {} seconds----------'.format((time_end-time_start).total_seconds()))
    time.sleep(30)