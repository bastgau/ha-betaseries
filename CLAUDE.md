# CLAUDE.md - Intégration Home Assistant « BetaSeries »

> Fichier de reprise de contexte. Objectif : développer un **custom component HACS**
> pour BetaSeries (suivi de séries/films), en respectant les normes et la philosophie
> Home Assistant. Ce document condense les décisions déjà prises et ce qui reste à faire.

> ⚠️ **Ce fichier est de la prose : il ne casse pas, il ment.** Dernière resynchronisation le
> **2026-08-01**. Avant lui, il affirmait un `api.py` disparu, un bump de store jamais fait, un
> capteur qui avait changé de nature et une borne d'options divisée par quatre - le tout sans qu'un
> seul test ne rougisse. **Sur un point qui décide de quelque chose, vérifier dans le code avant de
> s'y fier.** Deux erreurs de cette journée viennent exactement de là : un chiffre de trafic
> extrapolé d'une note au lieu du code, et un commentaire de `const.py` qui contredisait ses propres
> constantes une minute après leur modification.

## Conventions de travail

- Explications en **français**, commentaires de code **en anglais**.
- Réponses concises ; distinguer toujours **vérifié** (avec preuve/source) de **déduit/supposé**.
- Ne rien coder qui touche au comportement produit sans validation de l'utilisateur.
- **Mesurer plutôt qu'estimer.** Les constats qui ont tenu dans la revue du 2026-08-01 sont ceux
  vérifiés en exécutant quelque chose ; ceux qui sont tombés étaient extrapolés.

## Légende de statut

- ✅ **figé** (vérifié, décidé) · 🟡 **à confirmer** (hypothèse) · 🧪 **à tester** (Bruno, avec clé)

---

## 1. Périmètre - découpage en versions

Custom component HACS pour un compte membre BetaSeries.

**Livré** (v1 → v3, tout est en place pour Show/Episode/Season) :

- `sensor` : stats du compte (`/members/infos`), les deux capteurs de dates de sortie
  (`/planning/member`), la liste à rattraper (`/episodes/list`), un capteur diagnostic. Voir §5.
