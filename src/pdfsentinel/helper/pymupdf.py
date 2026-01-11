from __future__ import annotations
import fitz
from typing import Dict, Any, List

# --- MUPDF ERROR BYPASS ---
fitz.TOOLS.mupdf_display_errors(False)
fitz.TOOLS.mupdf_display_warnings(False)

def open_document(path: str) -> fitz.Document:
    return fitz.open(path)

def load_page(doc: fitz.Document, index: int) -> fitz.Page:
    return doc.load_page(index)

def get_physical_metrics(page: fitz.Page) -> Dict[str, Any]:
    rect = page.rect
    mediabox = page.mediabox
    return {
        "width_pt": float(rect.width),
        "height_pt": float(rect.height),
        "width_in": float(rect.width / 72.0),
        "height_in": float(rect.height / 72.0),
        "mediabox_width": float(mediabox.width),
        "mediabox_height": float(mediabox.height),
        "rotation": int(page.rotation),
        "user_unit": float(getattr(page, "user_unit", 1.0))
    }

def get_image_metadata(page: fitz.Page) -> List[Dict[str, Any]]:
    image_info = []
    try:
        images = page.get_images(full=True)
    except Exception:
        # If the image table itself is corrupted
        return []

    for img in images:
        try:
            # Defensive extraction: if img[5] (colorspace) is a broken xref, 
            # we cast to string and catch the fail.
            cs_name = str(img[5]) if img[5] is not None else "Unknown"
            
            image_info.append({
                "xref": int(img[0] or 0),
                "smask_xref": int(img[1] or 0),
                "width": int(img[2] or 0),
                "height": int(img[3] or 0),
                "bpc": int(img[4] or 8),
                "colorspace_name": cs_name,
                "pixel_count": int((img[2] or 0) * (img[3] or 0)),
                "is_inline": img[0] == 0
            })
        except (IndexError, TypeError, ValueError):
            continue
    return image_info

def get_vector_dna(page: fitz.Page) -> Dict[str, Any]:
    try:
        drawings = page.get_drawings()
    except Exception:
        # Return empty stats if drawings fail to parse entirely
        return {"path_count": 0, "total_points": 0, "error": "parse_failure"}

    stats = {
        "path_count": len(drawings),
        "total_points": 0,
        "curve_segments": 0,
        "rect_segments": 0,
        "clipping_paths": 0,
        "total_paint_ops": 0,
        "has_transparency": False,
        "has_blend_modes": False,
        "has_tiling_patterns": False,
        "has_even_odd_winding": False,
        "max_stroke_width": 0.0
    }

    for d in drawings:
        # Paint Ops
        if d.get("fill") is not None: stats["total_paint_ops"] += 1
        if d.get("stroke") is not None or d.get("color") is not None: stats["total_paint_ops"] += 1
        
        # Transparency with None guards
        f_op = d.get("fill_opacity")
        s_op = d.get("stroke_opacity")
        fill_val = float(f_op) if f_op is not None else 1.0
        stroke_val = float(s_op) if s_op is not None else 1.0
        
        if fill_val < 0.999 or stroke_val < 0.999:
            stats["has_transparency"] = True
        
        # Blend Modes - string cast handles broken refs
        bm = d.get("blendmode")
        if bm is not None:
            if str(bm) not in ("Normal", "0", "None"):
                stats["has_blend_modes"] = True
            
        if d.get("even_odd") is True:
            stats["has_even_odd_winding"] = True
        
        if d.get("seqno", 0) is not None and int(d.get("seqno", 0)) < 0:
            stats["has_tiling_patterns"] = True

        for item in d.get("items", []):
            try:
                t = item[0]
                if t == "l": stats["total_points"] += 2
                elif t in ("c", "q"): 
                    stats["total_points"] += 4
                    stats["curve_segments"] += 1
                elif t == "re": 
                    stats["total_points"] += 4
                    stats["rect_segments"] += 1
                    if d.get("fill") is None and d.get("color") is None:
                        stats["clipping_paths"] += 1
            except (IndexError, TypeError):
                continue
        
        raw_w = d.get("width")
        sw = float(raw_w) if raw_w is not None else 1.0
        if sw > stats["max_stroke_width"]: stats["max_stroke_width"] = sw
    
    return stats

def get_text_metadata(page: fitz.Page) -> Dict[str, Any]:
    try:
        fonts = page.get_fonts()
        text_dict = page.get_text("dict")
    except Exception:
        return {"font_count": 0, "char_count": 0, "error": "parse_failure"}

    char_count = 0
    for block in text_dict.get("blocks", []):
        if "lines" in block:
            for line in block["lines"]:
                for span in line["spans"]:
                    txt = span.get("text")
                    if txt:
                        char_count += len(txt)

    return {
        "font_count": len(fonts),
        "char_count": char_count,
        "is_complex_font_system": any("CJK" in str(f[3]) or "Identity-" in str(f[3]) for f in fonts)
    }