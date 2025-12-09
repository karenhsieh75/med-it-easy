"""
Skin tone analysis utilities adapted from the standalone face analysis scripts.
Integrates dark circle analysis from eye.py.
"""

from typing import Any, Dict, Iterable, List, Tuple
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

# Palette definition
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
# 注意：為了黑眼圈 index 對齊，保持 refine_landmarks=False
_face_mesh = mp_face_mesh.FaceMesh(static_image_mode=True, refine_landmarks=False, max_num_faces=1)

DARK_CIRCLE_THRESHOLD = 40.0

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
DOCTOR_RULES_PATH = ASSETS_DIR / "doctor.json"

# 嘗試讀取規則檔，若無則使用空字典避免 crash
try:
    with open(DOCTOR_RULES_PATH, "r", encoding="utf-8") as f:
        DOCTOR_RULES = json.load(f)
except FileNotFoundError:
    DOCTOR_RULES = {}

# ========= Dark Circle Helpers (Ported from eye.py) =========

def _landmarks_to_points(landmarks, w, h, idx_list):
    """把指定 index 的 landmark 轉成 (x,y) 像素座標陣列"""
    pts = []
    for idx in idx_list:
        lm = landmarks[idx]
        x = int(lm.x * w)
        y = int(lm.y * h)
        pts.append([x, y])
    return np.array(pts, dtype=np.int32)


def _polygon_pixels(image: np.ndarray, polygon: np.ndarray) -> np.ndarray:
    """Return pixels inside polygon; empty array if no coverage."""
    h, w, _ = image.shape
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask, [polygon], 255)
    return image[mask == 255]


def _normalize_score(x, low, high):
    return float(np.clip((x - low) / (high - low + 1e-6), 0.0, 1.0))


def _landmarks_list(landmarks_obj: Any) -> Iterable:
    """Normalize Mediapipe landmarks input to a list-like structure."""
    if hasattr(landmarks_obj, "landmark"):
        return landmarks_obj.landmark
    return landmarks_obj

def _analyze_dark_circles(img: np.ndarray, landmarks_obj: Any) -> Dict[str, Any]:
    """
    執行黑眼圈分析邏輯，回傳分數與類型。
    """
    h, w, _ = img.shape
    landmarks = _landmarks_list(landmarks_obj)
    
    # 1. Landmark Indices (From eye.py)
    left_eye_bottom_idx = [452, 451, 450, 449, 448]
    right_eye_bottom_idx = [232, 231, 230, 229, 228]
    left_cheek_idx = [187, 147, 123, 205]
    right_cheek_idx = [411, 376, 352, 425]

    # 2. Geometry helpers
    def shift_polygon(points, dy):
        return np.array([[x, y + dy] for (x, y) in points], dtype=np.int32)

    # 3. Collect ROI
    left_eye_poly = _landmarks_to_points(landmarks, w, h, left_eye_bottom_idx)
    right_eye_poly = _landmarks_to_points(landmarks, w, h, right_eye_bottom_idx)

    SHIFT_Y = 0  # 可調整
    left_eye_poly_shifted = shift_polygon(left_eye_poly, SHIFT_Y)
    right_eye_poly_shifted = shift_polygon(right_eye_poly, SHIFT_Y)

    left_eye_pixels = _polygon_pixels(img, left_eye_poly_shifted)
    right_eye_pixels = _polygon_pixels(img, right_eye_poly_shifted)
    
    # Stack pixels safely
    if len(left_eye_pixels) == 0 or len(right_eye_pixels) == 0:
        return {"score": 0.0, "type": "error"}
        
    eye_pixels = np.vstack([left_eye_pixels, right_eye_pixels])

    def get_lab_stats(pixels):
        if len(pixels) == 0:
            return None, None
        rgb = pixels[:, ::-1] / 255.0
        lab = color.rgb2lab(rgb.reshape(1, -1, 3)).reshape(-1, 3)
        return np.mean(lab, axis=0), lab

    mean_eye_lab, eye_lab = get_lab_stats(eye_pixels)
    
    # Collect cheek pixels pure
    lc_pixels_raw = _polygon_pixels(img, _landmarks_to_points(landmarks, w, h, left_cheek_idx))
    rc_pixels_raw = _polygon_pixels(img, _landmarks_to_points(landmarks, w, h, right_cheek_idx))
    cheek_pixels = np.vstack([lc_pixels_raw, rc_pixels_raw])
    mean_cheek_lab, _ = get_lab_stats(cheek_pixels)

    if mean_eye_lab is None or mean_cheek_lab is None:
        return {"score": 0.0, "type": "error"}

    L_eye, a_eye, b_eye = mean_eye_lab
    L_cheek, a_cheek, b_cheek = mean_cheek_lab

    # 4. Feature Calculation
    brightness_drop = L_cheek - L_eye
    da = a_eye - a_cheek
    db = b_eye - b_cheek
    
    eye_L_all = eye_lab[:, 0]
    threshold_L = L_cheek - 8.0
    dark_ratio = float(np.mean(eye_L_all < threshold_L))

    # 5. Score
    brightness_score = _normalize_score(brightness_drop, 2.0, 20.0) * 70.0
    dark_ratio_score = _normalize_score(dark_ratio, 0.1, 0.7) * 30.0
    raw_score = brightness_score + dark_ratio_score
    dark_circle_score = float(np.clip(raw_score, 0.0, 100.0))

    # 6. Type Classification
    type_label = "none"
    advice_key = "none"
    
    if dark_circle_score < 15:
        type_label = "none / mild"
    else:
        if db < -1.5 and da < 0:
            type_label = "vascular (偏青紫)"
            advice_key = "vascular"
        elif db > 2.0:
            type_label = "pigmented (色素型)"
            advice_key = "pigmented"
        elif brightness_drop > 10 and abs(db) < 2.0:
            type_label = "structural / shadow"
            advice_key = "shadow"
        else:
            type_label = "mixed / unclear"
            advice_key = "mixed"

    return {
        "score": dark_circle_score,
        "type_label": type_label,
        "advice_key": advice_key,
        "metrics": {
            "brightness_drop": brightness_drop,
            "da": da,
            "db": db
        }
    }

