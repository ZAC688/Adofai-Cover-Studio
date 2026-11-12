"""Additional P0 structure candidate. Not a validated detector.

Select bounded, tile-sized dark faces and structurally complex warm-colored
paths. There are no image names, screen coordinates, or reference-mask inputs.
"""
import cv2
import numpy as np
from PIL import Image


def tile_regions_mask(image: Image.Image) -> Image.Image:
    rgb = np.asarray(image.convert("RGB"))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    value = hsv[:, :, 2]
    edge_source = cv2.GaussianBlur(value, (3, 3), 0)
    edges = cv2.Canny(edge_source, 45, 110)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    result = np.zeros_like(gray)
    for contour in contours:
        area = cv2.contourArea(contour)
        if not max(40, gray.size * .000025) <= area <= gray.size * .025:
            continue
        (_, _), (width, height), _ = cv2.minAreaRect(contour)
        small, large = sorted((width, height))
        if small < 6 or large / small > 7 or area / max(width * height, 1) < .45:
            continue
        perimeter = cv2.arcLength(contour, True)
        corners = cv2.approxPolyDP(contour, .018 * perimeter, True)
        if not 3 <= len(corners) <= 14:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        local = np.zeros((h, w), np.uint8)
        shifted = contour - np.array([[[x, y]]])
        boundary = np.zeros_like(local)
        cv2.drawContours(boundary, [shifted], -1, 255, 3)
        boundary_values = value[y:y+h, x:x+w][boundary > 0]
        boundary_hsv = hsv[y:y+h, x:x+w][boundary > 0]
        if not len(boundary_values) or np.percentile(boundary_values, 90) < 120:
            continue
        warm_fraction = ((boundary_hsv[:, 0] >= 12) & (boundary_hsv[:, 0] <= 45)
                         & (boundary_hsv[:, 1] >= 30)).mean()
        # A dark hole bordered by a warm path is background, not a dark tile face.
        if warm_fraction > .4:
            continue
        cv2.drawContours(local, [shifted], -1, 255, cv2.FILLED)
        local = cv2.erode(local, np.ones((3, 3), np.uint8))
        interior = gray[y:y+h, x:x+w][local > 0]
        if len(interior) < 12 or float(np.median(interior)) > 70:
            continue
        cv2.drawContours(result, [contour], -1, 255, cv2.FILLED)
    warm = cv2.inRange(hsv, np.array([12, 30, 65]), np.array([45, 255, 255]))
    warm = cv2.morphologyEx(warm, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    warm_contours, _ = cv2.findContours(warm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in warm_contours:
        area = cv2.contourArea(contour)
        if not gray.size * .002 <= area <= gray.size * .25:
            continue
        perimeter = cv2.arcLength(contour, True)
        corners = cv2.approxPolyDP(contour, .0015 * perimeter, True)
        hull_area = max(cv2.contourArea(cv2.convexHull(contour)), 1)
        if len(corners) >= 12 and area / hull_area < .75:
            cv2.drawContours(result, [contour], -1, 255, cv2.FILLED)
    return Image.fromarray(result)
