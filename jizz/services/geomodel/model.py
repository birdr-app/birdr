"""Load the GeoModel ONNX file and score places.

Input is ``[lat, lon, week]`` with week 1..48 (four "BirdNET weeks" per month). Output is one
0..1 occurrence score per label (14,082 taxa, birds and others). The scores are a smoothed prior
from GBIF records plus environment, not reporting rates: use them to rank and bucket.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

WEEKS_PER_MONTH = 4
ONNX_NAME = 'BirdNET+_Geomodel_V3.0.4_Global_14K_FP32.onnx'
LABELS_NAME = 'BirdNET+_Geomodel_V3.0.4_Global_14K_Labels.txt'


class GeoModelMissing(RuntimeError):
    pass


def month_scores(week_scores: np.ndarray) -> np.ndarray:
    """``[points, 48, labels]`` -> ``[points, 12, labels]``: the mean of each month's four weeks."""
    n, weeks, labels = week_scores.shape
    return week_scores.reshape(n, weeks // WEEKS_PER_MONTH, WEEKS_PER_MONTH, labels).mean(axis=2)


class GeoModel:
    def __init__(self, directory: str | Path | None = None):
        import onnxruntime as ort

        if directory is None:
            from django.conf import settings

            directory = settings.GEOMODEL_DIR
        self.directory = Path(directory)
        onnx, labels = self.directory / ONNX_NAME, self.directory / LABELS_NAME
        if not onnx.exists() or not labels.exists():
            raise GeoModelMissing(f'GeoModel files not found in {self.directory}; run scripts/download_geomodel.sh')
        self.session = ort.InferenceSession(str(onnx), providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name
        rows = [line.rstrip('\n').split('\t') for line in labels.read_text(encoding='utf-8').splitlines() if line.strip()]
        self.taxon_ids = [r[0] for r in rows]
        self.scientific = [r[1].strip() for r in rows]
        self.common = [r[2].strip() if len(r) > 2 else '' for r in rows]

    @property
    def label_count(self) -> int:
        return len(self.scientific)

    def predict_months(self, points: list[tuple[float, float]]) -> np.ndarray:
        """Monthly scores ``[len(points), 12, labels]`` (float32) for ``(lat, lon)`` points."""
        out = np.zeros((len(points), 12, self.label_count), dtype=np.float32)
        weeks = np.arange(1, 13 * WEEKS_PER_MONTH - WEEKS_PER_MONTH + 1, dtype=np.float32)  # 1..48
        for i, (lat, lon) in enumerate(points):
            batch = np.stack([np.full_like(weeks, lat), np.full_like(weeks, lon), weeks], axis=1)
            probs = self.session.run(None, {self.input_name: batch})[0]
            out[i] = np.clip(month_scores(probs[None])[0], 0.0, 1.0)
        return out

    def species_index(self) -> dict[str, int]:
        """Lowercased scientific name -> label index (birds are matched to ``Species.name_latin``)."""
        return {name.lower(): i for i, name in enumerate(self.scientific)}
