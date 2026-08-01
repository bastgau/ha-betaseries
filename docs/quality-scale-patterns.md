# Patterns Platinum - référence pour l'implémentation BetaSeries

> Extraits vérifiés du code source Home Assistant 2026.7.0 installé localement
> (`homeassistant/components/`). Objectif : appliquer ces patterns dès la v1
> plutôt que de refactorer plus tard pour monter en quality scale.

## Méthode de recherche (reproductible)

Chaque intégration core a un `quality_scale.yaml` listant des règles par rang
(Bronze/Silver/Gold/Platinum) avec un statut `done`/`todo`/`exempt`. Aucune
intégration cloud_polling à auth par device flow n'est Platinum à ce jour ;
les deux références retenues couvrent chacune une moitié du problème :

- **`tado`** (déjà retenu au §3 du CLAUDE.md) - gabarit du **device flow**
  (`config_flow.py` : `async_show_progress`, polling, reauth).
- **`habitica`** (Platinum, `integration_type: service`, `iot_class:
cloud_polling`) - le plus proche conceptuellement de BetaSeries : compte
  utilisateur cloud avec stats, coordinator, sensor/binary_sensor/calendar/
  services. Toutes les règles Platinum (`async-dependency`, `strict-typing`,
  `inject-websession`) + Gold + Silver + Bronze sont `done` ou `exempt`.

Pour identifier des candidats similaires à l'avenir : scanner tous les
`*/quality_scale.yaml` du paquet `homeassistant` installé, ne garder que ceux
dont les 3 règles Platinum sont `done`/`exempt`, puis croiser avec
`manifest.json` (`iot_class`, présence de `coordinator.py`).

## Patterns à appliquer

### 1. `runtime_data` typé (pas de `hass.data[DOMAIN][entry_id]`)

```python
# coordinator.py
type BetaSeriesConfigEntry = ConfigEntry[BetaSeriesCoordinator]

# __init__.py
async def async_setup_entry(hass: HomeAssistant, entry: BetaSeriesConfigEntry) -> bool:
    coordinator = BetaSeriesCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
```

Source : `habitica/coordinator.py:58`, `habitica/__init__.py:69-72`.

### 2. Exceptions traduites, jamais d'`Exception` brute

Toujours lever `ConfigEntryAuthFailed` / `ConfigEntryNotReady` / `UpdateFailed`
/ `HomeAssistantError` avec `translation_domain=DOMAIN` + `translation_key` +
`translation_placeholders` (clés définies dans `strings.json`).

```python
except NotAuthorizedError as e:
    raise ConfigEntryAuthFailed(
        translation_domain=DOMAIN,
        translation_key="authentication_failed",
    ) from e
except TooManyRequestsError as e:
    raise ConfigEntryNotReady(
        translation_domain=DOMAIN,
        translation_key="setup_rate_limit_exception",
        translation_placeholders={"retry_after": str(e.retry_after)},
    ) from e
```

Source : `habitica/coordinator.py:129-151`.

### 3. Coordinator : séparer `_async_setup` (auth/init) et `_async_update_data` (polling)

- `_async_setup` : appelé une seule fois avant le premier refresh. Teste l'auth,
  lève `ConfigEntryAuthFailed`/`ConfigEntryNotReady` si ça échoue.
- `_async_update_data` : appelé à chaque polling. Lève `UpdateFailed` en cas
  d'erreur transitoire (ne casse pas l'entry, juste l'update courant).

Directement transposable à `MemberCoordinator` (setup = premier appel
`/members/infos`, teste le token) et `PlanningCoordinator`.
Source : `habitica/coordinator.py:120-163`.

### 4. Entity de base : `has_entity_name` + `DeviceInfo(entry_type=SERVICE)`

```python
class BetaSeriesEntity(CoordinatorEntity[BetaSeriesCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entity_description) -> None:
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="BetaSeries",
            name=member_login,
            identifiers={(DOMAIN, unique_id)},
        )
```

Cohérent avec le §6 du CLAUDE.md (device unique « BetaSeries - {login} »).
Source : `habitica/entity.py:23-57`.

### 5. `PARALLEL_UPDATES = 1` dans chaque module de plateforme

À ajouter en haut de `sensor.py`, `binary_sensor.py`, `calendar.py` (Silver
`parallel-updates` - limite les appels concurrents au coordinator/API).
Source : `habitica/sensor.py:49`.

### 6. Session HTTP injectée, jamais créée par l'intégration

`async_get_clientsession(hass, ...)` - jamais de `aiohttp.ClientSession()`
manuel (Platinum `inject-websession`). Déjà noté au §6 du CLAUDE.md, confirmé
par `habitica/config_flow.py:339` et `habitica/__init__.py:57`.

### 7. Config flow : `async_set_unique_id` + `_abort_if_unique_id_configured`

Avant `async_create_entry`, toujours fixer l'unique_id (ici `member.id`) et
avorter si déjà configuré - évite les doublons d'entry pour le même compte.
Source : `habitica/config_flow.py:171-172, 204-205`.

### 8. Reauth flow minimal

`async_step_reauth` → `async_step_reauth_confirm`, avec
`async_set_unique_id` + `_abort_if_unique_id_mismatch` puis
`async_update_and_abort(reauth_entry, data_updates={...})`. Pertinent pour
BetaSeries si le token s'avère expirant (🟡 au §3 du CLAUDE.md) - le gabarit
Tado couvre déjà ce cas, à recouper avec ce pattern.
Source : `habitica/config_flow.py:236-267`.

## Non retenu

- `habitica` utilise API key + login/password, pas un device flow - ne pas
  copier son `config_flow.py` pour l'étape d'auth elle-même, seulement pour
  les patterns de structure (reauth, reconfigure, unique_id).
- Pas de `ConfigSubentry` prévu pour BetaSeries (habitica l'utilise pour les
  membres de guilde/party - hors périmètre v1/v2/v3).