- `binary_sensor` : épisodes / films disponibles.
- `calendar` : calendrier des sorties.
- `button` : trois boutons de purge de cache, désactivés par défaut.
- `diagnostics` : agrégats uniquement, jamais un titre de série (voir `diagnostics.py`).
- Auth par device flow ou login/mot de passe (choix au premier écran, voir §3), reauth, OptionsFlow.
- **v3** : 10 services (marquer/démarquer vu épisode/saison, noter/dénoter épisode/saison/série) -
  périmètre restreint à Show/Episode/Season (arbitrage #6), routes testées via Bruno avant
  implémentation. Voir §8. Plus `delete_token`, et `search_shows`/`add_show`/`remove_show`
  (recherche catalogue depuis la card, voir §8) : **14 services au total**, toutes routes
  vérifiées via Bruno.

**À faire** :

- **v3 - films** : `rate_movie`/`unrate_movie` laissés de côté faute de besoin identifié - à faire
  si le besoin se confirme, même démarche (Bruno d'abord). Voir §8.
- Pas de v4 prévue ; on avisera selon les retours d'usage (`set_movie_status` reste un candidat si
  le besoin se confirme).

> Le découpage v1/v2/v2bis a servi à cadencer le développement ; il n'a plus de valeur descriptive
> aujourd'hui et le README ne l'utilise plus. Ne pas s'en servir pour raisonner sur l'existant :
> se référer à §5 (entités) et §6 (architecture), qui décrivent l'état réel.

## 2. Distribution & environnement ✅

- Cible : **custom component HACS** (pas le core pour l'instant).
- Client API **bundlé** dans le sous-paquet `custom_components/betaseries/betaseries/`
  (pas `api.py` : ce fichier unique a été éclaté en un paquet, une classe par fichier, voir §7).
  - Justification vérifiée : la règle « lib externe sur PyPI » est une exigence _core_,
    pas imposée en custom/HACS (dev docs + tuto officiel).
  - Si un jour on vise le core → extraire le sous-paquet en package PyPI.
  - **Ce sous-paquet est dimensionné par l'API, pas par l'intégration.** Plusieurs points d'entrée
    n'ont aucun appelant côté HA (`fetch_timeline`, `fetch_episodes_by_id`, `fetch_show_episodes`,
    `fetch_episodes_to_watch`, les helpers de navigation sur les modèles, toute la hiérarchie
    d'évènements de timeline). C'est **délibéré** : le critère est la fidélité à l'API, pas
    « quelque chose l'utilise-t-il ». Ne pas élaguer sur cette base - c'est écrit en tête de
    `custom_components/betaseries/betaseries/README.md`, qui documente aussi tout le sous-paquet.
- **Autonome dans sa source, pas dans son chemin d'import** (vérifié en venv propre) : importer
  `custom_components.betaseries.betaseries.<x>` exécute d'abord `custom_components/betaseries/__init__.py`,
  qui importe Home Assistant. Contourner en mettant `custom_components/betaseries` sur `sys.path` est
  pire : le `calendar.py` de l'intégration masque alors le `calendar` de la stdlib, qu'aiohttp importe.
  L'extraction PyPI est donc la seule vraie sortie.
- Cible : **Home Assistant 2026.7.0 minimum**, **Python 3.14** (devcontainer).
- Tooling : ruff/pylint/pyright. `ruff target-version = "py313"` **volontairement** (contourne un bug
  formatter ruff 0.15.x qui casse `except (A, B):` sous py314) ; repasser à py314 quand corrigé.
- Variables d'env : projet non-secret dans `.devcontainer/.common-env` (committé : `PROJECT_NAME`,
  `PROJECT_ROOT_PATH`, `INTEGRATION_DOMAIN=betaseries`, `INTEGRATION_NAME=BetaSeries`).
  **Pas de `.env` racine** (rien ne le consomme ; le `.env` process-env de Bruno vivrait dans `bruno/`,
  et Bruno ne tourne pas dans le devcontainer sauf à installer `@usebruno/cli`). Fichiers statiques
  (hacs.json, pyproject.toml, manifest.json) + CI = valeurs en dur / bloc `env:` GitHub Actions.
- HACS default store (si soumission) exige : README avec install (HACS + manuel),
  options du config flow, et **table des entités** (entity_id, unité, sens).

### CI ✅

Cinq workflows. Les deux qui comptent au quotidien :

- **`lint.yml`** : 5 outils (ruff check, ruff format, pylint, pyright, docstring-linter) × 3
  périmètres (`client`, `integration`, `tests`), en matrice.
- **`test.yml`** : 2 jobs, `client` et `integration`, chacun avec **son propre plancher de
  couverture à 95 %** (`--cov-fail-under=95`).

⚠️ **Pas de filtre `paths:` au niveau du workflow, dans ni l'un ni l'autre** (retiré le 2026-08-11).
Un required status check (branch protection : `client`, `integration`, `tests`) reste bloqué en
« Expected — Waiting for status to be reported » si le workflow qui le produit ne se déclenche
jamais - ce qui arrivait sur toute PR ne touchant aucun `.py` (doc, README, `bruno/`...), puisque
les deux `on.pull_request.paths` filtraient déjà à ce niveau. Les deux workflows tournent
maintenant sur chaque push/PR ; un job `changes` (en tête, via `dorny/paths-filter`) calcule si les
chemins pertinents ont changé et expose `outputs.python`, que `client`/`integration`/`lint`
consomment via `if: needs.changes.outputs.python == 'true'`. Un job dont le `if` est faux est
**skipped**, pas absent - GitHub Actions traite un skip comme satisfaisant un required check,
contrairement à un contexte qui n'est jamais rapporté. La liste de chemins surveillés par
`paths-filter` dans chaque workflow reprend exactement l'ancien bloc `paths:`.

Le découpage n'est pas cosmétique : **chaque moitié couvre 100 % de ce qu'elle possède, seule.**
Si une branche du client finit par n'être atteinte que via un test HA, ça se voit comme une chute
de couverture au lieu de se noyer dans un run combiné. Le job `integration` utilise
`.coveragerc-integration`, qui soustrait le client de la mesure (`pytest-cov` sait ajouter des
chemins, jamais en retrancher un).

- **Version de HA épinglée en dur**, pas résolue au run time (bascule faite le 2026-08-06, commit
  `9e027ba` - ce que ce paragraphe affirmait avant, une résolution dynamique via
  `https://pypi.org/pypi/homeassistant/json`, décrivait l'état **pré**-`9e027ba` et a survécu sans
  être corrigé à la resynchronisation du 2026-08-01, elle-même antérieure). `test.yml` n'appelle
  plus pypi.org et ne passe plus de `homeassistant==<version>` au job : seul
  `requirements-test-integration.txt` fixe la version, via `pytest-homeassistant-custom-component`
  **épinglé exactement** (`==0.13.348`, qui tire `homeassistant==2026.7.4` en transitif) plutôt que
  laissé sans version.
  - Corollaire inversé par rapport à l'ancien texte : **la CI est déterministe** - un run ne rougit
    plus tout seul entre deux commits identiques, mais elle ne dit plus non plus « ça marche-t-il
    avec le HA que les gens font tourner aujourd'hui ». Elle répond « ça marche-t-il avec la version
    de HA fixée dans ce fichier ».
  - Motif du pin, documenté dans le fichier lui-même : laisser
    `pytest-homeassistant-custom-component` sans contrainte de version fait remonter des **bêtas**
    HA non publiées (vérifié historiquement : 0.13.351 exigeait `homeassistant==2026.8.0b3`), donc
    un pin exact vers une release qui précède ce comportement est le seul moyen d'obtenir du stable.
  - ⚠️ Ce pin est un **entretien manuel récurrent**, pas un `TODO` isolé : le fichier dit
    explicitement de le bumper « quand homeassistant est upgradé », mais rien ne rappelle qu'il
    l'est - aucun job ne compare la version pinnée à la dernière stable HA. Vérifier ce fichier
    avant de faire confiance à un run vert comme preuve de compatibilité avec le HA du jour.
- `scripts/lint [client|integration|tests|src|all]` calque exactement la matrice CI, pour qu'un vert
  local prédise un vert distant. `scripts/test` lance la suite complète (plancher 95 % via
  `pyproject.toml`).
- ⚠️ **Toujours valider une modif de CI en venv propre, jamais dans le devcontainer** : celui-ci a
  tout d'installé et masque les dépendances manquantes. C'est exactement comme ça que le périmètre
  `tests` du lint est passé en local tout en étant rouge en CI (ni `pytest` ni
  `pytest_homeassistant_custom_component` dans `requirements-lint.txt`).

## 3. Authentification - device flow, ou login/mot de passe ✅

Gabarit : intégration **Tado** (`homeassistant/components/tado/config_flow.py`).
Le polling vit dans le client (`betaseries/auth.py`) ; le config flow reste mince.

### Endpoints (vérifiés)

- `POST /oauth/device` (form-urlencoded, `client_id`) →
  `{ device_code, user_code, verification_url, expires_in: 1800, interval: 5 }`
- `POST /oauth/access_token` (form-urlencoded, `client_id` + `client_secret` + `code=<device_code>`)

### Logique de poll (vérifiée sur les 2 états)

- **En attente** : HTTP `400`, corps `{ "errors": [{ "code": 2001, "text": "En attente de l'identification." }] }`
  → tester sur le **code numérique 2001** (pas le texte, localisable), `sleep(interval)`, retry.
- **Succès** : HTTP `200`, corps `{ "access_token": "...", "token_type": "bearer" }`.
- **Autre erreur** (secret invalide, code expiré) → sortie en échec (pas de retry infini).
- Garde-fou global : borne la boucle sur `expires_in` (1800 s) → step `timeout`.

### Token

- JSON `{access_token, token_type:"bearer"}`, **pas de refresh_token ni expires_in**.
- **Peut être rejeté** ✅ (vérifié en prod, pas juste supposé) → le reauth flow (déjà prévu, gabarit
  Tado) prend le relais - voir §3bis pour la signature exacte de ce rejet.

### Requêtes API (vérifié)

- Base URL : `https://api.betaseries.com`
- Headers obligatoires : `X-BetaSeries-Key: <api_key>` + `X-BetaSeries-Version: 3.0`
  - `Authorization: Bearer <token>` pour les appels authentifiés.
- Param `fields` **inopérant** ❌ sur `/members/infos` et `/planning/member` (vérifié via Bruno :
  payload complet renvoyé à l'identique avec ou sans `fields`, silencieusement ignoré). Le code
  ne tente donc pas d'alléger le payload côté requête ; le parsing ne lit que les clés utiles.
- Param **`locale`** ✅ (vérifié via le spec OpenAPI officiel - `components.parameters.LocaleParam`,
  `description: "Locale parameter to specify language preference"`, `default: "fr"`) - référencé
  (via `$ref`) par les 5 endpoints du client (`/members/infos`, `/planning/member`,
  `/shows/display`, `/shows/episodes`, `/episodes/list`) et bien d'autres, mais **absent du dump
  JSON par défaut** de chaque endpoint (visible seulement en résolvant les `$ref` vers
  `components.parameters`). Envoyé sur chaque requête (`Client._params`), valeur choisie par
  l'utilisateur (`fr`/`en` uniquement, arbitrage #9) - config flow (étape `user`) + OptionsFlow.
- **Identifiants invalides sur les endpoints authentifiés** ✅ (2 codes vérifiés en prod, via le log
  ajouté dans `Client._raise_for_error`) : contrairement au device flow (`/oauth/access_token`),
  un problème d'identifiants sur `/members/infos`, `/planning/member`, `/shows/display`,
  `/shows/episodes`, `/episodes/list` renvoie HTTP **400** (pas 401), avec deux codes distincts
  observés selon la cause :
  - `{"code": 1001, "text": "Mauvaise clé API."}` → `X-BetaSeries-Key` (api_key/client_id) invalide.
  - `{"code": 2001, "text": "Données d'identification incorrectes."}` → access token rejeté - même
    code numérique `2001` que l'état "en attente" du device flow (§3), signification différente.
    `client.py` (`Client._raise_for_error`, `const.INVALID_CREDENTIALS_ERROR_CODES = {1001, 2001}`)
    détecte les deux et lève `AuthError` au même titre qu'un 401, pour déclencher le reauth flow
    (`ConfigEntryAuthFailed`) plutôt qu'un `ConfigEntryNotReady` en boucle.
- **Le client ne logge jamais lui-même** ✅ (choix d'architecture) : `Error`/`AuthError`
  (`betaseries/exceptions.py`) portent `status`/`body` (réponse brute qui a déclenché l'erreur) en
  attributs plutôt que de logger un warning directement dans `client.py`. C'est `coordinator.py`
  (`_log_auth_failure` pour les `AuthError`, un `_LOGGER.debug` pour les `Error` génériques) qui
  lit ces attributs et logge - le logger utilisé est donc toujours celui de `coordinator.py`
  (`custom_components.betaseries.coordinator`), jamais celui du sous-package `betaseries/`. Deux
  raisons : (1) une lib ne devrait pas avoir d'effet de bord de logging, l'appelant décide ; (2) le
  logger d'un module niveau `custom_components.betaseries.betaseries.client` n'est un descendant de
  `custom_components.betaseries` (et donc couvert par le réglage `logger.logs` de l'utilisateur)
  que tant que ce sous-package reste bundlé - si `betaseries/` est un jour extrait en package PyPI
  (§2, v4), son nom de module changerait complètement (ex. `pybetaseries.client`), cassant cet
  héritage ; en gardant tout le logging côté `coordinator.py`, ce risque disparaît.
- **Rotation de clé/secret** ✅ : BetaSeries ne permet pas de régénérer uniquement le
  `client_secret` d'une application existante - il faut supprimer l'application sur
  betaseries.com et en recréer une (nouveau `client_id` + `client_secret`). **Aggravant** : cette
  suppression n'est elle-même pas self-service - il faut passer par le support BetaSeries (pas de
  bouton "supprimer" accessible directement sur le site). En cas de fuite du `client_secret`, la
  rotation complète dépend donc d'un délai de traitement côté support, pas juste d'une manipulation
  immédiate côté utilisateur. Le reauth flow HA (écran de confirmation → nouveau device flow)
  permet de ressaisir une nouvelle paire clé/secret sans supprimer/recréer l'entrée de config HA
  elle-même dès que la nouvelle app existe ; c'est la création/suppression de l'app côté
  betaseries.com qui n'est pas en libre-service. Un message de log explicite (`coordinator.py`,
  `_log_auth_failure`) rappelle ce point quand un `AuthError` survient.
- **Reauth avec un compte BetaSeries différent** ✅ (gabarit Tado, mécanisme HA standard) :
  `config_flow.py` appelle `self._abort_if_unique_id_mismatch()` après le nouveau device flow -
  si l'`id` du membre authentifié diffère de celui de l'entrée reauthentifiée, le flow **abort**
  (raison `unique_id_mismatch`) et **n'écrase rien** : l'entrée garde son `unique_id`/`access_token`
  d'origine, le nouveau token obtenu pendant cette tentative est juste jeté. Pour changer de compte
  sur une entrée existante, il faut supprimer/recréer l'intégration - le reauth ne permet de
  renouveler les identifiants que **pour le même compte**. Chaîne de traduction
  (`strings.json`/`translations/{en,fr}.json`, clé `config.abort.unique_id_mismatch`) présente pour
  ce cas (`_abort_if_unique_id_mismatch()` utilise ce nom de raison par défaut - sans traduction,
  HA afficherait la clé brute).
- **Mode d'auth alternatif via login/mot de passe** : `POST /members/auth?login=...&password=...`
  (`bruno/Members/auth.bru`, vérifié - renvoie `{"user": {...}, "token": "...", "hash": "...",
"errors": []}`) donne un `token` utilisable en `Authorization: Bearer` sur les endpoints
  authentifiés comme un access_token OAuth classique (testé en enchaînant `auth.bru` → `infos.bru`
  avec ce token). Limite connue : le token est **stable** (jamais régénéré) et **n'est pas révoqué
  par un changement de mot de passe du compte** - un token compromis resterait donc utilisable
  indéfiniment, sans moyen de rotation. Accepté malgré cette limite : la rotation du `client_secret`
  du device flow n'est **pas non plus** self-service (suppression/recréation de l'app via le
  support BetaSeries, voir ci-dessus) - la différence entre les deux modes n'est donc pas
  « révocable / pas révocable » mais « pas de geste de rotation rapide, dans les deux cas, sous des
  formes différentes ». Ce mode alternatif existe en complément du device flow, notamment pour
  contourner un blocage connu du device flow dans l'appli mobile Android (voir le
  `## Troubleshooting` du README).
  **Implémentation** : `Auth.authenticate_with_password(login, password)` (`betaseries/auth.py`) -
  seule méthode de `Auth` qui n'a pas besoin de `client_secret` (paramètre optionnel du
  constructeur, `""` par défaut). Contrairement au device flow, une seule requête bloquante, pas de
  polling - et la réponse porte déjà `user.id`/`user.login`, donc pas de `fetch_member_identity`
  supplémentaire. `config_flow.py` ajoute une première étape `user` en `async_show_menu` (deux
  options : `device_credentials` - l'ancien formulaire api_key/client_secret/locale, renommé - et
  `password_credentials` - api_key/login/password/locale) ; les deux convergent vers
  `_async_create_or_update_entry()` une fois access_token + identité connus. Le menu réapparaît
  aussi bien en reauth qu'après un timeout de device code (plutôt que de retourner directement au
  formulaire device) : un timeout est justement le symptôme qui motive ce second mode, donc autant
  laisser l'utilisateur basculer dessus à ce moment-là plutôt que de ne lui proposer que de
  réessayer la même chose. Rien n'est persisté de plus qu'avant dans `entry.data` (`api_key` +
  `access_token` uniquement, quel que soit le mode - ni `client_secret` ni login/mot de passe ne
  sont stockés).

