from confluent_kafka.admin import AdminClient, NewTopic

BOOTSTRAP_SERVERS = "localhost:9092"
TOPIC = "book-lines"

admin = AdminClient({"bootstrap.servers": BOOTSTRAP_SERVERS})

futures = admin.create_topics(
    [NewTopic(TOPIC, num_partitions=1, replication_factor=1)]
)

for topic, future in futures.items():
    try:
        future.result()  # bloque jusqu'à la création
        print(f"Topic '{topic}' créé.")
    except Exception as e:
        print(f"Impossible de créer le topic '{topic}' : {e}")
