"""Color-assisted reference drafts for human review, independent of production.

The per-image selections and cleanup below are an annotation recipe, NOT a
recognizer. Never import these settings into the application or use these masks
as approved truth until the user has reviewed the original/overlay/cutout sheets.
"""
from pathlib import Path
import hashlib
import json

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]

# Independently traced outline of the scan-line theme. White balls occlude two
# portions of this geometry; the ellipses below exclude those visible balls.
SCAN_OUTLINE = [(84,0),(495,0),(548,29),(556,43),(553,59),(543,67),(449,67),
    (443,78),(432,101),(435,135),(446,147),(457,171),(483,186),(538,220),
    (545,233),(543,248),(532,258),(437,261),(425,275),(417,285),(413,323),
    (430,342),(437,361),(476,383),(532,418),(537,432),(534,447),(523,455),
    (428,459),(416,477),(407,493),(405,524),(426,544),(433,565),(469,585),
    (517,614),(524,628),(521,644),(511,650),(393,650),(386,615),(377,590),
    (363,576),(347,543),(339,522),(341,496),(353,469),(368,450),(386,421),
    (399,404),(398,390),(387,372),(373,349),(358,326),(352,302),(358,283),
    (371,257),(391,232),(402,208),(410,195),(401,178),(386,151),(376,122),
    (377,103),(388,78),(400,54),(414,29),(421,23),(84,23)]

WHITE_SIX_RECTS = [(0,282,67,301),(48,283,67,336),(49,318,128,337),
    (88,300,177,319),(159,265,178,319),(159,265,249,284),(230,229,249,284),
    (230,229,321,248),(302,229,321,284),(302,265,380,284),(340,247,431,266),
    (412,248,431,301),(412,282,502,301),(483,247,502,301),(483,247,574,266),
    (555,248,574,301),(555,282,635,301),(594,265,685,284),(666,247,685,284),
    (594,229,685,248),(594,194,613,248),(594,194,685,213),(666,158,685,213),
    (666,158,725,177),(705,138,725,177)]

WHITE_SEVEN = [
    [(239,650),(275,671),(300,670),(332,655),(345,654),(380,677),(386,685),
     (382,695),(376,698),(278,698),(266,714),(310,715),(319,721),(321,728),
     (314,735),(211,735),(208,748),(248,772),(254,782),(252,789),(245,794),
     (164,794),(147,786),(131,787),(151,800),(155,810),(153,819),(147,826),
     (138,827),(146,837),(148,846),(144,852),(135,855),(34,855),(0,863),
     (0,792),(41,816),(111,816),(111,814),(85,814),(78,808),(77,801),
     (82,795),(111,794),(111,775),(90,775),(84,772),(82,767),(83,759),
     (90,754),(111,754),(112,751),(84,751),(84,730),(123,731),(129,721),
     (161,737),(190,748),(202,747),(179,727),(163,701),(162,694),(166,688),
     (174,688),(211,711),(253,712),(237,683),(228,663),(228,657),(233,651)],
    [(47,762),(61,751),(74,751),(74,773),(61,774)],
    [(101,735),(116,731),(128,735),(124,749),(100,748)],
]

BALLS = {1:[(962,632,990,660),(972,685,1003,716)],
         2:[(448,595,479,627),(439,648,473,682)],
         3:[(155,778,195,816),(167,833,203,870)],
         4:[(716,778,754,817),(788,778,825,817),(780,816,813,849)],
         5:[(334,529,387,578),(363,582,447,665)],
         6:[(698,157,723,180),(663,160,687,185)],
         7:[(303,645,328,671),(257,670,296,710)],
         8:[(338,389,355,414),(315,423,333,449)],
         9:[(713,61,733,89),(660,79,682,108)]}


def small_holes(mask, limit):
    n, labels, stats, _ = cv2.connectedComponentsWithStats(255 - mask, 8)
    for k in range(1, n):
        x, y, w, h, area = stats[k]
        if area <= limit and x > 0 and y > 0 and x + w < mask.shape[1] and y + h < mask.shape[0]:
            mask[labels == k] = 255
    return mask


