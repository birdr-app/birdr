from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional, Tuple

import numpy as np
from django.conf import settings

logger = logging.getLogger(__name__)

Backend = Literal['opencv', 'onnxruntime', 'none']


@dataclass(frozen=True)
class YoloBirdResult:
    bird_max_conf: float
    bird_num_boxes: int
    bird_max_area_ratio: float


def _letterbox(img_bgr: np.ndarray, new_size: int = 640) -> Tuple[np.ndarray, float, int, int]:
    """Resize+pad to square like YOLOv5 export expects. Returns (padded, scale, pad_x, pad_y)."""
    import cv2  # type: ignore

    h, w = img_bgr.shape[:2]
    scale = min(float(new_size) / max(h, 1), float(new_size) / max(w, 1))
    nh, nw = int(round(h * scale)), int(round(w * scale))
    resized = img_bgr
    if (nw, nh) != (w, h):
        resized = cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
    pad_x = (new_size - nw) // 2
    pad_y = (new_size - nh) // 2
    padded = cv2.copyMakeBorder(
        resized,
        pad_y,
        new_size - nh - pad_y,
        pad_x,
        new_size - nw - pad_x,
        borderType=cv2.BORDER_CONSTANT,
        value=(114, 114, 114),
    )
    return padded, scale, pad_x, pad_y


def _resolve_onnx_path() -> Optional[Path]:
    path = (getattr(settings, 'MEDIA_YOLO_ONNX_PATH', '') or '').strip()
    if not path:
        return None
    p = Path(path)
    return p if p.is_file() else None


def _nms_xyxy_cv2(
    boxes_xyxy: np.ndarray,
    scores: np.ndarray,
    *,
    conf_thr: float,
    iou_thr: float,
) -> Tuple[np.ndarray, np.ndarray]:
    import cv2  # type: ignore

    b = boxes_xyxy.astype(np.float32)
    # OpenCV expects [x, y, width, height], not xyxy coordinates.
    boxes_xywh = b.copy()
    boxes_xywh[:, 2] = b[:, 2] - b[:, 0]
    boxes_xywh[:, 3] = b[:, 3] - b[:, 1]
    idxs = cv2.dnn.NMSBoxes(
        boxes_xywh.tolist(),
        scores.astype(float).tolist(),
        score_threshold=conf_thr,
        nms_threshold=iou_thr,
    )
    if idxs is None or len(idxs) == 0:
        return b[:0], scores[:0]
    idxs = np.array(idxs).reshape(-1).astype(int)
    return b[idxs], scores[idxs]


def _postprocess_yolov5_style(
    det: np.ndarray,
    *,
    conf_thr: float,
    iou_thr: float,
    bird_id: int,
    rgb_u8: np.ndarray,
    scale: float,
    pad_x: int,
    pad_y: int,
) -> YoloBirdResult:
    import cv2  # type: ignore

    if det.ndim == 3:
        det = det[0]
    if det.ndim != 2 or det.shape[1] < 6:
        return YoloBirdResult(bird_max_conf=0.0, bird_num_boxes=0, bird_max_area_ratio=0.0)

    obj = det[:, 4]
    cls = det[:, 5:]
    if bird_id < 0 or bird_id >= cls.shape[1]:
        return YoloBirdResult(bird_max_conf=0.0, bird_num_boxes=0, bird_max_area_ratio=0.0)

    conf = obj * cls[:, bird_id]
    keep = conf >= conf_thr
    if not np.any(keep):
        return YoloBirdResult(
            bird_max_conf=float(np.max(conf) if conf.size else 0.0),
            bird_num_boxes=0,
            bird_max_area_ratio=0.0,
        )

    boxes = det[keep, :4].copy()
    scores = conf[keep].copy()

    x, y, w, h = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    x1 = x - w / 2.0
    y1 = y - h / 2.0
    x2 = x + w / 2.0
    y2 = y + h / 2.0
    b = np.stack([x1, y1, x2, y2], axis=1).astype(np.float32)

    b, scores = _nms_xyxy_cv2(b, scores, conf_thr=conf_thr, iou_thr=iou_thr)
    if scores.size == 0:
        return YoloBirdResult(
            bird_max_conf=float(np.max(conf) if conf.size else 0.0),
            bird_num_boxes=0,
            bird_max_area_ratio=0.0,
        )

    H, W = rgb_u8.shape[:2]
    b[:, [0, 2]] = (b[:, [0, 2]] - pad_x) / max(scale, 1e-9)
    b[:, [1, 3]] = (b[:, [1, 3]] - pad_y) / max(scale, 1e-9)
    b[:, 0] = np.clip(b[:, 0], 0, W)
    b[:, 2] = np.clip(b[:, 2], 0, W)
    b[:, 1] = np.clip(b[:, 1], 0, H)
    b[:, 3] = np.clip(b[:, 3], 0, H)

    areas = np.maximum(0.0, b[:, 2] - b[:, 0]) * np.maximum(0.0, b[:, 3] - b[:, 1])
    img_area = float(max(H * W, 1))
    area_ratio = float(np.max(areas) / img_area) if areas.size else 0.0
    return YoloBirdResult(
        bird_max_conf=float(np.max(scores) if scores.size else 0.0),
        bird_num_boxes=int(scores.size),
        bird_max_area_ratio=area_ratio,
    )


