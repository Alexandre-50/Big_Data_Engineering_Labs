import re
import time

from confluent_kafka import Consumer

BOOTSTRAP_SERVERS = "localhost:9092"
TOPIC = "book-lines"
OUTPUT_FILE = "cleaned_book.txt"
IDLE_TIMEOUT = 10  # secondes sans message avant d'arrêter

consumer = Consumer({
    "bootstrap.servers": BOOTSTRAP_SERVERS,
    "group.id": "book-cleaner",
    "auto.offset.reset": "earliest",
})
consumer.subscribe([TOPIC])


def clean(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s']", " ", text)  # supprime la ponctuation
    text = re.sub(r"\s+", " ", text).strip()   # normalise les espaces
    return text


received = 0
written = 0
last_message = time.time()

try:
    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        while time.time() - last_message < IDLE_TIMEOUT:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"Erreur : {msg.error()}")
                continue

            last_message = time.time()
            received += 1
            cleaned = clean(msg.value().decode("utf-8"))
            if cleaned:  # on saute les lignes vides
                out.write(cleaned + "\n")
                written += 1
finally:
    consumer.close()

print(f"{received} messages reçus, {written} lignes écrites dans {OUTPUT_FILE}.")
