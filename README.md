# Open WSL
### Pull the repository
# Run Zookeeper->Kafka sever
### Go to the directory of kafka "/kafka/confluent-7.4.0/"
### Start zookeeper
```Run "sh ./zookeeper-start.sh"```
### Start kafka server
```Run "sh ./kafka-start.sh"```
### Create kafka topic - kafka topic name: "myproject"
```sh .\bin\kafka-topics --create --bootstrap-server localhost:9092 --replication-factor 1 --partitions 1 --topic json_data```
```sh .\bin\kafka-topics --create --bootstrap-server localhost:9092 --replication-factor 1 --partitions 1 --topic avro_data```

# Run script ETL, fake_data
### Go to the directory of kafka "/kafka/"
### ETL
```Run "python3 ETL.py"```
### Fake data
```Run "python3 fake_data.py"```

# Run Schema Registry, Ksql server
### Go to the directory of kafka "/kafka/confluent-7.4.0/"
### Start Schema Registry
```Run "sh ./schema-registry.sh"```
### Start ksql server
```Run "sh ./ksql-server-start.sh"```
### Start ksql
```Run "ksql http://localhost:8088"```

# Convert json data to avro data in kafka topics
### Create stream in ksql
***Run "CREATE STREAM source (
    job_id VARCHAR,
    publisher_id VARCHAR,
    campaign_id VARCHAR,
    group_id VARCHAR,
    Date VARCHAR,
    Hour VARCHAR,
    spend_hour VARCHAR,
    clicks VARCHAR,
    bid_set VARCHAR,
    conversion VARCHAR,
    qualified VARCHAR,
    unqualified VARCHAR,
    sources VARCHAR,
    company_id VARCHAR
) WITH (
    KAFKA_TOPIC = 'json_data',
    VALUE_FORMAT = 'JSON'
);"***

```Run "SET 'auto.offset.reset' = 'earliest';"```

```Run "CREATE STREAM target_avro WITH (VALUE_FORMAT='AVRO', KAFKA_TOPIC='avro_data') AS SELECT * FROM source;"```

# Run kafka connect
### Go to the directory of kafka "/kafka/confluent-7.4.0/"
```Run script "sh ./bin/connect-standalone ./etc/kafka/jdbc_sink_config.properties ./etc/schema-registry/connect-avro-standalone.properties"```