### Prérequis utilisateur ✅

- **1 clé API BetaSeries par utilisateur** (`client_id` + `client_secret`), à créer sur le site.
  Non partageable (secret exposé en repo public). À documenter dans le README.
- Étape 1 du config flow = saisie `api_key` + `client_secret`, avant l'écran de code.

### Détails HA vérifiés (source : code HA 2026.8.dev)

- `async_show_progress(*, step_id, progress_action, description_placeholders, progress_task)` -
  `progress_task` **doit** être passé (sinon warning + `deprecated_show_progress`).
- Bonus dispo : `async_update_progress(0..1)` (barre déterminée ; inutile pour attente indéterminée).

---

## 4. Modèle de données (vérifié via Bruno)

### `GET /members/infos` → source des sensors + binary_sensor

Retourne `member` (dont `id`, `login`, `xp`) et `member.stats`.

- `member.id` → `unique_id` de l'intégration · `member.login` → titre de l'entry.
- **Temps en minutes** (vérifié par cohérence arithmétique : ~45 min/épisode, ~104 min/film).
- Champs utiles : `episodes_to_watch, shows_to_watch, movies_to_watch, shows_current,
badges, progress (%), time_to_spend, time_on_tv, shows, shows_finished, episodes,
movies, streak_days, member_since_days, episodes_per_month, favorite_genre`.
- `progress` = `episodes / (episodes + episodes_to_watch) * 100` (taux d'avancement global).

### `GET /planning/member` → source calendar + les deux capteurs de dates de sortie

`{ "episodes": [ ... ] }`. Par épisode :

- `date` (`"YYYY-MM-DD"`) → **all-day** (pas d'heure) · `show.title` + `code` (`"S03E04"`) → titre event
- `title` (nom épisode) → description
- `user.seen` (bool) → **plus aucune entité ne le lit** (voir le cache ci-dessous). Le calendrier ne l'a jamais filtré (c'est un calendrier de **sorties**), et les deux
  capteurs `previous_episode_airing` / `next_episode_airing` répondent « qu'est-ce qui est sorti /
  va sortir », pas « que dois-je regarder ». Seul `diagnostics.py` le compte encore, à titre
  informatif. La question « que me reste-t-il à voir » est traitée par `/episodes/list` (§4bis)
- `platform_links[].platform` (`"Netflix"`, `"Apple TV"`) → attribut · `resource_url` → lien
- `id, show.id, season, episode` → cibles des services
- `show.description` (synopsis de la série) → présent uniquement sur cet endpoint (absent des
  sous-objets `show` de `/shows/episodes` et `/episodes/list`, vérifié) - lu par `_parse_episode`
  (`Show.description: str | None`, `None` via `.get` sans défaut si absent). Utile car
  `episode.description` (résumé de
  l'épisode) est souvent **vide pour un épisode pas encore diffusé** (vérifié, exemple réel dans
  `bruno/Planning/member.bru`) - le fallback `episode.description or episode.show.description`
  est implémenté côté HA (`calendar.py`), pas dans le client (cohérent avec l'arbitrage déjà pris
  de ne jamais faire ce genre de fallback dans `_parse_episode`, voir sous-package README).
- `show.slug` → même sous-objet, même endpoint uniquement (vérifié absent de `/episodes/list`,
  pas vérifié présent/absent sur `/shows/episodes` faute d'exemple Bruno). Lu en
  `Show.slug: str | None` (`None` via `.get` sans défaut si absent, même logique que
  `description`). `Show.resource_url` (propriété, pas un champ stocké) le dérive via le pattern
  d'URL BetaSeries vérifié sur `/shows/display` (`https://www.betaseries.com/serie/{slug}`) -
  aucun endpoint « episode » ne renvoie directement l'URL de la série elle-même (seulement celle
  de l'épisode, `Episode.resource_url`), d'où ce calcul plutôt qu'une lecture directe.
- **Cache du planning** (`_episode_to_dict`/`_episode_from_dict`, `PLANNING_STORE_VERSION`) :
  persiste `show_description`/`show_slug`, et **ne persiste plus `seen`**.
  - Le cache se justifie par « un mois passé ne change plus » : vrai d'une date de diffusion,
    **faux d'un statut de visionnage**. Un mois caché n'étant jamais refetché, un capteur qui
    lirait `seen` depuis le cache resterait figé sur un épisode déjà regardé pendant toute la
    fenêtre `months_behind` - d'où le retrait de ce champ de la sérialisation.
  - `Episode.seen` est donc `bool | None`, où **`None` veut dire « inconnu », jamais « pas vu »** :
    un filtre doit tester `is False`, pas la véracité. Un mois passé traverse le cycle
    sérialisation → désérialisation **dès le refresh qui le fetch** (écrit puis relu), donc il ne
    porte jamais de `seen`, quelle qu'en soit la provenance.
  - Pas de bump de version pour ce retrait : les entrées écrites avant portent encore la clé, elle
    est simplement **ignorée à la lecture** plutôt que crue.
  - ⚠️ **La discipline de bump n'a jamais été appliquée** : la constante vaut 1 alors que la forme
    sérialisée a changé au moins deux fois (`episode` → `number`, puis `+show_description/slug`).
    Le filet (`_CacheStore` jette toute version antérieure) est testé ; le geste qui l'arme ne
    l'est pas. Y penser à chaque changement de `_episode_to_dict`.
- ⚠️ Payload lourd (`characters`, `crew`…) et `fields` ne le réduit pas (voir §3) → filtré côté
  client via `month=YYYY-MM` (vérifié, voir §6/coordinator). Un `month` **antérieur** au mois
  courant n'est pas supporté par l'API, mais le mois courant lui-même renvoie tout son passé déjà
  écoulé (vérifié : épisodes datés avant aujourd'hui dans le mois en cours, `seen` vrai ou faux) →
  le calendrier ne peut pas remonter avant le début du mois courant, mais n'est pas limité au futur
  strict à l'intérieur de celui-ci.

### `GET /episodes/list` (vérifié) → repli calendrier / liste à voir.

- Param **`excludes`** ✅ (vérifié via Bruno, `bruno/Episodes/list.bru`) : allège le payload, contrairement
  à `fields` (§3, silencieusement ignoré). Accepte une liste séparée par des virgules, mais
  **seule la valeur `characters` retire réellement quelque chose** (vérifié) - la clé
  `characters` de chaque épisode revient alors en tableau vide, la forme du payload est donc
  inchangée et le parsing n'est pas impacté. Envoyé par HA (`WatchListCoordinator`) car aucune
  entité n'expose le casting ; côté client c'est un paramètre de l'appelant
  (`exclude_characters: bool = False`, cf. sous-package README) et non un choix de la lib - un
  booléen plutôt qu'une liste, justement parce qu'une seule valeur fonctionne.
  **Propre à cet endpoint** : les autres endpoints du client (dont `/planning/member`, pourtant
  tout aussi lourd en `characters`/`crew`) ne semblent pas le prendre en compte - inutile donc
  d'espérer alléger le planning par ce biais.

### `GET /shows/display?id=id1,id2,...` → posters **et note** des séries

Vérifié (Bruno, `bruno/Shows/display-[multiple].bru`) : accepte plusieurs `id` séparés par une
virgule → réponse `{"shows": [...]}` (tableau, un objet complet par id demandé), contre
`{"show": {...}}` (singulier) pour un seul id (`bruno/Shows/display.bru`). **Un seul appel groupé**
suffit donc pour toutes les séries actuellement dans la fenêtre de planning, pas un par série.
Champ utile : `images.poster` (aussi `images.show`/`banner`/`box`/`clearlogo`), URL publique sur
`pictures.betaseries.com` - **pas d'auth nécessaire pour l'afficher** (vérifié : `curl -I` sans
header → `200`, `cache-control: public, max-age=31536000`). `images.*` peut être entièrement `null`
(pas de poster pour cette série) → à gérer côté code (pas d'`entity_picture` plutôt qu'une URL
cassée). L'endpoint `GET /pictures/shows` (censé renvoyer l'image brute) est écarté : renvoie une
erreur Cloudflare en pratique, alors que `/shows/display` donne déjà tout ce qu'il faut en JSON.

### `GET /pictures/episodes?id=id` → vignette d'épisode, ❌ **exige une clé API**

Vérifié sur **4 ids** dont 3 valides, issus des réponses `/planning/member` sauvegardées dans
`bruno/` : **sans header, l'endpoint renvoie systématiquement `400` + `{"code": 1001, "text":
"Please set an API key."}`**, sans redirection.

⚠️ **Piège pour retester ça un jour** : BetaSeries répond `cache-control: private, max-age=14400`
sur cet endpoint, et **Cloudflare met malgré tout la réponse en cache et la ressert à des requêtes
anonymes**. Un `curl` sans header lancé peu après un appel authentifié peut donc recevoir un `302`
qui appartient à _quelqu'un d'autre_ (vérifiable à l'en-tête `x-betaseries-key` de la réponse et
`cf-cache-status: HIT`) et laisser croire à tort que l'endpoint est public. Forcer un cache `MISS`
(paramètre aléatoire) donne le vrai résultat : `400`. **Leçon générale : sur cet hôte, tester une
URL « publique » juste après un appel authentifié ne prouve rien - forcer un cache MISS.**

Conséquence : **inutilisable en `entity_picture`** (le navigateur du frontend HA charge l'URL sans
en-tête → image brisée, de façon non déterministe selon l'état du cache Cloudflare). La propriété
`Episode.images` qui construisait cette URL a été **supprimée** pour cette raison.

Le seul moyen de servir cette vignette serait un **proxy côté HA** (`HomeAssistantView`, motif de
`media_player` : `requires_auth = False` + vérification manuelle d'`Entity.access_token`, ~150
lignes + cache) - **écarté** : le poster de série ci-dessus est déjà public et suffit.

### `GET https://pictures.betaseries.com/...` (posters de `/shows/display`) → ✅ réellement public

Vérifié à froid (aucun en-tête, cache MISS) : `200 image/jpeg`, ~646 Ko,
`cache-control: public`. C'est **l'hôte des URLs `images.poster`** renvoyées par `/shows/display`
(§4 ci-dessus), et donc la seule source d'image utilisable directement en `entity_picture`.

### `GET /badges/badge?id=id1,id2,...` → même pattern bulk, vérifié

Idem : plusieurs `id` séparés par une virgule → `{"badges": [...]}` (tableau, vérifié via
`bruno/Badges/1 - Badges.bru`). Champ `picture_url`, URL publique sur
`www.betaseries.com/images/badges/...` (pas d'auth). Utile si on affiche un jour les derniers
badges obtenus avec leur icône plutôt qu'un simple compteur.

---

## 5. Entités (spec figée)

### sensor (source: MemberCoordinator)

| Entité              | Champ                    | device_class | unit | state_class      | enabled |
| ------------------- | ------------------------ | ------------ | ---- | ---------------- | ------- |
| Episodes to watch   | stats.episodes_to_watch  | -            | -    | measurement      | ✅      |
| Time to spend       | stats.time_to_spend      | duration     | min  | measurement      | ✅      |
| Progress            | stats.progress           | -            | %    | measurement      | ✅      |
| Shows not started   | stats.shows_to_watch     | -            | -    | measurement      | ✅      |
| Movies to watch     | stats.movies_to_watch    | -            | -    | measurement      | ✅      |
| Shows in progress   | stats.shows_current      | -            | -    | measurement      | ✅      |
| Badges              | stats.badges             | -            | -    | measurement      | ✅      |
| Shows total         | stats.shows              | -            | -    | measurement      | ✅      |
| Shows finished      | stats.shows_finished     | -            | -    | measurement      | ✅      |
| Episodes watched    | stats.episodes           | -            | -    | total            | ✅      |
| Time on TV          | stats.time_on_tv         | duration     | min  | total            | ✅      |
| Movies total        | stats.movies             | -            | -    | measurement      | ✅      |
| XP                  | member.xp                | -            | -    | measurement      | ✅      |
| Streak days         | stats.streak_days        | duration     | d    | measurement      | ✅      |
| Membership duration | stats.member_since_days  | duration     | d    | total_increasing | ✅      |
| Episodes per month  | stats.episodes_per_month | -            | -    | measurement      | ✅      |
| Favorite genre      | stats.favorite_genre     | -            | -    | -                | ✅      |

`Badges` porte en attribut la liste complète des badges obtenus (source `GET /members/badges`,
refetchée seulement quand `stats.badges` change - voir §6). Attribut **non enregistré au recorder**
(~10 kB pour 40 badges).

### sensor (source: PlanningCoordinator)

| Entité                  | Champ                                           | device_class | enabled       |
| ----------------------- | ----------------------------------------------- | ------------ | ------------- |
| Previous episode airing | dernier épisode déjà diffusé                    | timestamp    | ✅            |
| Next episode airing     | premier épisode à diffuser (aujourd'hui inclus) | timestamp    | ✅            |
| Calendar event count    | `len(planning)`, attribut = compte par mois     | -            | ❌ diagnostic |

### sensor (source: WatchListCoordinator)

| Entité               | Champ                                                  | state_class | enabled |
| -------------------- | ------------------------------------------------------ | ----------- | ------- |
| Shows to catch up on | `total` de `/episodes/list` (nb de séries à rattraper) | measurement | ✅      |

Attribut `shows` : les N premières séries avec leurs prochains épisodes (bornes `shows_limit` /
`episodes_limit`), plus `total_shows` / `total_episodes` qui sont les compteurs **globaux** de
l'endpoint et **ignorent ces bornes**. `shows` est **non enregistré au recorder** (~8,5 kB ; le
recorder jette _tous_ les attributs d'une entité au-delà de 16 kB).

**Attribut `data` (opt-in)** ✅ : sur `Shows to catch up on`, `Calendar event count`,
`Previous/Next episode airing` et `Suggestion of the day`, derrière l'option `upcoming_media_card`
(`entry.options`, défaut `False`) - voir §6/§9 pour le détail. Une seule option pour les cinq
sensors, pas une par sensor.

⚠️ `/episodes/list` trie les séries **alphabétiquement** et tronque à `shows_limit` : l'attribut
montre donc toujours les mêmes séries en A–D (10 sur 38 par défaut). Le paramètre `order`
(`account` | `smart`) est peut-être la réponse - **non testé**.

Arbitrage #1 (amendé) : les sensors « métier » sont tous `enabled` par défaut. Sont **désactivés**
par défaut : `Calendar event count` et les trois boutons - tous `entity_category: diagnostic`,
utiles au support, pas à l'usage.

> **Note state_class** _(vérifié conventions HA)_ : `Episodes watched` et `Time on TV` sont en **`total`**
> (pas `total_increasing`) car ils peuvent **diminuer** si on démarque un épisode - `total_increasing`
> interpréterait toute baisse comme un reset et fausserait les stats. `Membership duration` reste
> `total_increasing` (strictement monotone).
> **Note precision** : `Progress` renvoie `77.4699…` → `suggested_display_precision: 1`
> (idéalement aussi sur `Time to spend` / `Time on TV`).

### Les deux capteurs de dates de sortie - miroirs exacts

Ni l'un ni l'autre ne lit `seen` : ce sont des **dates de sortie**, pas une liste à regarder.

|                           | Groupe considéré                                   | Heure du timestamp |
| ------------------------- | -------------------------------------------------- | ------------------ |
| `previous_episode_airing` | la **dernière** date passée (`air_date < today`)   | minuit             |
| `next_episode_airing`     | la **première** date à venir (`air_date >= today`) | 23:59:59           |

BetaSeries ne donne jamais l'heure de diffusion : chacun épingle donc l'heure **dont il ne peut pas
se tromper**, pour que le rendu relatif du frontend (« dans 3 jours », « il y a 2 jours ») soit
toujours cohérent avec ce que le capteur annonce. Un épisode daté d'aujourd'hui appartient à
`next` jusqu'à la fin de la journée, donc les deux ne pointent jamais le même épisode.

**Départage à date égale** (plusieurs épisodes sortent le même jour) - fonction partagée
`_best_rated()` : meilleure note de la série d'abord, puis **plus grand `id` d'épisode**, comparé
numériquement (`"1001"` doit battre `"999"`). Une série sans note vaut 0 et perd - « non notée » et
« notée zéro » ne sont **pas** distinguées. La note ne départage qu'**entre épisodes du même jour** :
elle ne prime jamais sur la date.

La note vient de `notes.mean` dans `GET /shows/display`, **déjà appelé** pour les posters : elle est
cachée avec eux (forme `{show_id: {"images": {...}, "rating": 3.89}}`) et ne coûte aucune requête.

Attributs des deux capteurs : `episode_id`, `show_id`, `code`, `season`, `number`, `title`,
`show_title`, `platforms`, `resource_url`, plus `show_images` (non enregistré au recorder) et
`entity_picture` (le poster). `episode_id`/`show_id` sont ce que cibleront les services v3.
Home Assistant n'a pas d'équivalent pour les évènements de `calendar` (`CalendarEvent` n'a pas de
champ image) : le poster ne s'affiche donc que sur les sensors, pas dans la vue calendrier native.

### button (diagnostic, désactivés par défaut)

`Clean badges cache`, `Clean planning cache`, `Clean shows to catch up cache` : chacun vide le cache
d'un coordinator puis rafraîchit. C'est le **seul** moyen de reforcer un refetch de ce que
l'intégration considère immuable (détails de badges, mois passés, artwork).

### binary_sensor (source: MemberCoordinator) - v1

| Entité             | Logique                     | enabled                                       |
| ------------------ | --------------------------- | --------------------------------------------- |
| Episodes available | stats.episodes_to_watch > 0 | ✅                                            |
| Movies available   | stats.movies_to_watch > 0   | ✅ (arbitrage #2 : gardé, enabled par défaut) |

### calendar (source: PlanningCoordinator) - v2

1 event par épisode, all-day, titre `show.title - code`. Ni `async_get_events` (vue calendrier) ni
la propriété `event` (prochain évènement HA) ne filtrent sur `seen` : c'est un calendrier de
**sorties**, il répond « qu'est-ce qui sort », pas « que dois-je regarder ». Filtrer dans `event`
laisserait d'ailleurs l'état contredire les évènements que le calendrier affiche lui-même.

⚠️ `event` doit en revanche **ignorer les épisodes déjà diffusés** (`air_date >= today`). HA dérive
l'état de cette seule propriété et n'allume le calendrier que pendant l'évènement : retourner le
premier épisode du planning - trié par date, remontant des mois en arrière - figerait l'état sur
`off` en permanence (test de non-régression à dates relatives).

---

## 6. Architecture

- **3 coordinators** (`DataUpdateCoordinator`), tous partageant un seul `Client` :
  - **`MemberCoordinator`** : `GET /members/infos`, **15 min** par défaut → sensors + binary_sensors.
    - Les détails de badges (`GET /members/badges`) ne sont refetchés que quand `stats.badges` -
      le compteur déjà présent dans `/members/infos` - change. Compteur et liste sont persistés
      ensemble, donc un redémarrage de HA ne force pas de refetch.
  - **`PlanningCoordinator`** : `GET /planning/member` (+ `month=YYYY-MM`), **60 min** par défaut
    → calendar + les deux capteurs de dates de sortie + le capteur diagnostic.
    - Fenêtre = mois passés (`planning_months_behind`) + mois courant + mois futurs
      (`planning_months_ahead`). Vérifié : `month=YYYY-MM` fonctionne aussi pour un mois
      **antérieur** au mois courant (pas de restriction API sur le passé).
    - Mois passés fetchés **une seule fois** puis persistés (`Store`, un fichier par config entry) ;
      seuls le mois courant et les futurs sont refetchés. Fenêtre élargie → les mois manquants sont
      fetchés ; mois sortis de la fenêtre → purgés. **`seen` n'est pas persisté** (voir §4).
    - ⚠️ **Les deux directions n'ont pas le même coût** : un mois passé est fetché une fois puis
      servi du disque, un mois futur est refetché **à chaque refresh**. Le coût par refresh est
      donc `months_ahead + 1`, et `months_behind` n'y entre pas. D'où le plafond bas (3) sur
      `MAX_PLANNING_MONTHS_AHEAD`.
  - **`WatchListCoordinator`** : `GET /episodes/list` (+ `excludes=characters`), **30 min** par
    défaut → le capteur `Shows to catch up on`. Séparé du planning à dessein : le planning est borné
    par sa fenêtre de mois, donc une série dont le dernier épisode non vu est ancien en sortirait ;
    et cet endpoint porte le `remaining` par série et les totaux globaux, que le planning n'a pas.
- **Artwork + note + trailer + genres** : helper partagé `_async_get_show_details()`, un appel
  groupé `GET /shows/display?id=...` pour les séries encore inconnues du cache, par coordinator.
  Retourne 4 dicts (`images, ratings, trailers, genres`), tous indexés par `show_id`, tous
  persistés dans le même cache par-show (`_IMAGES_KEY` sert toujours de marqueur « entrée écrite
  par cette version du cache » - une entrée qui ne l'a pas est retraitée comme manquante,
  ré-fetchée, sans bump de `*_STORE_VERSION`).
  - ⚠️ **L'appel est dans le `try`** des deux coordinators, et le helper **relaie les `AuthError`**
    au lieu de les absorber comme les autres `Error` : `AuthError` héritant d'`Error`, tout absorber
    ferait passer un token rejeté pour un simple souci d'artwork (refresh déclaré réussi, reauth
    jamais demandé).
  - **`trailers`** ✅ : `ShowAdditionalInformation.trailer_url`, déjà une URL HTTPS jouable ou
    `None` - reconstruite **côté client** (`betaseries/client.py`, `_trailer_url()`), pas dans
    `coordinator.py`. L'API renvoie deux champs bruts, `next_trailer` (id vidéo nu) et
    `next_trailer_host` (plateforme) ; seul le host `"youtube"` est confirmé en pratique
    (`bruno/Shows/display.bru`) - tout autre host, ou absence de trailer, donne `None` plutôt
    qu'une URL devinée pour un host jamais vérifié. `ShowAdditionalInformation` n'expose donc
    **jamais** les deux champs bruts séparément.
  - **`genres`** ✅ : `ShowAdditionalInformation.genres` (déjà localisés par l'API), tuple vide si
    absent - aucune transformation, contrairement au trailer.
- Arbitrage #4 : les **trois** intervalles, la fenêtre de mois et les bornes de la watch list sont
  réglables via OptionsFlow (défauts 15/60/30 min, 2/2 mois, 10 séries × 2 épisodes).
- `entity.py` : base entity, `DeviceInfo` unique (« BetaSeries - {login} »),
  `unique_id = f"{member_id}_{key}"` → toutes les entités sous un seul device.
  - ⚠️ Le login vient de **`entry.runtime_data.member.data.identity.login`**, jamais de
    `entry.title` : le titre n'en est que la valeur initiale et l'utilisateur peut le renommer, ce
    qui pointerait le lien « Visiter l'appareil » sur une page inexistante sinon.
- `__init__.py` : `async_setup_entry` construit le client puis les 3 coordinators.
  - Seul **`MemberCoordinator`** utilise `async_config_entry_first_refresh()` : c'est la requête qui
    prouve que les identifiants marchent. Les deux autres font un `async_refresh()` simple, donc une
    panne du planning ou de la watch list dégrade leurs entités en `unavailable` **sans faire tomber
    l'entrée** ni les sensors du compte.
  - `async_remove_entry` supprime les 4 fichiers de cache (`CACHE_STORES` dans `const.py`) : HA ne
    nettoie jamais `.storage` tout seul. **Un cache ajouté sans être listé là survivrait à toute
    entrée qui l'a créé.**
- Réutiliser l'aiohttp de HA via `async_get_clientsession` (pas de requirement externe).

## 7. Structure de fichiers (réelle)

```
custom_components/betaseries/
├── manifest.json
├── __init__.py         # setup/unload/remove entry, PLATFORMS
├── const.py            # options, defauts/bornes, cles + versions de Store
├── betaseries/         # <- client bundlé, un paquet (pas `api.py`), voir son README
├── coordinator.py      # Member + Planning + WatchList, _CacheStore, helper shows/display
├── config_flow.py      # menu device/password + device flow (gabarit Tado) + timeout + reauth + OptionsFlow
├── entity.py           # base entity + DeviceInfo
├── sensor.py           # 21 sensors (table §5)
├── binary_sensor.py    # 2 binary sensors
├── calendar.py         # CalendarEntity
├── button.py           # 3 boutons de purge de cache (diagnostic)
├── diagnostics.py      # export agrégé, credentials redacted
├── services.py         # 14 services : 10 Show/Episode/Season + delete_token + search/add/remove, voir §8
├── services.yaml       # champs des 14 services (gabarit habitica)
├── strings.json        # textes config flow + entités + services (EN)
├── translations/       # en.json + fr.json
└── icons.json          # icônes mdi
```

Repo root : `hacs.json`, `README.md`, `LICENSE`, `tests/`, `bruno/`, `scripts/`,
`.coveragerc-integration`, `requirements-{lint,test-client,test-integration}.txt`,
`.github/workflows/` (hassfest, HACS validate, release, **lint, test** - voir §2).

### manifest.json (réel)

```json
{
  "domain": "betaseries",
  "name": "BetaSeries",
  "version": "0.1.0",
  "codeowners": ["@bastgau"],
  "config_flow": true,
  "documentation": "https://github.com/bastgau/ha-betaseries",
  "integration_type": "service",
  "iot_class": "cloud_polling",
  "requirements": []
}
```

## 8. Services - v3 ✅ (Show/Episode/Season livrés, Movies différé)

Périmètre : Show, Episode et Season uniquement - Movies laissé de côté (pas de `rate_movie`, pas de
dossier `bruno/Movies/`) faute de valeur d'automatisation identifiée pour l'instant ; à
reconsidérer si le besoin se confirme.

Les 10 routes ont toutes été testées via Bruno (`.bru` avec un bloc `example` et une vraie réponse
sauvegardée, gabarit `bruno/Planning/member.bru`) avant d'écrire une seule ligne de client - c'est
ce qui a permis de corriger deux points que le spec OpenAPI seul aurait fait supposer à tort
(voir juste après la table).

| Service (v3)             | Route                      | Paramètres                                                                   | Réponse (succès)                                              |
| ------------------------ | -------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------- |
| `mark_episode_watched`   | `POST /episodes/watched`   | `episode_id` (**plusieurs**, `id=1,2` séparés par des virgules)              | `{"episodes": [...objets complets...], "errors": []}`         |
| `mark_episode_unwatched` | `DELETE /episodes/watched` | `episode_id` (plusieurs acceptés côté requête ; réponse toujours singulière) | `{"episode": {...}, "errors": []}`                            |
| `rate_episode`           | `POST /episodes/note`      | `episode_id` (plusieurs), `note` (1-5)                                       | `{"episode": {...}, "note": N, "errors": []}`                 |
| `unrate_episode`         | `DELETE /episodes/note`    | `episode_id` (plusieurs acceptés ; réponse ne renvoie qu'un seul objet)      | `{"episode": {...}, "errors": []}`                            |
| `mark_season_watched`    | `POST /seasons/watched`    | `show_id`, `season` (un seul show/saison à la fois)                          | `{"episodes": [{"id":...}, ...bruts], "errors": []}`          |
| `mark_season_unwatched`  | `DELETE /seasons/watched`  | `show_id`, `season`                                                          | `{"episodes": [{"id":...}, ...bruts], "errors": []}`          |
| `rate_season`            | `POST /seasons/note`       | `show_id`, `season`, `note` (1-5)                                            | `{"seasons": [toutes les saisons de la série], "errors": []}` |
| `unrate_season`          | `DELETE /seasons/note`     | `show_id`, `season` (pas de champ note)                                      | `{"seasons": [...], "errors": []}`                            |
| `rate_show`              | `POST /shows/note`         | `show_id`, `note` (1-5)                                                      | `{"show": {...complet...}, "note": N, "errors": []}`          |
| `unrate_show`            | `DELETE /shows/note`       | `show_id` (pas de champ note)                                                | `{"show": {...complet...}, "errors": []}`                     |

**Deux corrections apportées par les tests Bruno, par rapport à ce que le spec OpenAPI seul aurait
fait supposer** :

- **Pas de flag `bulk` booléen** : aucune réponse Bruno n'en montre trace, sur aucune route,
  malgré plusieurs essais - "bulk marking" (texte descriptif OpenAPI) décrit la capacité à passer
  plusieurs ids par virgules, pas un paramètre en plus. `mark_episode_watched` n'a donc qu'un champ
  `episode_id` (accepte plusieurs valeurs).
- **`rate_season` est un service à part entière**, pas un paramètre `note` optionnel de
  `mark_season_watched`. Les deux actions restent liées par une règle métier : une saison doit être
  **entièrement vue** avant de pouvoir être notée.

**Règle métier confirmée par un vrai 400** (code `2005`, même texte "L'utilisateur n'a pas marqué
cet épisode comme vu." réutilisé à travers plusieurs routes, y compris en contexte saison) : noter
un épisode/une saison non vu(e), ou démarquer un épisode déjà pas-vu, échoue avec ce code. Détecté
côté client (`betaseries/const.py`, `ERROR_CODE_NOT_WATCHED = 2005`) et surfacé comme
`NotWatchedError` (`betaseries/exceptions.py`), narrowée à son tour en `ServiceValidationError`
côté `services.py` (le seul cas où l'appelant peut corriger son appel - voir/marquer vu d'abord).

Anomalie notée sans lui donner suite : un `DELETE /seasons/watched` répété a une fois renvoyé
`{"code": 3004, "text": "Le paramètre \"season\" est invalide."}` sur un appel par ailleurs
identique à un appel réussi juste avant. Tombe dans le cas générique (`HomeAssistantError`).

Arbitrage #8 ✅ : cible uniquement l'`id` BetaSeries (pas de `thetvdb_id` en alternative) - suffisant
vu que les coordinators exposent déjà cet id pour tout ce qui est actionnable depuis le dashboard
(cf. v2bis, §5). Ciblage du **compte** via un champ `config_entry` (`ConfigEntrySelector`) sur
chaque service - pattern standard HA pour une intégration à un device par entrée, calqué sur
`homeassistant/components/habitica/services.py` (référence déjà citée en §10).

Après un succès de `mark_episode_watched`/`mark_episode_unwatched`/`mark_season_watched`/
`mark_season_unwatched` : refresh de `MemberCoordinator` **et** `WatchListCoordinator`
(`async_request_refresh()`, non bloquant) - les deux seules données affichées que ces actions
changent (`episodes_to_watch`, `shows_to_catch_up_on`/suggestion). **Pas** de refresh après les 6
actions de notation (`rate_*`/`unrate_*`) : aucune entité n'affiche la note d'un membre, seul
`notes.mean` (moyenne globale) sert au tie-break des deux capteurs de date de sortie, caché avec
l'artwork sans mécanisme d'invalidation ciblée par série.

Écarté du périmètre v3 (pas de valeur d'automatisation évidente pour un usage HA, cohérent avec
l'arbitrage #3 de garder le scope serré) : commentaires, tags, collections (premium), sondages,
amis/blocage, favoris, masquer épisode/saison, marquer téléchargé, et tout ce qui touche aux films
(voir plus haut). `add_show` (`POST /shows/show`) et `set_movie_status` (`POST /movies/movie`,
`state`: à voir/vu/pas envie) restent des candidats v4 si le besoin se confirme à l'usage (cas
d'usage fort identifié : ajouter une série à la liste via une phrase Assist, ex.
_« Ajoute Severance à ma liste BetaSeries »_).

### `delete_token` - hors périmètre Show/Episode/Season

Onzième service, à part des dix ci-dessus : il ne cible ni série, ni épisode, ni saison, mais le
compte lui-même. `POST /members/destroy` (vérifié via Bruno, `bruno/Members/token-destroy.bru`) -
détruit le token d'accès actif, sans paramètre. Champ `config_entry` seul (`ConfigEntrySelector`,
même pattern que les dix autres).

**Irréversible** : pas de `create_token` correspondant - obtenir un nouveau token repasse
obligatoirement par le config flow (device code ou login/mot de passe), il n'y a pas de geste API
équivalent. Après un appel réussi, refresh de `MemberCoordinator` uniquement (pas
`WatchListCoordinator`, qui n'a pas d'authentification propre) - ce refresh échoue aussitôt avec le
token qui vient d'être détruit, ce qui déclenche immédiatement le reauth plutôt que d'attendre le
prochain cycle planifié (`AuthError` → `ConfigEntryAuthFailed`, mécanisme déjà en place, voir §3).

### `search_shows` / `add_show` / `remove_show` - catalogue et appartenance au compte ✅

Douzième à quatorzième services, ajoutés pour la recherche de séries depuis la card (voir
`card/README.md`). Ils sortent du périmètre « ce que je suis déjà » de tous les autres : ils
touchent au **catalogue** et à l'appartenance d'une série au compte, pas au visionnage.

| Service        | Route                | Paramètres                         | Réponse                            |
| -------------- | -------------------- | ---------------------------------- | ---------------------------------- |
| `search_shows` | `GET /shows/search`  | `query`, `limit` (1-50, défaut 20) | `{"shows": [...]}` - voir ci-après |
| `add_show`     | `POST /shows/show`   | `show_id`                          | rien (comme les autres écritures)  |
| `remove_show`  | `DELETE /shows/show` | `show_id`                          | rien (même endpoint, verbe opposé) |

- **`search_shows` est le seul service en `SupportsResponse.ONLY`** : il répond au lieu d'agir, et
  une variante sans réponse ne servirait à rien. La réponse est volontairement **neutre** (dicts
  plats : `id, title, year, status, rating, platforms, genres, seasons, followers, in_account,
poster, fanart, summary, resource_url`), pas au format `upcoming-media-card` - le mapping vers
  les items de la card se fait dans la card, seul consommateur qui en a besoin. Aucun refresh de
  coordinator : une recherche ne change rien, et la card l'appelle à chaque frappe débouncée.
- `add_show` et `remove_show` refreshent **member + watch list**, comme `mark_episode_watched` et
  pour la même raison (`shows`, `shows_to_watch` et la liste à rattraper bougent). `add_show` sort
  donc des candidats v4 listés plus haut.
- ✅ **Les trois routes sont vérifiées via Bruno** (`bruno/Shows/search.bru`,
  `bruno/Shows/add-show.bru`, `bruno/Shows/remove-show.bru`, tous avec bloc `example` et réponse
  réelle) - l'OpenAPI n'en documentait aucun schéma de réponse. Ce que ça a confirmé :
  `/shows/search` renvoie bien les **mêmes objets show que `/shows/display`** (`shows` au pluriel,
  avec `creation`, `status`, `notes.mean`, `in_account`, `slug`, `resource_url`,
  `platforms.svods[].name`), donc `_parse_show` est réutilisable tel quel.
- **Deux codes d'erreur métier, propres à `/shows/show`** (HTTP 400, vérifiés dans les deux
  directions) : `2003` « L'utilisateur a déjà cette série dans son compte » et `2004`
  « L'utilisateur n'a pas cette série dans son compte ». Traités comme `ERROR_CODE_NOT_WATCHED`
  (2005) : détectés dans `Client._raise_for_error`, surfacés en `AlreadyInAccountError` /
  `NotInAccountError` (`betaseries/exceptions.py`), narrowés en **`ServiceValidationError`** côté
  `services.py`. C'est le critère déjà retenu pour 2005 - l'appelant peut corriger son appel,
  contrairement à un token rejeté ou une panne serveur.
- ⚠️ **Piège de lecture d'un `.bru`** : `add-show.bru` affiche `POST /shows/show?id=29030` dans sa
  ligne `url:`, ce qui donne à croire que le paramètre passe en query. C'est faux - le bloc
  faisant foi est `body: formUrlEncoded` + `body:form-urlencoded`, et la query de l'`url:` n'est
  que le reflet d'affichage maintenu par Bruno. **Vérifié sur les 37 requêtes de la collection** :
  les 18 GET passent tout en `params:query` (`body: none`), les 17 POST/DELETE tout en
  form-urlencoded, sans une seule exception.
- Quatre champs ont été ajoutés à `ShowAdditionalInformation` pour ça (`creation`,
  `broadcast_status`, `platforms`, `in_account`) - tous déjà présents dans le payload
  `/shows/display`, donc gratuits pour les appelants existants.

## 9. Arbitrages - tous tranchés ✅

1. **Enabled par défaut** : tous les sensors sont `enabled` par défaut (pas de noyau restreint).
2. **Binary `Movies available`** : gardé en v1, `enabled` par défaut (même traitement que `Episodes available`).
3. **Périmètre services** : aucun service en v1/v2 ; les services prévus sont livrés en v3.
4. **Intervalles** : 15 min (member) / 60 min (planning) par défaut, réglables via OptionsFlow.
5. **integration_type** : `service` (retenu).
6. **Périmètre services v3** : livré pour Show/Episode/Season - `mark_episode_watched`/
   `mark_episode_unwatched`, `rate_episode`/`unrate_episode`, `mark_season_watched`/
   `mark_season_unwatched`, `rate_season`/`unrate_season`, `rate_show`/`unrate_show`. Movies
   (`rate_movie`) et `add_show`/`set_movie_status` écartés pour l'instant (candidats v4 selon
   usage, voir §8).
7. **Pas de flag `bulk` distinct** : aucune réponse Bruno n'en montre trace (§8) ; "bulk" décrit la
   capacité à passer plusieurs ids par virgules, pas un paramètre séparé.
8. **Identifiant cible des services** : `id` BetaSeries uniquement, pas de `thetvdb_id` en
   alternative - suffisant vu que les coordinators exposent déjà cet id pour tout ce qui est
   actionnable (v2bis, §5).
9. **Locale (langue des réponses)** : uniquement `fr`/`en` proposés (`SelectSelector`, pas de champ
   texte libre) - les seules langues où le contenu BetaSeries est fiablement localisé. Collectée à
   l'ajout du compte (étape `device_credentials` ou `password_credentials` du config flow selon le
   mode choisi au menu `user`, y compris pendant une reauth - mêmes formulaires partagés) puis
   stockée en **option** (`entry.options`, pas `entry.data`), éditable ensuite via OptionsFlow comme
   les intervalles/fenêtre de mois. Défaut `fr`, alignée sur le défaut de l'API elle-même (voir §3).
10. **Deux méthodes d'authentification, choix explicite de l'utilisateur** : le device
    flow reste la méthode par défaut/recommandée (menu `user`, premier item), mais le mode
    login/mot de passe (`Auth.authenticate_with_password`, voir §3) est offert comme alternative
    plutôt qu'écarté silencieusement - la rotation du `client_secret` n'étant elle-même pas
    self-service, le compromis n'est pas clair-cut. Le menu et le formulaire `password_credentials`
    portent chacun un avertissement (`strings.json`/`translations/{en,fr}.json`) sur le token non
    révoqué, pour que le choix reste informé plutôt qu'implicite.
11. **`data` pour `upcoming-media-card`, opt-in** : intégration tierce avec la card
    Lovelace [`custom-cards/upcoming-media-card`](https://github.com/custom-cards/upcoming-media-card),
    dont le contrat de données a été vérifié dans son propre source (pas sa doc) - nom d'attribut
    `data` figé en dur, élément 0 = objet gabarit (`title_default`/`line1_default`.../`icon`),
    chaque item exige `airdate` ou la card le saute silencieusement. Décisions :
    - **Une option unique** (`upcoming_media_card`, `entry.options`, défaut `False`, section Watch
      list de l'OptionsFlow) active `data` sur les **cinq** sensors concernés à la fois -
      `Shows to catch up on`, `Calendar event count`, `Previous/Next episode airing`,
      `Suggestion of the day`. Pas d'option par sensor : coût de construction/mémoire jugé trop
      faible pour justifier cinq interrupteurs.
    - **Une ligne = une série** (pas un épisode) sur les sensors qui en listent plusieurs -
      grain déjà annoncé par l'état de `Shows to catch up on` (`total_shows`), et qui limite
      l'exposition du biais alphabétique de `/episodes/list` (voir plus haut) à 10 lignes plutôt
      qu'à 20+ épisodes tous en A-D.
    - **`flag`** distingue le sens : `True` constant sur les sensors qui listent du non-vu (watch
      list, suggestion), **absent** sur les sensors qui listent des dates de sortie
      (`Previous/Next episode airing`, `Calendar event count`) - ce dernier groupe n'a d'ailleurs
      plus `seen` disponible pour les mois servis du cache (§4), un `flag` y serait faux la moitié
      du temps.
    - **`studio` détourné** pour porter les plateformes de streaming (`platforms`, triées
      alphabétiquement, jointes par `" / "`) - la card n'a pas de clé dédiée pour ça, et cette
      info existe déjà (`/planning/member`'s `platform_links`).
    - `runtime`, `release`, `price` : jamais mappés, aucune donnée BetaSeries correspondante.

## 10. Références

- Gabarit device flow : `homeassistant/components/tado/config_flow.py`.
- Autres exemples device flow HA : `github`, `google` (api.py séparé), `actron_air`.
- Squelette canonique HACS : repo `integration_blueprint`.
- Patterns Platinum (coordinator, runtime_data, exceptions traduites, entity de base,
  reauth) : `docs/quality-scale-patterns.md`, basé sur `habitica` (Platinum, cloud_polling,
  service - le plus proche conceptuellement de BetaSeries) croisé avec `tado` pour l'auth.

## 11. Reste à faire

### La prochaine grosse étape

- **v3 - services pour les films** : `rate_movie`/`unrate_movie` (et `set_movie_status` en v4
  candidat) restent à faire si le besoin se confirme - voir §8. Même démarche que pour
  Show/Episode/Season : tester via Bruno (créer `bruno/Movies/`) avant d'écrire une ligne de client.
