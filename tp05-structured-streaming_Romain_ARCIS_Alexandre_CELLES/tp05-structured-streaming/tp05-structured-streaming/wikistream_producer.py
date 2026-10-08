# %% Dependencies
"""
Producteur Kafka pour les événements Wikimedia (EventStreams).

Version enrichie du producteur du TP (étape 11) : les filtres sont
paramétrables en ligne de commande, ce qui permet de suivre une autre
langue, plusieurs wikis, des pages précises, un namespace, ou d'exclure
les bots, sans modifier le code.

Exemples :
  python wikistream_producer.py                                  # démo : fr.wikipedia.org, edits, 10 min
  python wikistream_producer.py --wiki en.wikipedia.org --minutes 5
  python wikistream_producer.py --wiki fr.wikipedia.org --wiki de.wikipedia.org
  python wikistream_producer.py --type edit --type new           # éditions + créations de pages
  python wikistream_producer.py --title "Paris" --title "France" # pages précises
  python wikistream_producer.py --namespace 0 --bots exclude     # articles seulement, humains seulement
  python wikistream_producer.py --title-contains football        # pages dont le titre contient "football"
"""
import argparse
import json
import os
import socket
from datetime import datetime, timedelta

# pywikibot réclame normalement un user-config.py ; inutile pour lire EventStreams
os.environ.setdefault('PYWIKIBOT_NO_USER_CONFIG', '1')

from confluent_kafka import Producer
from pywikibot.comms.eventstreams import EventStreams


# %% Arguments
def parse_args():
  p = argparse.ArgumentParser(description='Wikimedia EventStreams -> Kafka')
  p.add_argument('--bootstrap', default='localhost:9092', help='Kafka bootstrap servers')
  p.add_argument('--topic', default='wikistreams', help='Kafka topic')
  p.add_argument('--wiki', action='append', dest='wikis',
                 help='server_name à suivre (répétable). Défaut : fr.wikipedia.org')
  p.add_argument('--type', action='append', dest='types',
                 help='type d\'événement : edit, new, log, categorize (répétable). Défaut : edit')
  p.add_argument('--title', action='append', dest='titles',
                 help='titre exact d\'une page à suivre (répétable)')
  p.add_argument('--title-contains', default=None,
                 help='ne garder que les pages dont le titre contient ce texte (insensible à la casse)')
  p.add_argument('--namespace', type=int, action='append', dest='namespaces',
                 help='namespace (0 = articles, 2 = pages utilisateur, ...) (répétable)')
  p.add_argument('--bots', choices=['all', 'only', 'exclude'], default='all',
                 help='garder tous les auteurs, seulement les bots, ou exclure les bots')
  p.add_argument('--min-size', type=int, default=None,
                 help='ne garder que les modifications dont |taille nouvelle - ancienne| >= N octets')
  p.add_argument('--minutes', type=float, default=10, help='durée de capture en minutes')
  p.add_argument('--since', default=None,
                 help='rejouer depuis cette date (ex. 20261008 ou 2026-10-08T10:00:00Z). '
                      'Défaut : flux en direct. Wikimedia ne conserve que ~7 jours.')
  p.add_argument('--quiet', action='store_true', help='ne pas afficher chaque événement')
  return p.parse_args()


# %% Helper Functions
# Serializer function to change message from python dict to json
value_serializer = lambda val: json.dumps(val).encode('utf-8')


def size_delta(change):
  length = change.get('length') or {}
  return (length.get('new') or 0) - (length.get('old') or 0)


def delivery_report(err, msg):
  if err is not None:
    print(f'Echec de livraison : {err}')


# %% Create wikistreams query
def build_stream(args):
  # Seul 'recentchange' porte les champs server_name / type / bot / length.
  # ('revision-create' n'a pas de champ 'type' : avec le filtre type='edit'
  #  de la démo, ses événements étaient de toute façon tous écartés.)
  stream = EventStreams(streams=['recentchange'], since=args.since)

  wikis = args.wikis or ['fr.wikipedia.org']
  types = args.types or ['edit']

  # Filtres "clé = valeur" : une liste signifie "une des valeurs" ; plusieurs
  # filtres enregistrés avec ftype='all' (défaut) doivent TOUS être vrais.
  stream.register_filter(server_name=wikis)
  stream.register_filter(type=types)

  if args.titles:
    stream.register_filter(title=args.titles)
  if args.namespaces:
    stream.register_filter(namespace=args.namespaces)
  if args.bots == 'only':
    stream.register_filter(bot=True)
  elif args.bots == 'exclude':
    stream.register_filter(bot=False)

  # Filtres "fonction" : n'importe quelle condition Python sur l'événement
  if args.title_contains:
    needle = args.title_contains.lower()
    stream.register_filter(lambda e: needle in e.get('title', '').lower())
  if args.min_size is not None:
    stream.register_filter(lambda e: abs(size_delta(e)) >= args.min_size)

  return stream


# %% Main
def main():
  args = parse_args()

  # Producer instantiation
  conf = {'bootstrap.servers': args.bootstrap,
          'client.id': socket.gethostname(),
          'compression.type': 'lz4'}
  producer = Producer(conf)

  stream = build_stream(args)

  # Run a single query and inspect raw and example formatted output
  change = next(stream)
  print('Raw Message: ' + str(change))
  print('\nFormatted Message: {type} on page "{title}" by "{user}" at {meta[dt]}.\n'
        .format(**change))

  # Streaming query for <minutes> minutes
  stop_time = datetime.now() + timedelta(minutes=args.minutes)
  sent = 0
  try:
    while datetime.now() < stop_time:
      producer.produce(
        topic=args.topic,
        key=change.get('title', '').encode('utf-8'),  # même page -> même partition
        value=value_serializer(change),
        callback=delivery_report,
      )
      producer.poll(0)  # déclenche les callbacks de livraison
      sent += 1
      if not args.quiet:
        print(f"[{change['meta']['dt']}] {change['server_name']} | {change['type']:<5} | "
              f"bot={str(change.get('bot')):<5} | {size_delta(change):+7d} o | "
              f"{change['title']} ({change['user']})")
      change = next(stream)
  except KeyboardInterrupt:
    print('\nInterrompu par l\'utilisateur')
  finally:
    print(f'\n{sent} événements envoyés, vidage du buffer du producteur...')
    producer.flush(60)
    print('Producteur fermé.')


if __name__ == '__main__':
  main()
