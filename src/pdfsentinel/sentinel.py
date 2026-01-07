import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from .helper import pymupdf

class PDFSentinel:
    DEFAULT_CONFIG = {
        "max_page_size": 2000,
        "max_image_pixels": 20_000_000,
        "max_vectors_operations": 1500,
        "max_raster_pixels": 30_000_000,
    }

    def __init__(self, base_config: Optional[Dict[str, Any]] = None):
        self.base_config = self._merge_config(self.DEFAULT_CONFIG, base_config or {})

    @staticmethod
    def _merge_config(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        cfg = dict(base)
        for k, v in override.items():
            if v is not None:
                cfg[k] = v
        return cfg


    def _analyze_page(
        self,
        doc_path: str,
        doc,
        page_index: int,
        config: Dict[str, Any],
        include_file_name: bool = True,
    ) -> Dict[str, Any]:
        page = pymupdf.load_page(doc, page_index)
        page_width, page_height = pymupdf.get_page_size(page)

        errors: List[str] = []

        max_page_size = config["max_page_size"]
        if page_width > max_page_size or page_height > max_page_size:
            errors.append(f"page_too_large:{page_width:.1f}x{page_height:.1f}")

        max_image_pixels = config["max_image_pixels"]
        images = pymupdf.get_page_images(page)
        max_img_px_on_page = 0
        for img in images:
            xref = img[0]

            try:
                info = pymupdf.extract_image(doc, xref)
            except Exception as e:
                continue

            w = info.get("width", 0)
            h = info.get("height", 0)
            pix = w * h
            if pix > max_img_px_on_page:
                max_img_px_on_page = pix
            if pix > max_image_pixels:
                errors.append(f"embedded_image_too_big:{w}x{h}")

        max_vectors_operations = config["max_vectors_operations"]
        drawings = pymupdf.get_page_drawings(page)
        vector_ops = len(drawings)
        if vector_ops > max_vectors_operations:
            errors.append(f"too_many_vector_ops:{vector_ops}")

        max_raster_pixels = config["max_raster_pixels"]
        width_in = page_width / 72.0
        height_in = page_height / 72.0
        est_pixels = int(width_in * 300) * int(height_in * 300)
        if est_pixels > max_raster_pixels:
            errors.append(f"raster_estimate_too_big:{est_pixels}")

        is_page_safe = len(errors) == 0

        data = {
            "page": page_index + 1,
            "is_page_safety": is_page_safe,
            "errors": errors,
            "page_width": page_width,
            "page_height": page_height,
            "max_image_pixels": max_img_px_on_page,
            "max_vectors_operations": vector_ops,
            "max_raster_pixels": est_pixels,
        }

        if include_file_name:
            data["file_name"] = str(Path(doc_path).name)

        return data

    def file_analysis(
        self,
        file_path: str,
        config: Optional[Dict[str, Any]] = None,
        json_response: bool = False,
    ) -> Dict[str, Any] | str:
        cfg = self._merge_config(self.base_config, config or {})
        doc = pymupdf.open_document(file_path)
        total_pages = pymupdf.get_page_count(doc)

        results: List[Dict[str, Any]] = []
        for idx in range(total_pages):
            page_result = self._analyze_page(file_path, doc, idx, cfg, include_file_name=False)
            results.append(page_result)

        is_file_safe = all(p["is_page_safety"] for p in results)
        response = {
            "file_name": str(Path(file_path).name),
            "pages": total_pages,
            "is_file_safety": is_file_safe,
            "results": results,
        }

        return json.dumps(response, indent=4, ensure_ascii=False) if json_response else response

    def page_analysis(
        self,
        file_path: str,
        page: int,
        config: Optional[Dict[str, Any]] = None,
        json_response: bool = False,
    ) -> Dict[str, Any] | str:
        cfg = self._merge_config(self.base_config, config or {})
        doc = pymupdf.open_document(file_path)
        total = pymupdf.get_page_count(doc)
        if page < 1 or page > total:
            result = {
                "file_name": str(Path(file_path).name),
                "page": page,
                "is_page_safety": False,
                "errors": [f"invalid_page:{page}"],
                "page_width": 0,
                "page_height": 0,
                "max_image_pixels": 0,
                "max_vectors_operations": 0,
                "max_raster_pixels": 0,
            }
            return json.dumps(result, indent=4, ensure_ascii=False) if json_response else result

        result = self._analyze_page(file_path, doc, page - 1, cfg, include_file_name=True)
        return json.dumps(result, indent=4, ensure_ascii=False) if json_response else result

    def is_file_safe(
        self,
        file_path: str,
        config: Optional[Dict[str, Any]] = None,
        json_response: bool = False,
    ) -> Dict[str, Any] | str:
        analysis = self.file_analysis(file_path, config)
        unsafety_pages = [
            {"page": r["page"], "errors": r["errors"]}
            for r in analysis["results"]
            if not r["is_page_safety"]
        ]
        result = {
            "file_name": analysis["file_name"],
            "pages": analysis["pages"],
            "is_file_safety": len(unsafety_pages) == 0,
            "unsafety_pages": unsafety_pages,
        }
        return json.dumps(result, indent=4, ensure_ascii=False) if json_response else result

    def is_page_safe(
        self,
        file_path: str,
        page: int,
        config: Optional[Dict[str, Any]] = None,
        json_response: bool = False,
    ) -> Dict[str, Any] | str:
        result = self.page_analysis(file_path, page, config)
        if isinstance(result, str):
            return result
        return json.dumps(result, indent=4, ensure_ascii=False) if json_response else result