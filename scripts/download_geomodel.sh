#!/usr/bin/env bash
# Download the pinned BirdNET GeoModel (ONNX + labels) used by trip_prep_geoscore.
#   scripts/download_geomodel.sh
# Weights are Apache-2.0 (docs/licenses/birdnet-geomodel-LICENSE-MODELS.md). They stay out of git.
set -euo pipefail

VERSION="v3.0.4"
BASE="https://github.com/birdnet-team/geomodel/releases/download/${VERSION}"
DEST="$(cd "$(dirname "$0")/.." && pwd)/jizz/geomodel_models/${VERSION}"
mkdir -p "$DEST"

fetch() {  # name sha256
  local name="$1" sha="$2" url="${BASE}/${1//+/%2B}"
  if [[ -f "$DEST/$name" ]] && [[ "$(shasum -a 256 "$DEST/$name" | cut -d' ' -f1)" == "$sha" ]]; then
    echo "ok      $name"; return
  fi
  echo "fetch   $name"
  curl -sSfL -o "$DEST/$name" "$url"
  [[ "$(shasum -a 256 "$DEST/$name" | cut -d' ' -f1)" == "$sha" ]] || { echo "checksum mismatch: $name" >&2; rm -f "$DEST/$name"; exit 1; }
}

fetch "BirdNET+_Geomodel_V3.0.4_Global_14K_FP32.onnx" 0de81d222c23dcb6fa428e958b4dac978783191357e01b7268a103fc6f08e61a
fetch "BirdNET+_Geomodel_V3.0.4_Global_14K_Labels.txt" 8250b457e45d43fc3e77b5cbd06a1d311baf585ab9c51ed8d42e011d98534835
echo "GeoModel ${VERSION} is in $DEST"
