# Exploration - calendrier « historique de visionnage »

> Note de conception issue d'une session d'exploration (2026-07-27). Aucun code n'a été écrit ;
> rien n'est tranché. À reprendre avec les contraintes ci-dessous en tête si cette entité est un
> jour implémentée.

## Idée

Ajouter une 2e entité `calendar` distincte (« Historique de visionnage » / `watch_history`) à côté
de `release_calendar` (`custom_components/betaseries/calendar.py`), montrant les épisodes vus avec
leur date réelle de visionnage plutôt que leur date de diffusion.

## Piste `/planning/member` - écartée

Bornée à la fenêtre de mois du `PlanningCoordinator` (défaut 2/2 mois autour du mois courant) : un
visionnage récent d'un épisode diffusé il y a plusieurs années serait hors fenêtre, jamais fetché.
Le seul candidat trouvé sur cet endpoint (`user.seen_date`, format `"YYYY-MM-DD HH:MM:SS"`) est
donc inutilisable seul pour un historique complet.

## Piste `GET /timeline/member` - viable, mais plus complexe que prévu

Vérifié via `bruno/Timeline/member.bru` (exemple réel sauvegardé, 100 events).

### Paramètres

| Paramètre              | Rôle                                                   | Notes                                                                                                          |
| ---------------------- | ------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------- |
| `id`                   | membre ciblé                                           | requis                                                                                                         |
| `nbpp`                 | taille de page (max 100)                               |                                                                                                                |
| `since_id` / `last_id` | pagination par curseur d'ID d'event                    | pas de borne de mois → peut remonter arbitrairement loin dans le temps                                         |
| `types`                | filtre par type d'événement, liste séparée par virgule | **valeurs non documentées** dans `openapi.json` (juste `"type": "string"`) - déduites empiriquement ci-dessous |

### Types d'événements observés (échantillon de 100)

| Type             | Occurrences | Rôle                       |
| ---------------- | ----------- | -------------------------- |
| `markas`         | 67          | épisode marqué vu          |
| `season_watched` | 14          | saison entière marquée vue |
| `add_serie`      | 6           | série ajoutée au compte    |
| `badge`          | 5           | badge obtenu               |
| `archive`        | 5           | série archivée             |
| `unarchive`      | 2           | série désarchivée          |
| `del_serie`      | 1           | série retirée du compte    |

### `markas` (épisode marqué vu)

Confirmé par le texte `html` (ex. _"vient de regarder Silo S03E04..."_). Champs utiles :

- `ref_id` (int) : id de l'épisode BetaSeries - même id que celui utilisé par `/planning/member`
  et par les services v3 (§8 CLAUDE.md), donc croisable/actionnable de la même façon.
- `date` : `"YYYY-MM-DD HH:MM:SS"` - même format que `seen_date`, correspond à l'heure réelle du
  visionnage (pas la diffusion).
- `html` : contient le code SxxEyy et le titre (série + épisode) mais en HTML avec un lien - à ne
  pas parser pour en extraire des données structurées (fragile), sert tout au plus d'aperçu texte.

Un filtre `types=markas` isolerait directement ce type d'event côté API, sans tri côté client (non
testé explicitement - vérifié seulement en creux, sur un appel sans filtre actif).

### `season_watched` (saison entière marquée vue)

- `ref_id` est **toujours 0** (inutilisable) ; l'identité se lit dans `ref`, une string au format
  `"{show_id}.{season_number}"` (ex. `"13381.1"` = show 13381 saison 1).
- `data` est toujours `[]` - **aucune liste d'épisodes individuels**, aucun détail structuré.
- Un seul timestamp `date` pour toute la saison marquée d'un coup.

Impossible de reconstruire, à partir de ce seul event, quels épisodes précis ont été vus ni leur
date individuelle. Deux options si on veut couvrir ce cas dans le calendrier :

- **(a)** un seul event résumé « saison entière » par `season_watched`, sans détail par épisode
  (simple, grossier) ;
- **(b)** croiser avec `GET /shows/episodes?id={show_id}&season={n}` pour lister les épisodes de
  la saison et générer un event par épisode avec la même `date` approximative (plus cohérent avec
  le calendar actuel par épisode, mais 1 appel API supplémentaire par `season_watched` rencontré).

Non tranché.

### Consolidation à la complétion d'une saison (vérifié par l'utilisateur)

Quand tous les épisodes d'une saison finissent par être marqués vus (un par un, ou via
`mark_season_watched`), **les events `markas` individuels de ces épisodes disparaissent de la
timeline**, remplacés par un seul event `season_watched` qui résume toute la saison. Ce n'est donc
pas qu'un chevauchement logique (deux events qui coexisteraient pour le même contenu) - l'API fait
une vraie consolidation rétroactive côté timeline.

### Démarquage (vérifié par l'utilisateur)

