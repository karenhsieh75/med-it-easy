"""
Skin tone analysis utilities adapted from the standalone face analysis scripts.

The functions here can be imported by FastAPI routers or background tasks
without re-initializing heavy computer vision primitives.
"""

from typing import Any, Dict, List, Tuple
import base64
import io
import json
import re
from pathlib import Path

import cv2
import mediapipe as mp
import matplotlib.pyplot as plt
import numpy as np
from skimage import color

# Palette definition is kept generic so it can be swapped or extended later.
skin_palette: List[Tuple[str, Tuple[int, int, int], str]] = [
    ("Porcelain", (255, 226, 220), "cool"),
    ("Fair Pink", (255, 214, 200), "cool"),
    ("Light Ivory", (245, 205, 180), "neutral"),
    ("Warm Sand", (235, 190, 160), "warm"),
    ("Beige", (220, 175, 150), "neutral"),
    ("Soft Tan", (205, 160, 130), "warm"),
    ("Tan", (190, 145, 115), "warm"),
    ("Honey", (175, 130, 105), "warm"),
    ("Caramel", (160, 115, 95), "warm"),
    ("Chestnut", (145, 100, 85), "warm"),
    ("Bronze", (130, 85, 70), "warm"),
    ("Deep", (115, 70, 60), "cool"),
]

palette_rgb = np.array([item[1] for item in skin_palette]) / 255.0
palette_lab = color.rgb2lab(palette_rgb.reshape(1, -1, 3)).reshape(-1, 3)

mp_face_mesh = mp.solutions.face_mesh
_face_mesh = mp_face_mesh.FaceMesh(static_image_mode=True, refine_landmarks=False)

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
DOCTOR_RULES_PATH = ASSETS_DIR / "doctor.json"

with open(DOCTOR_RULES_PATH, "r", encoding="utf-8") as f:
    DOCTOR_RULES = json.load(f)


def extract_skin_features(roi: np.ndarray) -> Dict[str, float]:
    roi = cv2.resize(roi, (200, 200))

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1].mean() / 255
    brightness = hsv[:, :, 2].mean() / 255

    lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
    L = lab[:, :, 0].mean() / 255
    a = (lab[:, :, 1].mean() - 128) / 128
    b = (lab[:, :, 2].mean() - 128) / 128
    contrast = lab[:, :, 0].std() / 255

    r = roi[:, :, 2].mean() / 255
    g = roi[:, :, 1].mean() / 255
    bl = roi[:, :, 0].mean() / 255

    redness = a
    yellow_bias = b
    cyan_bias = -(a + b) / 2

    red_map = (lab[:, :, 1] - 128) / 128
    red_patch_var = float(np.std(red_map))

    deviations = [
        abs(redness),
        abs(yellow_bias),
        abs(cyan_bias),
        abs(saturation - 0.35),
        abs(contrast - 0.22),
        abs(brightness - 0.5),
    ]
    balance_score = float(1.0 - np.mean(deviations))

    return {
        "brightness": float(brightness),
        "L": float(L),
        "redness": float(redness),
        "yellow_bias": float(yellow_bias),
        "cyan_bias": float(cyan_bias),
        "saturation": float(saturation),
        "contrast": float(contrast),
        "r_mean": float(r),
        "g_mean": float(g),
        "b_mean": float(bl),
        "red_patch_var": red_patch_var,
        "balance_score": balance_score,
    }


def _parse_condition(condition: str) -> Tuple[str, float]:
    m = re.match(r"(<=|>=|<|>)\s*([-\d\.]+)", condition.strip())
    if not m:
        raise ValueError(f"Invalid condition format: {condition}")
    op, val = m.group(1), float(m.group(2))
    return op, val


def _eval_condition(value: float, op: str, threshold: float) -> bool:
    # Scale to percentage when the rule threshold looks like a percentage.
    if value <= 1.0 and abs(threshold) > 1.2:
        value = value * 100
    match op:
        case "<":
            return value < threshold
        case ">":
            return value > threshold
        case "<=":
            return value <= threshold
        case ">=":
            return value >= threshold
    return False


def _select_rule(features: Dict[str, float]) -> Dict[str, Any]:
    for rule_id, rule in DOCTOR_RULES.items():
        feat = rule.get("feature")
        if feat not in features:
            continue
        op, threshold = _parse_condition(rule["condition"])
        if _eval_condition(features[feat], op, threshold):
            return {
                "rule_id": rule_id,
                "feature": feat,
                "condition": rule["condition"],
                "explanation": rule.get("explanation", ""),
                "advice": rule.get("advice", ""),
            }
    return {
        "rule_id": "default",
        "feature": "n/a",
        "condition": "n/a",
        "explanation": "目前膚況穩定，維持良好作息與防曬即可。",
        "advice": "持續保持規律睡眠、多喝水，並使用溫和清潔與保濕。",
    }


