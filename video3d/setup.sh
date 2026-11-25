#!/usr/bin/env bash
# Réinstalle tout ce qu'il faut pour rendre le personnage : Blender (module Python), les données MakeHuman
# et les packs d'éléments 3D (CC0). À lancer depuis le dossier video3d/ :  bash setup.sh
# Sites nécessaires : pypi.org, raw.githubusercontent.com, files.makehumancommunity.org
set -euo pipefail
cd "$(dirname "$0")"

# 1. Blender en module Python (rendu Cycles sur processeur)
[ -x blender-venv/bin/python ] || python3 -m venv blender-venv
./blender-venv/bin/python -c "import bpy" 2>/dev/null || ./blender-venv/bin/pip install -q bpy

# 2. Paquet MakeHuman (contient les 1281 morphologies : data/targets.npz)
if [ ! -f mh-pkg/makehuman/data/targets.npz ]; then
  mkdir -p dl mh-pkg
  pip download --no-deps -q -d dl makehuman==1.3.2
  python3 -I -m zipfile -e dl/makehuman-1.3.2-py3-none-any.whl mh-pkg
fi

# 3. Maillage de base, squelette et yeux (dépôt public MakeHuman)
B=https://raw.githubusercontent.com/makehumancommunity/makehuman/master/makehuman/data
mkdir -p mh-data/rigs mh-data/eyes/high-poly mh-data/modifiers
[ -s mh-data/base.obj ] || curl -fsS -o mh-data/base.obj "$B/3dobjs/base.obj"
for f in rigs/default.mhskel rigs/default_weights.mhw eyes/high-poly/high-poly.obj eyes/high-poly/high-poly.mhclo modifiers/modeling_modifiers.json; do
  [ -s "mh-data/$f" ] || curl -fsS -o "mh-data/$f" "$B/$f"
done

# 4. Packs d'éléments officiels (tous libres de droits, CC0)
F=https://files.makehumancommunity.org
unpack() {  # unpack <zip> <dossier> : refuse les chemins absolus ou remontants
  python3 -I - "$1" "$2" <<'PY'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
bad = [n for n in z.namelist() if n.startswith('/') or '..' in n.split('/')]
assert not bad, bad
z.extractall(sys.argv[2])
PY
}
mkdir -p dl mh-assets mh-extra
if [ ! -d mh-assets/skins ]; then
  curl -fsS -C - -o dl/makehuman_system_assets_cc0.zip "$F/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip"
  unpack dl/makehuman_system_assets_cc0.zip mh-assets
fi
for p in asset_packs/poses01/poses01_cc0.zip asset_packs/gloves01/gloves01_cc0.zip asset_packs/hair01/hair01_cc0.zip \
         functional/visemes01.zip functional/visemes02.zip functional/faceunits01.zip; do
  z=$(basename "$p"); d=${z%.zip}; d=${d%_cc0}
  if [ ! -d "mh-extra/$d" ]; then
    curl -fsS -C - -o "dl/$z" "$F/$p"
    mkdir -p "mh-extra/$d"
    unpack "dl/$z" "mh-extra/$d"
  fi
done
mkdir -p cache
echo "Prêt. Exemple : cd hero && ../blender-venv/bin/python diag.py out room_close room_medium"