Démarquer un épisode ne crée **pas** de nouvel event « démarquage » - il **retire rétroactivement
l'event `markas` existant** de la timeline. L'API reflète l'état courant des actions, pas un pur
journal d'audit immuable où chaque action (y compris son annulation) laisserait sa propre trace.

## Conséquences pour le modèle de cache

Un `TimelineCoordinator` devrait indexer son cache **par `episode_id`**, pas par event brut de la
timeline - c'est la seule granularité qui marche pour un calendar « par épisode » et qui permet de
résoudre `season_watched` en épisodes individuels.

Traitement envisagé par type d'event rencontré :

- `markas` → `cache[ref_id] = {seen_date: date, ...}` (ajoute/écrase l'entrée de cet épisode).
- `season_watched` → résoudre via `GET /shows/episodes?id={show_id}&season={n}`, puis
  `cache[episode_id] = {seen_date: date}` pour chaque épisode de la saison (même `date` pour tous).
- démarquage → `del cache[episode_id]`, mais **aucun event dédié ne le signale** (voir ci-dessus) -
  la seule façon de le détecter est de constater qu'un `markas` déjà en cache a disparu du flux.

### Le curseur `since_id`/`last_id` ne peut pas être suivi en confiance (append-only)

Puisqu'un démarquage retire un event passé sans jamais émettre de nouvel event, avancer le curseur
`last_id` seul ne peut **jamais** détecter cette disparition (on ne regarde que ce qui est plus
récent que le curseur). Il faut donc combiner :

1. l'avancée incrémentale du curseur pour capter les nouveaux `markas`/`season_watched` (rapide,
   peu de volume par refresh) ;
2. une **re-vérification périodique d'une fenêtre récente** (re-fetch sans curseur, ou `last_id`
   reculé volontairement), pour détecter les disparitions et purger le cache en conséquence.

Ce compromis est analogue à celui déjà fait par `PlanningCoordinator`, qui refetch systématiquement
le mois courant en entier (au lieu de lui faire confiance une fois en cache) précisément parce que
`seen` peut changer après coup (voir §6 CLAUDE.md).

### Faux positifs dus à la consolidation de saison

Un `markas` individuel qui disparaît du flux ne signifie **pas forcément** un démarquage - il peut
avoir été absorbé par un `season_watched` qui couvre toujours cet épisode (cf. consolidation
ci-dessus). Un algorithme naïf (« id disparu du re-fetch de fenêtre → reset dans le cache »)
produirait des faux positifs : des épisodes toujours vus seraient à tort marqués comme démarqués.

Il faut donc, à chaque re-vérification de fenêtre, résoudre les `season_watched` rencontrés
**avant** de comparer les ids et conclure qu'un épisode manquant est vraiment démarqué (et pas
juste réabsorbé dans un résumé de saison).

## Note annexe : pourquoi pas un calendrier HA éditable ?

Envisagé un temps comme moyen d'éviter la gestion d'un cache incrémental. Écarté : `CalendarEntity`
(`homeassistant/components/calendar/__init__.py`) ne fait aucun diff lui-même - `async_get_events`
est rappelée à chaque demande (vue Lovelace, websocket, service `calendar.get_events`) et reconstruit
la réponse en entier à partir de ce que l'entité a en mémoire. Rendre le calendar éditable
(`async_create_event`/`async_delete_event`) ne supprimerait donc pas le besoin d'un cache
incrémental - ça le déplacerait vers une API calendar plus lourde à opérer correctement (gestion
d'UID, pas de transaction atomique simple) que `homeassistant.helpers.storage.Store`. Par ailleurs,
un event de sortie (`release_calendar`) est un fait immuable une fois publié (cohérent avec un
calendar en lecture seule), alors qu'un marquage « vu » peut être corrigé après coup côté BetaSeries

- mais cette distinction ne change rien à la conclusion : dans les deux cas, la source de vérité
  reste le compte BetaSeries, pas le calendar HA.

## Reste à trancher avant d'implémenter

1. `season_watched` : option (a) event résumé vs (b) dépliage par épisode via `/shows/episodes`.
2. Récupérer titre de série/code SxxEyy/poster à partir du seul `ref_id` (pour `markas`) nécessite
   un appel supplémentaire (`GET /episodes/display?id=...`, pattern bulk déjà utilisé en v2bis pour
   `/shows/display`) - pas de champs structurés directement dans l'event timeline pour ça.
3. Pas de coordinator existant pour cette source : ce serait un nouveau coordinator (pas une
   extension du `PlanningCoordinator`), avec sa propre logique de pagination/cache (curseur d'ID,
   fenêtre de re-vérification périodique) - architecture à concevoir avant de coder quoi que ce soit.
4. Tester `types=markas` explicitement (vérifié seulement en creux jusqu'ici, sur un appel sans
   filtre actif).
