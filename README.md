# maasto

> *Maasto* (finnois) : le terrain.

Vérification rapide des conditions neige/rando pour un point GPS donné. Génère un rapport HTML autonome qui croise météo, image satellite, sorties communautaires (Camptocamp) et bulletin avalanche. Le signal terrain (sorties Camptocamp récentes) sert de garde-fou quand le modèle météo se plante — d'où le nom.

## Installation

```sh
cd ~/Dev/Alpi/maasto
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage CLI

```sh
# Coords décimales
python -m maasto 45.165,6.170

# Coords DMS
python -m maasto "45°09'54\"N 6°10'12\"E"

# Avec altitude forcée et fenêtre temporelle custom
python -m maasto 45.165,6.170 --altitude 2800 --days 21
```

Le résultat va dans `results/<slug>_<date>/report.html` — ouvre dans ton navigateur.

## Sources

| Source | Données | Notes |
|---|---|---|
| Open-Meteo | Météo / hauteur de neige | Gratuit en usage non commercial ; offre payante pour un usage commercial |
| Open-Elevation, Nominatim (OSM) | Altitude, géocodage | Gratuit, public — respecter les limites de débit |
| Camptocamp | Sorties récentes | API publique, gratuite |
| SLF, Météo-France | Bulletins avalanche | Données publiques |
| Sentinel-2 (Earth Search / AWS) | Image satellite | Catalogue gratuit ; l'accès aux images via AWS peut générer des frais |

La licence MIT couvre **ce code uniquement**. Chaque API tierce a ses propres conditions d'usage — à vérifier avant tout usage intensif ou commercial, et apporte tes propres accès si nécessaire.
