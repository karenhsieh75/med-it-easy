"""
Skin tone analysis utilities adapted from the standalone face analysis scripts.

The functions here can be imported by FastAPI routers or background tasks
without re-initializing heavy computer vision primitives.
"""

from typing import Any, Dict, List, Tuple
import base64
import io

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

    # Exclude eyes and mouth landmarks to avoid makeup/feature bias.
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

    if not skin_pixels:
        return {"status": "error", "message": "Face detected, but no valid skin pixels found."}

    skin_pixels = np.array(skin_pixels)
    skin_rgb = skin_pixels[:, ::-1] / 255.0  # BGR to RGB
    skin_lab = color.rgb2lab(skin_rgb)
    user_lab = np.mean(skin_lab, axis=0)

    deltas = np.linalg.norm(palette_lab - user_lab, axis=1)
    best_idx = int(np.argmin(deltas))
    best_name = skin_palette[best_idx][0]

    eps = 1e-6
    weights = 1 / (deltas + eps)
    weights = weights / weights.sum()

    group_sum = {"warm": 0.0, "cool": 0.0, "neutral": 0.0}
    composition_details = []
    for (name, rgb, group), weight in zip(skin_palette, weights):
        group_sum[group] += float(weight)
        composition_details.append(
            {
                "name": name,
                "percentage": float(weight * 100),
                "group": group,
            }
        )

    return {
        "status": "analysis_complete",
        "best_match": best_name,
        "warm_cool_neutral_base": {k: float(v * 100) for k, v in group_sum.items()},
        "detailed_composition": composition_details,
        # Raw fields are kept for optional visualization downstream.
        "_raw_weights": weights.tolist(),
        "_raw_group_sum": {k: float(v) for k, v in group_sum.items()},
        "_raw_best_idx": best_idx,
    }


def generate_plot_base64(
    skin_palette_data: List[Tuple[str, Tuple[int, int, int], str]],
    weights: List[float],
    group_sum: Dict[str, float],
    best_idx: int,
) -> str:
    """Builds a composite plot and returns a base64-encoded PNG."""
    n = len(skin_palette_data)
    theta = 360 / n

    fig = plt.figure(figsize=(15, 6))

    ax1 = fig.add_subplot(1, 3, 1, aspect="equal")
    for i, (name, rgb, group) in enumerate(skin_palette_data):
        start = i * theta
        wedge = plt.matplotlib.patches.Wedge(
            (0, 0), 1, start, start + theta, facecolor=np.array(rgb) / 255, edgecolor="white"
        )
        ax1.add_patch(wedge)
    angle_rad = np.deg2rad(best_idx * theta + theta / 2)
    arrow = plt.matplotlib.patches.FancyArrowPatch(
        posA=(1.3 * np.cos(angle_rad), 1.3 * np.sin(angle_rad)),
        posB=(1.05 * np.cos(angle_rad), 1.05 * np.sin(angle_rad)),
        arrowstyle="-|>",
        mutation_scale=18,
        color="black",
        linewidth=2,
    )
    ax1.add_patch(arrow)
    ax1.set_xlim(-1.5, 1.5)
    ax1.set_ylim(-1.5, 1.5)
    ax1.set_title("Skin Tone Wheel\n(Arrow = Your Tone)", fontsize=13)
    ax1.axis("off")

    ax2 = fig.add_subplot(1, 3, 2)
    ax2.axis("off")
    text = "Skin Tone Composition (12 colors)\n\n"
    for (name, _rgb, _group), weight in zip(skin_palette_data, weights):
        text += f"{name:12s}: {weight * 100:5.2f}%\n"
    text += "\nWarm/Cool/Neutral Base:\n"
    text += f"Warm:   {group_sum['warm'] * 100:5.2f}%\n"
    text += f"Cool:   {group_sum['cool'] * 100:5.2f}%\n"
    text += f"Neutral:{group_sum['neutral'] * 100:5.2f}%\n"
    ax2.text(0, 0.5, text, fontsize=12, family="monospace", va="center")

    ax3 = fig.add_subplot(1, 3, 3)
    colors = [rgb for (_, rgb, _) in skin_palette_data]
    ax3.barh([item[0] for item in skin_palette_data], weights, color=np.array(colors) / 255.0)
    ax3.set_title("Skin Tone Composition Bar Chart")
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)

    return base64.b64encode(buf.getvalue()).decode("utf-8")


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
    "generate_plot_base64",
    "generate_rose_plot_base64",
    "skin_palette",
]