def drafts():
    manifest_path = ROOT / 'test-assets/solid/manifest.json'
    if manifest_path.exists() and json.loads(manifest_path.read_text(encoding='utf-8')).get('annotation_status') == 'APPROVED_AND_FROZEN':
        raise RuntimeError('Approved labels are frozen; draft generation cannot overwrite them.')
    output = ROOT / 'test-assets/solid/annotation-drafts'
    reviews = ROOT / 'artifacts/upgrade-04/02-recognition/annotation-review'
    output.mkdir(parents=True, exist_ok=True)
    reviews.mkdir(parents=True, exist_ok=True)
    samples = []
    overview = Image.new('RGB', (1500, 1140), '#404040')
    for index, path in enumerate(sorted((ROOT / 'testscreenshots/test_2').glob('*.png')), 1):
        source = Image.open(path).convert('RGB')
        rgb = np.array(source)
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        if index in (1, 2, 3, 6, 7, 8, 9):
            mask = cv2.inRange(hsv, np.array([10, 40, 48]), np.array([43, 255, 255]))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
            mask = small_holes(mask, 1000)
            # Color-picking annotations omit white clipping; outline these visibly
            # overexposed track sections separately by hand before review.
        elif index == 4:
            v = hsv[:, :, 2]
            mask = np.uint8((v >= 29) & (v <= 210)) * 255
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
            mask = small_holes(mask, 5500)
        else:
            mask = cv2.inRange(hsv, np.array([0, 65, 60]), np.array([179, 255, 255]))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
            mask = small_holes(mask, 8000)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        cleaned = np.zeros_like(mask)
        for k in range(1, count):
            if stats[k, cv2.CC_STAT_AREA] >= 130:
                cleaned[labels == k] = 255
        mask = Image.fromarray(cleaned)
        draw = ImageDraw.Draw(mask)
        if index == 5:
            draw.rectangle((0, 0, source.width, source.height), fill=0)
            draw.polygon(SCAN_OUTLINE, fill=255)
        if index == 6:
            for box in WHITE_SIX_RECTS:
                draw.rectangle(box, fill=255)
            for points in [[(88,318),(135,318),(141,323),(140,331),(94,358),(88,354)],
                           [(340,265),(389,265),(396,270),(393,279),(346,305),(340,300)],
                           [(594,282),(640,282),(647,288),(644,296),(600,322),(594,318)],
                           [(706,138),(729,150),(728,158),(706,158)]]:
                draw.polygon(points, fill=255)
        if index == 7:
            for points in WHITE_SEVEN:
                draw.polygon(points, fill=255)
        for box in BALLS.get(index, []):
            draw.ellipse(box, fill=0)
        if index == 4:
            values = np.array(mask)
            # The large white background logo is not a track icon. Preserve the
            # surrounding tile faces, but exclude its visible white lettering.
            values[np.all(rgb > 215, axis=2)] = 0
            mask = Image.fromarray(values)
        mask.save(output / f'solid-{index:02}-draft.png')
        rgba = source.convert('RGBA')
        tint = Image.new('RGBA', source.size, (50, 235, 100, 0))
        tint.putalpha(mask.point(lambda x: round(x * .45)))
        overlay = Image.alpha_composite(rgba, tint)
        cut = rgba.copy()
        cut.putalpha(mask)
        cutbg = Image.new('RGBA', source.size, '#697482')
        cutbg.alpha_composite(cut)
        width = 520
        height = round(source.height * width / source.width)
        sheet = Image.new('RGB', (width * 3, height + 35), '#262626')
        draw = ImageDraw.Draw(sheet)
        for col, (label, image) in enumerate(zip(('ORIGINAL', 'GREEN = KEEP (DRAFT)', 'CUTOUT (NOT APPROVED)'), (source, overlay, cutbg))):
            sheet.paste(image.convert('RGB').resize((width, height)), (width * col, 35))
            draw.text((width * col + 8, 10), f'solid-{index:02} / {label}', fill='white')
        sheet.save(reviews / f'solid-{index:02}-review.png')
        thumb = ImageOps.contain(cutbg.convert('RGB'), (490, 345))
        overview.paste(thumb, (((index-1) % 3) * 500, ((index-1) // 3) * 380 + 25))
        ImageDraw.Draw(overview).text((((index-1) % 3) * 500 + 8, ((index-1) // 3) * 380 + 8), f'solid-{index:02} DRAFT CUTOUT', fill='white')
        samples.append({'id': f'solid-{index:02}', 'file': str(path.relative_to(ROOT)).replace('\\', '/'),
                        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size': list(source.size),
                        'ground_truth': f'annotation-drafts/solid-{index:02}-draft.png', 'annotation_approved': False})
    overview.save(reviews / 'overview.png')
    manifest = {'scope': 'User-provided test_2 solid/dark patterned backgrounds; track outline/interior/icons, exclude balls/particles/decoration.',
                'thresholds': {'intersection_over_union_min': .9}, 'annotation_method': 'Independent per-image color selections with manual cleanup; awaiting human review, never production output.',
                'samples': samples}
    (ROOT / 'test-assets/solid/manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    drafts()