def _extract_skin_pixels(img: np.ndarray, landmarks: Any) -> np.ndarray:
    h, w, _ = img.shape
    mouth = list(range(61, 89))
    eyes = list(range(33, 133))
    exclude = set(mouth + eyes)

    skin_pixels = []
    for idx, lm in enumerate(landmarks.landmark):
        if idx in exclude:
            continue
        x = int(lm.x * w)
        y = int(lm.y * h)
        if 0 <= x < w and 0 <= y < h:
            skin_pixels.append(img[y, x])

    return np.array(skin_pixels)


def _face_roi(img: np.ndarray, landmarks: Any) -> np.ndarray:
    h, w, _ = img.shape
    xs = [int(lm.x * w) for lm in landmarks.landmark]
    ys = [int(lm.y * h) for lm in landmarks.landmark]
    x1, x2 = max(min(xs), 0), min(max(xs), w - 1)
    y1, y2 = max(min(ys), 0), min(max(ys), h - 1)

    pad_x = int((x2 - x1) * 0.05)
    pad_y = int((y2 - y1) * 0.05)
    x1 = max(x1 - pad_x, 0)
    x2 = min(x2 + pad_x, w - 1)
    y1 = max(y1 - pad_y, 0)
    y2 = min(y2 + pad_y, h - 1)

    if x2 <= x1 or y2 <= y1:
        return img
    return img[y1 : y2 + 1, x1 : x2 + 1]


def _palette_weights(skin_pixels: np.ndarray) -> Tuple[List[float], int, Dict[str, float]]:
    skin_rgb = skin_pixels[:, ::-1] / 255.0  # BGR to RGB
    skin_lab = color.rgb2lab(skin_rgb)
    user_lab = np.mean(skin_lab, axis=0)

    deltas = np.linalg.norm(palette_lab - user_lab, axis=1)
    best_idx = int(np.argmin(deltas))

    eps = 1e-6
    weights = 1 / (deltas + eps)
    weights = weights / weights.sum()

    group_sum = {"warm": 0.0, "cool": 0.0, "neutral": 0.0}
    for (_name, _rgb, group), weight in zip(skin_palette, weights):
        group_sum[group] += float(weight)

    return weights.tolist(), best_idx, group_sum


def analyze_face_color(img: np.ndarray) -> Dict[str, Any]:
    """
    Accepts an OpenCV BGR image and returns a dict with analysis details.
    """
    h, w, _ = img.shape
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = _face_mesh.process(rgb_img)

    if not results.multi_face_landmarks:
        return {"status": "error", "message": "No face detected in the image."}

    landmarks = results.multi_face_landmarks[0]
    skin_pixels = _extract_skin_pixels(img, landmarks)
    if skin_pixels.size == 0:
        return {"status": "error", "message": "Face detected, but no valid skin pixels found."}

    weights, best_idx, group_sum = _palette_weights(skin_pixels)
    rose_plot = generate_rose_plot_base64(skin_palette, weights)

    roi = _face_roi(img, landmarks)
    features = extract_skin_features(roi)
    matched_rule = _select_rule(features)

    return {
        "status": "analysis_complete",
        "result": matched_rule,
        "_analysis_rose_plot_base64": rose_plot,
        "_palette_best_idx": best_idx,
        "_palette_group_sum": group_sum,
    }


def generate_rose_plot_base64(
    palette: List[Tuple[str, Tuple[int, int, int], str]], weights: List[float]
) -> str:
    """Generates a radial bar plot encoded in base64."""
    n = len(palette)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    palette_rgb = np.array([item[1] for item in palette]) / 255.0

    plt.figure(figsize=(6, 6))
    ax = plt.subplot(111, polar=True)
    ax.bar(angles, weights, width=2 * np.pi / n, color=palette_rgb, edgecolor="white")
    ax.set_xticks(angles)
    ax.set_xticklabels([name for (name, _, _) in palette], fontsize=9)
    ax.set_yticklabels([])
    ax.set_title("Skin Tone Rose Diagram", va="bottom")

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close()
    return base64.b64encode(buf.getvalue()).decode("utf-8")


__all__ = [
    "analyze_face_color",
    "generate_rose_plot_base64",
    "skin_palette",
]
