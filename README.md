# PDF Sentinel

**PDF Sentinel** is a lightweight safety inspection library for PDF documents. It detects oversized, vector-heavy, or otherwise resource-intensive pages (like blueprints) that could slow down or crash OCR and pipelines.

---

## Features

* Detects dangerous or heavy PDF pages:

  * Large page dimensions (A0, engineering blueprints, etc.)
  * Massive embedded images
  * Vector-heavy drawings (architectural plans)
  * Pages that exceed safe rasterization thresholds
* Returns simplified or detailed analysis for pages and files
* Configurable limits (page size, pixel thresholds, etc.)
* Optional JSON response for easy API integration

---

## Installation

```bash
pip install PDFSentinel
```

This will install the library from PyPI and make it available to import in your project.

---

## Usage

### Simplified file safety check

```python
from pdfsentinel import PDFSentinel

sentinel = PDFSentinel()
result = sentinel.is_file_safe("samples/test.pdf")
print(result)
```

**Output (Python dict):**

```json
{
    "file_name": "test.pdf",
    "pages": 23,
    "is_file_safety": true,
    "unsafety_pages": []
}
```

You can also get JSON-formatted output directly:

```python
print(sentinel.is_file_safe("samples/test.pdf", json_response=True))
```

---

### Simplified page safety check

```python
print(sentinel.is_page_safe("samples/test.pdf", 2, json_response=True))
```

**Example output:**

```json
{
    "file_name": "test1.pdf",
    "page": 24,
    "is_page_safety": false,
    "errors": [
        "page_too_large:2592.0x1728.0",
        "too_many_vector_ops:33035",
        "raster_estimate_too_big:77760000"
    ]
}
```

---

### Full file analysis

```python
print(sentinel.file_analysis("samples/test.pdf", json_response=True))
```

**Output:**

```json
{
    "file_name": "test1.pdf",
    "pages": 2,
    "is_file_safety": true,
    "results": [
        {
            "page": 1,
            "is_page_safety": true,
            "errors": [],
            "page_width": 612.0,
            "page_height": 792.0,
            "max_image_pixels": 0,
            "max_vectors_operations": 58,
            "max_raster_pixels": 8415000
        },
        {
            "page": 2,
            "is_page_safety": false,
            "errors": [
                "page_too_large:2592.0x1728.0",
                "too_many_vector_ops:33035",
                "raster_estimate_too_big:77760000"
            ],
            "page_width": 612.0,
            "page_height": 792.0,
            "max_image_pixels": 0,
            "max_vectors_operations": 58,
            "max_raster_pixels": 8415000
        }
    ]
}
```

---

### Single page detailed analysis

```python
print(sentinel.page_analysis("samples/test.pdf", 3, json_response=True))
```

---

## Configuration

You can override safety thresholds per call:

```python
sentinel.is_file_safe("samples/test.pdf", config={
    "max_page_size": 1800,
    "max_image_pixels": 10_000_000,
    "max_vectors_operations": 1000,
    "max_raster_pixels": 20_000_000
})
```

| Parameter                | Default    | Description                                   |
| ------------------------ | ---------- | --------------------------------------------- |
| `max_page_size`          | 2000       | Max page dimension in points                  |
| `max_image_pixels`       | 20,000,000 | Max embedded image size (w × h)               |
| `max_vectors_operations` | 1500       | Max allowed vector drawing operations         |
| `max_raster_pixels`      | 30,000,000 | Estimated max rasterization size (at 300 dpi) |

---

## Testing Example

You can create a simple `test_sentinel.py` at the project root:

```python
import PDFSentinel

sentinel = PDFSentinel()

result = sentinel.is_file_safe("samples/test.pdf", json_response=True)
print(result)
```

---


## License

MIT License © 2025 — Not Empty Foundation