def _get_dc_advice(advice_key: str) -> Tuple[str, str]:
    """回傳 (Explanation, Advice)；統一使用 vascular 建議。"""
    return (
        "檢測到黑眼圈。",
        "這通常與血液循環不良、過敏性鼻炎或熬夜有關。建議熱敷眼周促進循環，控制過敏症狀，並補充維生素K。"
    )

# ========= Original Skin Tone Logic =========

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
    landmarks_list = _landmarks_list(landmarks)
    skin_pixels = []
    for idx, lm in enumerate(landmarks_list):
        if idx in exclude:
            continue
        x = int(lm.x * w)
        y = int(lm.y * h)
        if 0 <= x < w and 0 <= y < h:
            skin_pixels.append(img[y, x])

    return np.array(skin_pixels)


def _face_roi(img: np.ndarray, landmarks: Any) -> np.ndarray:
    h, w, _ = img.shape
    landmarks_list = _landmarks_list(landmarks)
    xs = [int(lm.x * w) for lm in landmarks_list]
    ys = [int(lm.y * h) for lm in landmarks_list]
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
    Uses Mediapipe for landmarks. Checks for dark circles first;
    if severe, overrides the general skin advice.
    """
    h, w, _ = img.shape
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = _face_mesh.process(rgb_img)

    if not results.multi_face_landmarks:
        return {"status": "error", "message": "No face detected in the image."}

    landmarks = results.multi_face_landmarks[0]
    
    # 1. 基礎膚色分析 (Palette & General Features)
    skin_pixels = _extract_skin_pixels(img, landmarks)
    if skin_pixels.size == 0:
        return {"status": "error", "message": "Face detected, but no valid skin pixels found."}

    weights, best_idx, group_sum = _palette_weights(skin_pixels)
    rose_plot = generate_rose_plot_base64(skin_palette, weights)

    roi = _face_roi(img, landmarks)
    features = extract_skin_features(roi)
    
    # 2. 獲取預設的膚況規則
    matched_rule = _select_rule(features)
    
    # 3. [NEW] 執行黑眼圈分析
    dc_result = _analyze_dark_circles(img, landmarks)
    dc_score = dc_result.get("score", 0.0)
    
    if dc_score > DARK_CIRCLE_THRESHOLD:
        explanation, advice = _get_dc_advice(dc_result["advice_key"])
        # 覆蓋原本的規則結果
        matched_rule = {
            "rule_id": "dark_circle_override",
            "feature": "dark_circle_score",
            "condition": f"> {DARK_CIRCLE_THRESHOLD}",
            "explanation": f"{explanation} ",
            "advice": advice
        }

    return {
        "status": "analysis_complete",
        "result": matched_rule,
        "dark_circle_data": dc_result, # 額外回傳完整黑眼圈數據供前端使用
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
