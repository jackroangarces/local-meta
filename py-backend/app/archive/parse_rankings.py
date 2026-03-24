from __future__ import annotations

# OUTDATED, but interesting to look at

import json
import re
from pathlib import Path

import os
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
from paddleocr import PaddleOCR
import cv2

RAW_ROOT = Path("data/raw/rankings")
PARSED_ROOT = Path("data/parsed/rankings")

def make_row_boxes(start_y: int, count: int, row_height: int, row_gap: int) -> list[tuple[int, int]]:
    return [
        (start_y + i * (row_height + row_gap), row_height)
        for i in range(count)
    ]

def make_split_row_boxes(blocks: list[tuple[int, int, int, int]]) -> list[tuple[int, int]]:
    rows: list[tuple[int, int]] = []
    for start_y, count, row_height, row_gap in blocks:
        rows.extend(make_row_boxes(start_y, count, row_height, row_gap))
    return rows

LAYOUTS: dict[tuple[int, int], dict] = {
    # width, height
    (4570, 3154): {
        "name": "5col",
        "columns": [
            {
                # left edge of column
                "x1": 45,
                # right edge of column
                "x2": 628,
                "row_boxes": make_row_boxes(start_y=450, count=21, row_height=118, row_gap=0),
            },
            {
                "x1": 950,
                "x2": 1526,
                "row_boxes": make_row_boxes(start_y=450, count=21, row_height=118, row_gap=0),
            },
            {
                "x1": 1848,
                "x2": 2424,
                "row_boxes": make_split_row_boxes([
                    (450, 8, 118, 0),
                    (1996, 8, 118, 0), 
                ]),
            },
            {
                "x1": 2752,
                "x2": 3325,
                "row_boxes": make_row_boxes(start_y=450, count=21, row_height=118, row_gap=0),
            },
            {
                "x1": 3653,
                "x2": 4236,
                "row_boxes": make_row_boxes(start_y=450, count=21, row_height=118, row_gap=0),
            },
        ],
    },
    (2768, 2821): {
        "name": "3col",
        "columns": 3,
    },
    (1856, 1886): {
        "name": "2col",
        "columns": 2,
    },
}

def load_manifest(snapshot_dir: Path) -> dict:
    manifest_path = snapshot_dir / "manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))

def load_image(image_path: Path):
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")
    return image

# Determine which layout it is based on the image size
def get_layout(image) -> dict:
    height, width = image.shape[:2]
    key = (width, height)
    if key not in LAYOUTS:
        raise ValueError(
            f"Unsupported image size: {key}. "
            f"Known sizes: {list(LAYOUTS.keys())}"
        )
    return LAYOUTS[key]

# Returns a list of row boxes in (col_idx, row_idx, x, y, w, h) format.
def generate_row_boxes(layout: dict) -> list[tuple[int, int, int, int, int, int]]:
    columns = layout.get("columns")
    boxes: list[tuple[int, int, int, int, int, int]] = []
    for col_idx, col in enumerate(columns, start=1):
        x1 = int(col["x1"])
        x2 = int(col["x2"])
        w = int(x2 - x1)
        if w <= 0:
            raise ValueError(f"Invalid column width for col {col_idx}: x1={x1}, x2={x2}")
        row_boxes = col.get("row_boxes", [])
        for row_idx, (y, h) in enumerate(row_boxes, start=1):
            boxes.append((col_idx, row_idx, x1, int(y), w, int(h)))
    return boxes

def ocr_boxes_to_file(image_path: str, boxes, output_file: str):
    ocr = PaddleOCR(
        use_textline_orientation=True,
        lang="en"
    )
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Could not load image: {image_path}")
    
    lines = []
    for rank, (col_idx, row_idx, x, y, w, h) in enumerate(boxes, start=1):
        crop = img[y:y+h, x:x+w]
        result = ocr.predict(crop)
        text = ""
        if result and isinstance(result, list):
            first = result[0]
            if isinstance(first, dict) and "rec_texts" in first:
                text = " ".join(first["rec_texts"]).strip()

        cleaned_text = normalize_row(text, rank)
        lines.append(cleaned_text)

    with open(output_file, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")
    print(f"Wrote OCR output to {output_file}")

def normalize_row(text: str, rank: int) -> str:
    tokens = text.split()
    rating = None
    name_parts = []
    
    for token in tokens:
        # rating (float or K)
        if re.match(r"^\d+(\.\d+)?K?$", token) and ("." in token or token.endswith("K")):
            if rating is None:
                rating = token
            else:
                name_parts.append(token)
            continue
        # skip integers
        if re.match(r"\d+", token):
            continue
        # skip common rank errors
        if token in {"F", "f", "I", "l", "|"}:
            continue
        # Everything else is name
        name_parts.append(token)

    name = " ".join(name_parts).strip()
    return f"{rank} {name} {rating or ''}".strip()

# debug
def draw_boxes(image, boxes: list[tuple[int, int, int, int, int, int]]):
    debug = image.copy()
    for col_idx, row_idx, x, y, w, h in boxes:
        cv2.rectangle(debug, (x, y), (x + w, y + h), (0, 255, 0), 2)
        label = f"C{col_idx}-R{row_idx}"
        cv2.putText(
            debug,
            label,
            (x, max(20, y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 255, 0),
            1,
            cv2.LINE_AA,
        )
    return debug

# debug
def save_debug_rows(
    image,
    boxes: list[tuple[int, int, int, int, int, int]],
    output_dir: Path,
):
    rows_dir = output_dir / "rows"
    rows_dir.mkdir(parents=True, exist_ok=True)

    for col_idx, row_idx, x, y, w, h in boxes:
        crop = image[y : y + h, x : x + w]
        filename = f"col_{col_idx}_row_{row_idx:02d}.png"
        cv2.imwrite(str(rows_dir / filename), crop)

def main() -> None:
    # just one snapshot for now
    snapshot_name = "2026-03-19"
    snapshot_dir = RAW_ROOT / snapshot_name
    manifest = load_manifest(snapshot_dir)
    output_dir = PARSED_ROOT / snapshot_name
    output_dir.mkdir(parents=True, exist_ok=True)

    for region_entry in manifest["regions"]:
        region = region_entry["region"]
        local_path = region_entry["local_path"]
        image_path = snapshot_dir / local_path
        boxes = generate_row_boxes(get_layout(load_image(image_path)))
        #debug_image = draw_boxes(load_image(image_path), boxes)
        #cv2.imwrite(str(output_dir / "debug_boxes.png"), debug_image)
        #save_debug_rows(load_image(image_path), boxes, output_dir)
        ocr_boxes_to_file(image_path, boxes, output_dir / "ocr.txt")

# Only run main if the script is executed directly
if __name__ == "__main__":
    main()