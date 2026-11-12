"""Offline track extraction for solid and dark, low-contrast patterned backgrounds.

Only source pixels are inspected. No filenames, sample coordinates, reference
labels, learned per-screenshot settings or network requests are used here.
"""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image
from pathlib import Path

from experiments.p0 import saliency_mask, validate_model


def background_distance(rgb: np.ndarray) -> np.ndarray:
    border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]))
    quantized = border // 8
    colors, counts = np.unique(quantized, axis=0, return_counts=True)
    chosen = colors[np.argmax(counts)]
    background = np.median(border[np.all(quantized == chosen, axis=1)], axis=0)
    return np.max(np.abs(rgb.astype(np.float32) - background), axis=2)


def track_mask(image: Image.Image, model_path: Path) -> Image.Image:
    # The bundled candidate model remains the fallback for older complex images;
    # keep validating its integrity, as the launcher does, before starting work.
    validate_model(model_path)
    rgb = np.array(image.convert('RGB'))
    if float((background_distance(rgb) > 48).mean()) <= .45:
        return solid_track_mask(image)
    return saliency_mask(image, model_path)


def fill_bounded_holes(mask: np.ndarray, max_area: float) -> np.ndarray:
    result = mask.copy()
    # A diagonal chain of outline pixels is a closed face. The complementary
    # background must use 4-connectivity or it leaks through diagonal corners.
    count, labels, stats, _ = cv2.connectedComponentsWithStats(255 - mask, connectivity=4)
    height, width = mask.shape
    for k in range(1, count):
        x, y, w, h, area = stats[k]
        if area <= max_area and x > 0 and y > 0 and x + w < width and y + h < height:
            result[labels == k] = 255
    return result


def remove_specks(mask: np.ndarray, min_area: float) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    keep = np.zeros(count, np.uint8)
    keep[1:] = np.where(stats[1:, cv2.CC_STAT_AREA] >= min_area, 255, 0)
    return keep[labels]


def close_clipped_faces(mask: np.ndarray) -> np.ndarray:
    """Close short outline gaps on the image boundary, without filling a frame."""
    result = mask.copy()
    for line in (result[0], result[-1], result[:, 0], result[:, -1]):
        points = np.flatnonzero(line)
        for a, b in zip(points[:-1], points[1:]):
            if b - a <= len(line) * .15:
                line[a:b + 1] = 255
    return result


def remove_white_balls(mask: np.ndarray, rgb: np.ndarray) -> np.ndarray:
    """Exclude compact clipped-white ball cores, not long bright tile edges."""
    cores = np.uint8(rgb.min(axis=2) > 235) * 255
    count, _, stats, _ = cv2.connectedComponentsWithStats(cores, 8)
    result = mask.copy()
    for k in range(1, count):
        x, y, w, h, area = stats[k]
        if area < max(50, mask.size * .000075) or not .65 <= w / h <= 1.5 or area / (w * h) < .25:
            continue
        center = (round(x + (w - 1) / 2), round(y + (h - 1) / 2))
        axes = (round(w * .54), round(h * .54))
        cv2.ellipse(result, center, axes, 0, 0, 360, 0, -1)
    return result


def solid_track_mask(image: Image.Image) -> Image.Image:
    rgb = np.array(image.convert('RGB'))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    height, width = gray.shape
    if min(height, width) < 8:
        raise ValueError('图片尺寸太小，无法识别轨道')
    # The most frequent quantized border color rejects occasional clipped track
    # ends and remains useful when the background contains faint repeating marks.
    distance = background_distance(rgb)
    visible = distance > 48
    saturated = visible & (hsv[:, :, 1] > 40)
    histogram = np.bincount(hsv[:, :, 0][saturated], minlength=180)
    # A filled colored path has a concentrated material color. Multicolor neon
    # outlines have a broad hue distribution and require enclosed-face recovery.
    window = np.array([sum(histogram[(np.arange(h-17, h+18) % 180)]) for h in range(180)])
    hue = int(window.argmax())
    hue_distance = np.minimum(np.abs(hsv[:, :, 0].astype(int) - hue), 180 - np.abs(hsv[:, :, 0].astype(int) - hue))
    material = saturated & (hue_distance <= 17)
    filled = int(material.sum()) > max(100, int(visible.sum()) * .4)
    kernel = np.ones((3, 3), np.uint8)
    if filled:
        mask = np.uint8(material) * 255
        # Bright clipped tile faces may have almost no saturation. Preserve their
        # sharp core while discarding most of the low-frequency surrounding glow.
        white = np.uint8((rgb.min(axis=2) >= 175) & visible) * 255
        mask = cv2.bitwise_or(mask, white)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = fill_bounded_holes(mask, min(1000, width * height * .002))
    else:
        neutral = saturated.sum() < visible.sum() * .3
        if neutral:
            # Gray outlines sit above the dark background texture; white lettering
            # is excluded separately rather than growing it into track geometry.
            mask = np.uint8((distance > 29) & (hsv[:, :, 2] <= 210)) * 255
        else:
            mask = np.uint8(saturated & (hsv[:, :, 2] > 60)) * 255
            mask = cv2.bitwise_or(mask, np.uint8(rgb.min(axis=2) > 180) * 255)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel if neutral else np.ones((5, 5), np.uint8))
        mask = close_clipped_faces(mask)
        mask = fill_bounded_holes(mask, width * height * (.0033 if neutral else .015))
        if neutral:
            mask[np.all(rgb > 215, axis=2)] = 0
    mask = remove_white_balls(mask, rgb)
    mask = remove_specks(mask, max(40, width * height * .00008))
    mask[np.asarray(image.convert('RGBA'))[:, :, 3] == 0] = 0
    return Image.fromarray(mask)
