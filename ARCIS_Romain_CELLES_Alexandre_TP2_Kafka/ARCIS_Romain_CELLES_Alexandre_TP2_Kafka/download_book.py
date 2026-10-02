import urllib.request

# Pride and Prejudice (Jane Austen) - change l'ID pour un autre livre
URL = "https://www.gutenberg.org/cache/epub/1342/pg1342.txt"
OUTPUT = "book.txt"

req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req) as response:
    data = response.read()

with open(OUTPUT, "wb") as f:
    f.write(data)

print(f"Livre téléchargé dans {OUTPUT} ({len(data)} octets).")
