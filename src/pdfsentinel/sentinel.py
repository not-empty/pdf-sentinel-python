import json
from pathlib import Path

from .helper import pymupdf


class PDFSentinel:
    DEFAULT_CONFIG = {
        "max_page_size": 2000.0,
        "max_image_pixels": 20_000_000,
        "max_vectors_operations": 1500,
        "max_raster_pixels": 30_000_000,
    }

    ADVANCED_DEFAULT_CONFIG = {
        "render_max_dim": 2400.0,
        "rss_width_huge": 1650.0,
        "rss_img_count": 110,
        "rss_img_total_pixels": 3_000_000,
        "rss_img_max_pixels": 500_000,
        "rss_img_smask_max": 0,
    }

    def __init__(self, base_config=None):
        self.base_config = self._merge_config(self.DEFAULT_CONFIG, base_config or {})
        self.advanced_config = dict(self.ADVANCED_DEFAULT_CONFIG)

    @staticmethod
    def _merge_config(base, override):
        cfg = dict(base)
        for k, v in override.items():
            if v is not None:
                cfg[k] = v
        return cfg

    def _evaluate_page_default(self, physical, images, vector, text, config):
        errors = []

        page_width_pt = float(physical.get("width_pt", 0.0))
        page_height_pt = float(physical.get("height_pt", 0.0))

        max_page_size = float(config["max_page_size"])
        if page_width_pt > max_page_size or page_height_pt > max_page_size:
            errors.append(f"page_too_large:{page_width_pt:.1f}x{page_height_pt:.1f}_pt")

        max_image_pixels = int(config["max_image_pixels"])
        max_img_px_on_page = 0

        for img in images:
            pix = int(img.get("pixel_count") or 0)
            if pix > max_img_px_on_page:
                max_img_px_on_page = pix

            if pix > max_image_pixels:
                w = int(img.get("width") or 0)
                h = int(img.get("height") or 0)
                if w and h:
                    errors.append(f"embedded_image_too_big:{w}x{h}")
                else:
                    errors.append(f"embedded_image_too_big_pixels:{pix}")

        vector_path_count = int(vector.get("path_count") or 0)
        if vector.get("error"):
            errors.append(f"vector_parse_failure:{vector.get('error')}")

        max_vectors_operations = int(config["max_vectors_operations"])
        if vector_path_count > max_vectors_operations:
            errors.append(f"too_many_vector_ops:{vector_path_count}")

        if text.get("error"):
            errors.append(f"text_parse_failure:{text.get('error')}")

        width_in = float(physical.get("width_in", 0.0))
        height_in = float(physical.get("height_in", 0.0))

        est_pixels = int(width_in * 300) * int(height_in * 300)

        max_raster_pixels = int(config["max_raster_pixels"])
        if est_pixels > max_raster_pixels:
            errors.append(f"raster_estimate_too_big:{est_pixels}")

        return {
            "errors": errors,
            "summary": {
                "page_width_pt": page_width_pt,
                "page_height_pt": page_height_pt,
                "max_embedded_image_pixels": max_img_px_on_page,
                "vector_path_count": vector_path_count,
                "raster_estimate_pixels_300dpi": est_pixels,
            },
        }

    def _evaluate_page_advanced(self, physical, images):
        errors_adv = []

        cfg = self.advanced_config

        w = float(physical.get("width_pt", 0.0) or 0.0)
        h = float(physical.get("height_pt", 0.0) or 0.0)
        physical_max_dim = max(w, h)

        if physical_max_dim >= cfg["render_max_dim"]:
            errors_adv.append("render:physical_max_dim>=2400")

        if w >= cfg["rss_width_huge"]:
            errors_adv.append("rss:physical_mediabox_width>=1650")

        img_count = len(images)
        img_total_pixels = 0
        img_max_pixels = 0
        img_smask_count = 0

        for img in images:
            pix = int(img.get("pixel_count") or 0)
            img_total_pixels += pix
            if pix > img_max_pixels:
                img_max_pixels = pix

            if (
                img.get("has_smask") is True
                or img.get("smask") is True
                or img.get("is_smask") is True
                or img.get("smask_ref") is not None
            ):
                img_smask_count += 1

        if (
            img_count >= cfg["rss_img_count"]
            and img_smask_count <= cfg["rss_img_smask_max"]
            and (
                img_total_pixels >= cfg["rss_img_total_pixels"]
                or img_max_pixels >= cfg["rss_img_max_pixels"]
            )
        ):
            errors_adv.append(
                "rss:img_count>=110+smask<=0+(img_total_pixels>=3000000 OR img_max_pixels>=500000)"
            )

        return {"errors_advanced": errors_adv}

    def _analyze_page(self, doc_path, doc, page_index, config, include_file_name=True):
        page = pymupdf.load_page(doc, page_index)

        physical = pymupdf.get_physical_metrics(page)
        images = pymupdf.get_image_metadata(page)
        vector = pymupdf.get_vector_dna(page)
        text = pymupdf.get_text_metadata(page)

        default_eval = self._evaluate_page_default(physical, images, vector, text, config)
        errors = default_eval["errors"]
        summary = default_eval["summary"]
        is_page_safe = len(errors) == 0

        adv_eval = self._evaluate_page_advanced(physical, images)
        errors_adv = adv_eval["errors_advanced"]
        is_page_safe_adv = len(errors_adv) == 0

        data = {
            "page": page_index + 1,
            "is_page_safety": is_page_safe,
            "errors": errors,
            "is_page_safety_advanced": is_page_safe_adv,
            "errors_advanced": errors_adv,
            "metrics": {
                "physical": physical,
                "images": images,
                "vector": vector,
                "text": text,
            },
            "summary": summary,
        }

        if include_file_name:
            data["file_name"] = str(Path(doc_path).name)

        return data

    def file_analysis(self, file_path, config=None, json_response=False):
        cfg = self._merge_config(self.base_config, config or {})
        doc = pymupdf.open_document(file_path)

        total_pages = int(getattr(doc, "page_count", 0) or 0)

        results = []
        for idx in range(total_pages):
            results.append(self._analyze_page(file_path, doc, idx, cfg, include_file_name=False))

        unsafe_pages = [
            str(p["page"])
            for p in results
            if not p["is_page_safety"]
        ]

        unsafe_pages_adv = [
            str(p["page"])
            for p in results
            if not p["is_page_safety_advanced"]
        ]

        response = {
            "file_name": str(Path(file_path).name),
            "pages": total_pages,

            "is_file_safety": len(unsafe_pages) == 0,
            "unsafe_pages": ",".join(unsafe_pages),

            "is_file_safety_advanced": len(unsafe_pages_adv) == 0,
            "unsafe_pages_advanced": ",".join(unsafe_pages_adv),

            "results": results,
        }

        return json.dumps(response, indent=4, ensure_ascii=False) if json_response else response

    def page_analysis(self, file_path, page, config=None, json_response=False):
        cfg = self._merge_config(self.base_config, config or {})
        doc = pymupdf.open_document(file_path)
        total_pages = int(getattr(doc, "page_count", 0) or 0)

        if page < 1 or page > total_pages:
            result = {
                "file_name": str(Path(file_path).name),
                "page": page,
                "is_page_safety": False,
                "errors": [f"invalid_page:{page}"],
                "is_page_safety_advanced": False,
                "errors_advanced": [f"invalid_page:{page}"],
                "metrics": {"physical": {}, "images": [], "vector": {}, "text": {}},
                "summary": {
                    "page_width_pt": 0.0,
                    "page_height_pt": 0.0,
                    "max_embedded_image_pixels": 0,
                    "vector_path_count": 0,
                    "raster_estimate_pixels_300dpi": 0,
                },
            }
            return json.dumps(result, indent=4, ensure_ascii=False) if json_response else result

        result = self._analyze_page(file_path, doc, page - 1, cfg, include_file_name=True)
        return json.dumps(result, indent=4, ensure_ascii=False) if json_response else result

    def is_file_safe(self, file_path, config=None, json_response=False):
        analysis = self.file_analysis(file_path, config, json_response=False)
        unsafety_pages = [
            {"page": r["page"], "errors": r["errors"]}
            for r in analysis["results"]
            if not r["is_page_safety"]
        ]

        unsafety_pages_adv = [
            {"page": r["page"], "errors_advanced": r.get("errors_advanced", [])}
            for r in analysis["results"]
            if not r.get("is_page_safety_advanced", True)
        ]

        result = {
            "file_name": analysis["file_name"],
            "pages": analysis["pages"],
            "is_file_safety": len(unsafety_pages) == 0,
            "unsafety_pages": unsafety_pages,
            "is_file_safety_advanced": len(unsafety_pages_adv) == 0,
            "unsafety_pages_advanced": unsafety_pages_adv,
        }

        return json.dumps(result, indent=4, ensure_ascii=False) if json_response else result

    def is_page_safe(self, file_path, page, config=None, json_response=False):
        result = self.page_analysis(file_path, page, config, json_response=False)
        return json.dumps(result, indent=4, ensure_ascii=False) if json_response else result