class _YoloRunner:
    def __init__(self) -> None:
        self._path: Optional[Path] = None
        self._backend: Backend = 'none'
        self._cv_net: Optional[object] = None
        self._ort_session: Optional[object] = None

    def configure(self) -> None:
        p = _resolve_onnx_path()
        if p is None:
            self._path = None
            self._backend = 'none'
            self._cv_net = None
            self._ort_session = None
            return
        if self._path == p and self._backend != 'none':
            return
        self._path = p
        self._cv_net = None
        self._ort_session = None
        self._backend = 'none'

        prefer_ort = bool(getattr(settings, 'MEDIA_YOLO_PREFER_ONNXRUNTIME', False))

        if prefer_ort:
            if self._try_onnxruntime():
                self._backend = 'onnxruntime'
                return
            if self._try_opencv():
                self._backend = 'opencv'
                return
        else:
            if self._try_opencv():
                self._backend = 'opencv'
                return
            if self._try_onnxruntime():
                self._backend = 'onnxruntime'
                return

        self._backend = 'none'

    def _try_opencv(self) -> bool:
        if self._path is None:
            return False
        try:
            import cv2  # type: ignore

            net = cv2.dnn.readNetFromONNX(str(self._path))
            # Smoke test forward with dummy input to catch import-time OK but forward-time failures.
            blob = np.zeros((1, 3, 640, 640), dtype=np.float32)
            net.setInput(blob)
            _ = net.forward()
            self._cv_net = net
            return True
        except Exception as exc:
            logger.warning('OpenCV DNN could not run YOLO ONNX (%s): %s', self._path, exc)
            self._cv_net = None
            return False

    def _try_onnxruntime(self) -> bool:
        if self._path is None:
            return False
        try:
            import onnxruntime as ort  # type: ignore

            sess = ort.InferenceSession(str(self._path), providers=['CPUExecutionProvider'])
            inp = sess.get_inputs()[0]
            dummy = np.zeros(tuple(inp.shape), dtype=np.float32)
            sess.run(None, {inp.name: dummy})
            self._ort_session = sess
            return True
        except Exception as exc:
            logger.warning('onnxruntime could not run YOLO ONNX (%s): %s', self._path, exc)
            self._ort_session = None
            return False

    def run(self, rgb_u8: np.ndarray) -> YoloBirdResult:
        self.configure()
        if self._path is None:
            return YoloBirdResult(bird_max_conf=0.0, bird_num_boxes=0, bird_max_area_ratio=0.0)
        if self._backend == 'none':
            raise RuntimeError(f'Could not load configured YOLO model: {self._path}')

        import cv2  # type: ignore

        img_bgr = rgb_u8[:, :, ::-1]
        inp, scale, pad_x, pad_y = _letterbox(img_bgr, new_size=640)
        conf_thr = float(getattr(settings, 'MEDIA_YOLO_CONF_THRESHOLD', 0.25))
        iou_thr = float(getattr(settings, 'MEDIA_YOLO_NMS_IOU_THRESHOLD', 0.45))
        bird_id = int(getattr(settings, 'MEDIA_YOLO_BIRD_CLASS_ID', 14))

        if self._backend == 'opencv' and self._cv_net is not None:
            try:
                blob = cv2.dnn.blobFromImage(inp, scalefactor=1.0 / 255.0, size=(640, 640), swapRB=False, crop=False)
                self._cv_net.setInput(blob)
                out = self._cv_net.forward()
                return _postprocess_yolov5_style(
                    np.asarray(out),
                    conf_thr=conf_thr,
                    iou_thr=iou_thr,
                    bird_id=bird_id,
                    rgb_u8=rgb_u8,
                    scale=scale,
                    pad_x=pad_x,
                    pad_y=pad_y,
                )
            except Exception as exc:
                logger.warning('OpenCV YOLO forward failed; trying onnxruntime fallback: %s', exc)
                self._cv_net = None
                if self._try_onnxruntime():
                    self._backend = 'onnxruntime'
                    return self.run(rgb_u8)
                self._backend = 'none'
                return YoloBirdResult(bird_max_conf=0.0, bird_num_boxes=0, bird_max_area_ratio=0.0)

        if self._backend == 'onnxruntime' and self._ort_session is not None:
            sess = self._ort_session
            inp_meta = sess.get_inputs()[0]
            name = inp_meta.name
            blob = cv2.dnn.blobFromImage(inp, scalefactor=1.0 / 255.0, size=(640, 640), swapRB=False, crop=False)
            out = sess.run(None, {name: blob})[0]
            return _postprocess_yolov5_style(
                np.asarray(out),
                conf_thr=conf_thr,
                iou_thr=iou_thr,
                bird_id=bird_id,
                rgb_u8=rgb_u8,
                scale=scale,
                pad_x=pad_x,
                pad_y=pad_y,
            )

        return YoloBirdResult(bird_max_conf=0.0, bird_num_boxes=0, bird_max_area_ratio=0.0)


_RUNNER = _YoloRunner()


def yolo_bird_features(rgb_u8: np.ndarray) -> YoloBirdResult:
    """
    Run an ONNX YOLO model and return bird box summary features.

    Tries OpenCV DNN first; falls back to onnxruntime if OpenCV cannot parse/execute the graph.
    If no model is configured/available, returns zeros (keeps vector stable).
    """
    return _RUNNER.run(rgb_u8)
