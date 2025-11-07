from __future__ import annotations
import fitz
from typing import Any, List, Tuple


def open_document(path: str) -> "fitz.Document":
    return fitz.open(path)


def get_page_count(doc: "fitz.Document") -> int:
    return doc.page_count


def load_page(doc: "fitz.Document", index: int) -> "fitz.Page":
    return doc.load_page(index)


def get_page_size(page: "fitz.Page") -> Tuple[float, float]:
    rect = page.rect
    return rect.width, rect.height


def get_page_images(page: "fitz.Page") -> List[tuple]:
    return page.get_images(full=True)


def extract_image(doc: "fitz.Document", xref: int) -> dict:
    return doc.extract_image(xref)


def get_page_drawings(page: "fitz.Page") -> list:
    return page.get_drawings()
