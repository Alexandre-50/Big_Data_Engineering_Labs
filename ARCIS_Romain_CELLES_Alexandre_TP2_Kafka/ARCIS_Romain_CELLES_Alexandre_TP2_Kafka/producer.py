from confluent_kafka import Producer

BOOTSTRAP_SERVERS = "localhost:9092"
TOPIC = "book-lines"
BOOK_FILE = "book.txt"

producer = Producer({"bootstrap.servers": BOOTSTRAP_SERVERS})


def delivery_report(err, msg):
    if err is not None:
        print(f"Échec d'envoi : {err}")


sent = 0
in_book = False

with open(BOOK_FILE, encoding="utf-8-sig") as f:
    for line in f:
        # On ignore l'en-tête et le pied de page légal de Gutenberg
        if "*** START OF" in line:
            in_book = True
            continue
        if "*** END OF" in line:
            break
        if not in_book:
            continue

        line = line.rstrip("\n")
        while True:
            try:
                producer.produce(TOPIC, value=line.encode("utf-8"), callback=delivery_report)
                break
            except BufferError:
                producer.poll(0.5)  # file pleine : on laisse le temps d'envoyer
        producer.poll(0)
        sent += 1

producer.flush()
print(f"{sent} lignes envoyées au topic '{TOPIC}'.")
