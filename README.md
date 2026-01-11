# PDF Sentinel

PDF Sentinel is a lightweight safety inspection library for PDF documents.
It detects oversized, vector-heavy, or resource-intensive pages (like blueprints)
that can slow down or crash OCR, rendering, or document-processing pipelines.

It is designed as a pre-flight guard before expensive operations such as OCR,
Vision-LLM inference, rasterization, or downstream document pipelines.

---

## Features

- Detects risky PDF pages:
  - Oversized page dimensions (A0, engineering drawings, blueprints)
  - Large embedded images
  - Vector-heavy pages (architectural / CAD drawings)
  - Pages with excessive rasterization cost
- Page-level and file-level analysis
- Two parallel safety models:
  - Default (configurable, conservative)
  - Advanced (tuned, risk-based)
- JSON output for API integration

---

## Installation

```bash
pip install pdfsentinel
```

---

## Quick Start

```python
from pdfsentinel import PDFSentinel

sentinel = PDFSentinel()

print(sentinel.is_file_safe("samples/test.pdf"))
print(sentinel.is_page_safe("samples/test.pdf", 1, json_response=True))
```

---

## Outputs

PDF Sentinel returns Python dicts by default.
If `json_response=True`, the same structure is returned as a JSON string.

All pages include both verdicts:

- `is_page_safety` + `errors` (default model)
- `is_page_safety_advanced` + `errors_advanced` (advanced model)

File-level analysis includes summary strings so you can quickly see which pages failed:

- `unsafe_pages` (comma-separated page numbers for default model)
- `unsafe_pages_advanced` (comma-separated page numbers for advanced model)

No error aggregation is done at the file root; reasons live on each page result.

---

## Public API

### 1) `file_analysis(file_path, config=None, json_response=False)`

Runs a full scan of all pages and returns per-page results.

**Returns (dict / JSON):**

```json
{
  "file_name": "test.pdf",
  "pages": 2,
  "is_file_safety": false,
  "unsafe_pages": "2",
  "is_file_safety_advanced": true,
  "unsafe_pages_advanced": "",
  "results": [
    {
      "page": 1,
      "is_page_safety": true,
      "errors": [],
      "is_page_safety_advanced": true,
      "errors_advanced": [],
      "metrics": {
        "physical": {},
        "images": [],
        "vector": {},
        "text": {}
      },
      "summary": {
        "page_width_pt": 612.0,
        "page_height_pt": 792.0,
        "max_embedded_image_pixels": 0,
        "vector_path_count": 58,
        "raster_estimate_pixels_300dpi": 8415000
      }
    }
  ]
}
```

---

### 2) `page_analysis(file_path, page, config=None, json_response=False)`

Runs a detailed scan of a single page (1-based index).

**Returns (dict / JSON):**

```json
{
  "file_name": "test.pdf",
  "page": 2,
  "is_page_safety": false,
  "errors": [
    "raster_estimate_too_big:77760000"
  ],
  "is_page_safety_advanced": true,
  "errors_advanced": [],
  "metrics": {
    "physical": {},
    "images": [],
    "vector": {},
    "text": {}
  },
  "summary": {
    "page_width_pt": 2592.0,
    "page_height_pt": 1728.0,
    "max_embedded_image_pixels": 354652,
    "vector_path_count": 33035,
    "raster_estimate_pixels_300dpi": 77760000
  }
}
```

If the page index is invalid, the method returns:

```json
{
  "file_name": "test.pdf",
  "page": 999,
  "is_page_safety": false,
  "errors": ["invalid_page:999"],
  "is_page_safety_advanced": false,
  "errors_advanced": ["invalid_page:999"],
  "metrics": { "physical": {}, "images": [], "vector": {}, "text": {} },
  "summary": {
    "page_width_pt": 0.0,
    "page_height_pt": 0.0,
    "max_embedded_image_pixels": 0,
    "vector_path_count": 0,
    "raster_estimate_pixels_300dpi": 0
  }
}
```

---

### 3) `is_file_safe(file_path, config=None, json_response=False)`

Convenience method that returns only the unsafe pages (default + advanced).
Useful for fast checks or CLI output.

**Returns (dict / JSON):**

```json
{
  "file_name": "test.pdf",
  "pages": 2,
  "is_file_safety": false,
  "unsafety_pages": [
    {
      "page": 2,
      "errors": [
        "raster_estimate_too_big:77760000"
      ]
    }
  ],
  "is_file_safety_advanced": true,
  "unsafety_pages_advanced": []
}
```

---

### 4) `is_page_safe(file_path, page, config=None, json_response=False)`

Convenience method for a single page.
This currently returns the same structure as `page_analysis(...)`.

**Returns (dict / JSON):**

```json
{
  "file_name": "test.pdf",
  "page": 2,
  "is_page_safety": false,
  "errors": [
    "raster_estimate_too_big:77760000"
  ],
  "is_page_safety_advanced": true,
  "errors_advanced": []
}
```

---

## Configuration (Default Model Only)

You can override default safety thresholds per call.
The advanced model is tuned and not intended to be overridden at runtime.

```python
sentinel.is_file_safe(
    "samples/test.pdf",
    config={
        "max_page_size": 1800,
        "max_image_pixels": 10_000_000,
        "max_vectors_operations": 1000,
        "max_raster_pixels": 20_000_000
    }
)
```

| Parameter               | Default    | Description                                  |
|------------------------|------------|----------------------------------------------|
| max_page_size          | 2000       | Max page dimension in points (pt)            |
| max_image_pixels       | 20000000   | Max pixels for a single embedded image       |
| max_vectors_operations | 1500       | Max allowed vector drawing operations        |
| max_raster_pixels      | 30000000   | Estimated raster size (300 DPI)              |

---

## Advanced Safety Model (How it Works)

PDF Sentinel includes an advanced safety model that runs in parallel with the default rules.

While the default model focuses on conservative limits (page size, vector count, raster estimates), the advanced model is risk-based and tuned using real-world performance data from PDF rendering pipelines.

The advanced model flags a page as unsafe if any of the following conditions are met:

Extreme physical size
Pages whose largest dimension exceeds a hard threshold are likely to cause excessive render time, regardless of content.

Very wide pages
Unusually wide pages (common in blueprints and engineering drawings) tend to stress rasterization and memory allocation.

Raster fan-out
Pages containing many embedded images with large combined pixel counts (and no soft masks) are strong indicators of memory pressure and CPU spikes during rendering.

Conceptually, the advanced decision is a simple OR gate over these risk signals:

dangerous =
    render_risk
    OR rss_risk

Where:

render_risk is driven primarily by physical page dimensions

rss_risk is driven by raster fan-out and total pixel pressure

The advanced model is intentionally not configurable at runtime.
Its thresholds are pre-tuned and designed to be stable, predictable, and comparable across environments.

This makes it ideal for:

Early rejection of pathological PDFs

Protecting OCR and AI pipelines from worst-case inputs

Fast, deterministic safety decisions at scale

You are free to rely on the default model, the advanced model, or both — depending on how strict your pipeline needs to be.

## License

MIT License © 2025 — Not Empty Foundation
