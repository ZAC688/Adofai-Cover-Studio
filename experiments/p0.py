"""Offline P0 experiment: compare a structural baseline and a local saliency model.

Neither method is declared an ADOFAI detector until the real-data gate passes.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import subprocess
from urllib.request import urlopen
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps

MODEL_SHA256 = "309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8"
MAX_IMAGE_BYTES = 10_000_000


def resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def decode_image(raw: bytes) -> Image.Image:
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("Image exceeds 10 MB")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in {"PNG", "JPEG"}:
                raise ValueError("Only PNG and JPEG are supported")
            image.load()
            return ImageOps.exif_transpose(image).convert("RGBA")
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Invalid image") from exc


def validate_model(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Offline model is missing: {path}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != MODEL_SHA256:
        raise ValueError("Offline model checksum mismatch")


def saliency_mask(image: Image.Image, model_path: Path) -> Image.Image:
    validate_model(model_path)
    rgb = image.convert("RGB").resize((320, 320), Image.Resampling.LANCZOS)
    values = np.asarray(rgb, dtype=np.float32)
    values = values / max(float(values.max()), 1.0)
    values = (values - np.array([.485, .456, .406], dtype=np.float32)) / np.array(
        [.229, .224, .225], dtype=np.float32)
    tensor = np.ascontiguousarray(values.transpose(2, 0, 1)[None])
    if os.environ.get('ADOFAI_ANDROID') == '1':
        from backend.android_inference import predict
        result = predict(tensor, model_path)
    else:
        import onnxruntime as ort
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        session = ort.InferenceSession(str(model_path), sess_options=options,
                                       providers=["CPUExecutionProvider"])
        result = session.run(None, {session.get_inputs()[0].name: tensor})[0][0, 0]
    low, high = float(result.min()), float(result.max())
    if high - low < 1e-8:
        result = np.zeros_like(result)
    else:
        result = (result - low) / (high - low)
    mask = Image.fromarray(np.clip(result * 255, 0, 255).astype(np.uint8))
    return mask.resize(image.size, Image.Resampling.LANCZOS)


def structural_mask(image: Image.Image) -> Image.Image:
    """Closed-edge candidate extraction, deliberately not a color-removal claim."""
    rgb = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    smooth = cv2.GaussianBlur(gray, (5, 5), 0)
    high, _ = cv2.threshold(smooth, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    edges = cv2.Canny(smooth, max(5, high * .5), max(15, high))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mask = np.zeros_like(gray)
    min_area = max(12, gray.size * .00002)
    for contour in contours:
        if cv2.contourArea(contour) >= min_area:
            cv2.drawContours(mask, [contour], -1, 255, cv2.FILLED)
    return Image.fromarray(mask)


def cutout(image: Image.Image, mask: Image.Image) -> Image.Image:
    if image.size != mask.size:
        raise ValueError("Mask and image sizes differ")
    rgba = np.array(image.convert("RGBA"))
    alpha = np.asarray(mask.convert("L"), dtype=np.uint16)
    rgba[:, :, 3] = ((rgba[:, :, 3].astype(np.uint16) * alpha + 127) // 255).astype(np.uint8)
    return Image.fromarray(rgba)


def quality_metrics(predicted: Image.Image, truth: Image.Image) -> dict[str, float]:
    if predicted.size != truth.size:
        raise ValueError("Prediction and ground truth sizes differ")
    p = np.asarray(predicted.convert("L")) >= 128
    t = np.asarray(truth.convert("L")) >= 128
    foreground, background = int(t.sum()), int((~t).sum())
    if not foreground or not background:
        raise ValueError("Ground truth must contain track and background")
    return {
        "track_recall": float((p & t).sum() / foreground),
        "background_residual": float((p & ~t).sum() / background),
        "intersection_over_union": float((p & t).sum() / (p | t).sum()),
    }


def assess_dataset(manifest_path: Path, predictions_dir: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures = []
    samples = manifest["samples"]
    categories = {sample["category"] for sample in samples}
    for category in ("background", "transparent", "dark", "complex"):
        if category not in categories:
            failures.append(f"Missing real sample category: {category}")
    complex_levels = {s.get("level") for s in samples if s["category"] == "complex"}
    if len(complex_levels - {None}) < 2:
        failures.append("Need complex screenshots from at least two distinct levels/themes")
    if not any(s.get("split") == "holdout" for s in samples if s["category"] == "complex"):
        failures.append("Missing independent complex-background holdout sample")
    results = []
    for sample in samples:
        if sample["category"] not in {"dark", "complex"}:
            continue
        truth_path = sample.get("ground_truth")
        if not truth_path or not sample.get("annotation_approved", False):
            failures.append(f"{sample['id']}: missing approved ground-truth mask")
            continue
        truth = manifest_path.parent / truth_path
        prediction = predictions_dir / f"{sample['id']}-mask.png"
        if not truth.is_file() or not prediction.is_file():
            failures.append(f"{sample['id']}: missing annotation or prediction file")
            continue
        values = quality_metrics(Image.open(prediction), Image.open(truth))
        results.append({"id": sample["id"], **values})
        if values["track_recall"] < .90 or values["background_residual"] > .05:
            failures.append(f"{sample['id']}: recognition is below the confirmed 90% / 5% gate")
    return {"passed": not failures, "failures": failures, "results": results}


def run_experiment(source: Path, output: Path, model_path: Path) -> dict:
    image = decode_image(source.read_bytes())
    output.mkdir(parents=True, exist_ok=True)
    image.save(output / "original.png")
    masks = {"structure": structural_mask(image), "u2netp": saliency_mask(image, model_path)}
    sheet = Image.new("RGB", (1200, 440), "#20252c")
    draw = ImageDraw.Draw(sheet)
    previews = [("original", image)]
    report = {"source": source.name, "size": list(image.size), "candidates": {}}
    for name, mask in masks.items():
        mask.save(output / f"{name}-mask.png")
        result = cutout(image, mask)
        result.save(output / f"{name}-cutout.png")
        report["candidates"][name] = {
            "foreground_fraction": float((np.asarray(mask) >= 128).mean()),
            "quality": "NOT_EVALUATED_NO_APPROVED_GROUND_TRUTH",
        }
        bg = Image.new("RGBA", image.size, "#596978")
        bg.alpha_composite(result)
        previews.append((name + " (unvalidated)", bg))
    for index, (name, preview) in enumerate(previews):
        preview = ImageOps.contain(preview.convert("RGB"), (390, 390))
        sheet.paste(preview, (index * 400 + 5, 35))
        draw.text((index * 400 + 8, 10), name, fill="white")
    sheet.save(output / "comparison.png")
    (output / "experiment.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


PAGE = """<!doctype html><meta charset="utf-8"><title>ADOFAI P0 离线识别验证</title>
<style>body{font:16px 'Microsoft YaHei',sans-serif;background:#151b24;color:#edf2fa;
max-width:1200px;margin:32px auto;padding:16px}img{width:100%}a{color:#8ed9ff}</style>
<h1>ADOFAI · P0 离线识别验证</h1><p>这是识别实验，不是完成的封面编辑器。
候选结果未经标注验收，不能视为轨道识别通过。</p>
<img src="comparison.png" alt="原图、结构候选与模型候选对照">
<p><a href="structure-cutout.png">查看结构候选</a> ·
<a href="u2netp-cutout.png">查看模型候选</a></p>"""


def find_edge() -> Path:
    candidates = [
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
        / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
        / "Microsoft/Edge/Application/msedge.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("Microsoft Edge was not found; no other browser will be opened")


def open_edge(port: int) -> None:
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    subprocess.Popen([str(find_edge()), f"http://127.0.0.1:{port}/"], creationflags=flags)


def serve(output: Path, port: int, ready_file: Path | None, launch_edge: bool = False) -> None:
    if ready_file and ready_file.is_file():
        try:
            previous = json.loads(ready_file.read_text(encoding="utf-8"))
            address = f"http://127.0.0.1:{int(previous['port'])}/health"
            with urlopen(address, timeout=1) as response:
                if json.load(response).get("application") == "adofai-p0":
                    if launch_edge:
                        open_edge(previous["port"])
                    return
        except (OSError, ValueError, KeyError):
            pass
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(output), **kwargs)

        def do_GET(self):
            if self.path == "/health":
                payload = b'{"application":"adofai-p0","status":"ready"}'
            elif self.path in {"/", "/index.html"}:
                payload = PAGE.encode("utf-8")
            else:
                return super().do_GET()
            self.send_response(200)
            self.send_header("Content-Type", "application/json" if self.path == "/health"
                             else "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    if ready_file:
        ready_file.parent.mkdir(parents=True, exist_ok=True)
        ready_file.write_text(json.dumps({"port": server.server_port, "pid": os.getpid()}),
                              encoding="utf-8")
    if launch_edge:
        open_edge(server.server_port)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=resource_root() / "models/u2netp.onnx")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--ready-file", type=Path)
    parser.add_argument("--open-edge", action="store_true")
    args = parser.parse_args()
    if args.input:
        print(json.dumps(run_experiment(args.input, args.output, args.model)))
    if args.serve:
        serve(args.output, args.port, args.ready_file, args.open_edge)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
