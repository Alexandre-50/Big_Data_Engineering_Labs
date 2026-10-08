# TP 05 — Structured Streaming (Wikimedia → Kafka → Spark)

```
tp05-structured-streaming/
├── compose.yaml                  # Kafka + Jupyter PySpark (fourni, inchangé)
├── admin.py                      # crée le topic "wikistreams" (fourni, inchangé)
├── wikistream_producer.py        # producteur enrichi : filtres en ligne de commande (étape 11)
├── notebooks/wikistream_pyspark.ipynb   # démo + explorations (étapes 10 et 12)
├── data/   jobs/                 # dossiers demandés à l'étape 1
```

## Étapes 1 à 9 — lancement

```bash
cd tp05-structured-streaming          # étapes 1-3 : dossiers et fichiers déjà en place
docker compose up -d                  # étape 4
docker logs pyspark_notebook          # étape 5 : copier le lien http://127.0.0.1:8888/lab?token=...

pip install confluent-kafka pywikibot # sur la machine hôte, si pas déjà fait
python admin.py                       # étape 6 : doit lister "wikistreams"
python wikistream_producer.py         # étape 7 : 10 min d'éditions de fr.wikipedia.org
```

Étape 8 : dans JupyterLab, ouvrir `work/wikistream_pyspark.ipynb` → *Run All*.
Étape 9 : `docker logs -f pyspark_notebook` pour suivre les sorties console.

> Plusieurs requêtes écrivent en même temps dans les logs. Pour une capture propre de chaque
> exploration, exécuter ses cellules une par une et arrêter les autres (dernière cellule).

## Étape 10 — agrégations ajoutées

Colonnes dérivées : `event_time` (vrai timestamp), `size_delta = length.new − length.old`,
`abs_delta`, `author_type` (bot / human).

| Exploration | Ce qu'on mesure |
|---|---|
| 0. Démo | éditions par bot, fenêtre 1 h |
| 1. Activité par minute | nb d'éditions, % de bots, contributeurs distincts, octets nets, taille moyenne / max des modifs |
| 2. Par wiki et type d'auteur | éditions/min, éditions mineures, octets modifiés, en moyenne glissante |
| 3. Alerte grosses modifs | chaque édition avec \|Δ\| ≥ 1000 octets (ajout ou suppression — vandalisme potentiel) |
| 4. Top pages / contributeurs | classement sur 10 min, interrogé en SQL depuis le notebook (sink `memory`) |

## Étape 11 — filtres au niveau du producteur

Le producteur utilise `EventStreams.register_filter` de pywikibot, piloté par des options :

```bash
python wikistream_producer.py --wiki en.wikipedia.org                      # autre langue
python wikistream_producer.py --wiki fr.wikipedia.org --wiki de.wikipedia.org  # plusieurs wikis
python wikistream_producer.py --type edit --type new                       # éditions + créations
python wikistream_producer.py --title "Paris" --title "France"             # pages précises
python wikistream_producer.py --title-contains football                     # titre contenant un mot
python wikistream_producer.py --namespace 0 --bots exclude                 # articles, humains seulement
python wikistream_producer.py --min-size 500 --minutes 5                   # grosses modifs, 5 min
python wikistream_producer.py --since 2026-10-08T08:00:00Z                 # rejouer l'historique (≤ 7 jours)
```

Comment ça marche :
- `register_filter(cle=valeur)` garde les événements dont le champ vaut cette valeur ;
  avec une **liste**, il suffit qu'une des valeurs corresponde (`server_name=['fr…', 'de…']`).
- Plusieurs filtres enregistrés sont combinés en **ET** (`ftype='all'` par défaut) ;
  `ftype='any'` donne un OU, `ftype='none'` exclut.
- On peut passer une **fonction** pour une condition libre (titre contenant un mot, taille minimale).

Filtrer côté producteur réduit le volume envoyé dans Kafka ; on peut aussi filtrer côté Spark
(`.filter(...)`, comme l'exploration 3), ce qui garde tout dans Kafka et permet plusieurs
consommateurs avec des filtres différents.

## Étape 12 — fenêtres tumbling et sliding

| | Tumbling (exploration 1) | Sliding (explorations 2 et 4) |
|---|---|---|
| Code | `window(event_time, "1 minute")` | `window(event_time, "5 minutes", "1 minute")` |
| Recouvrement | non : chaque événement est dans **1** fenêtre | oui : chaque événement est dans **5** fenêtres (durée / pas) |
| Lecture | photo minute par minute, pics visibles | moyenne mobile, courbe lissée |
