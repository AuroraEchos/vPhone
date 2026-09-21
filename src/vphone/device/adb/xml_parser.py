"""Parse UI Automator XML into backend-neutral raw nodes."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET

from vphone.device.errors import UiTreeError
from vphone.device.models import RawUiNode, Rect, UiTreeSnapshot

_BOUNDS = re.compile(r"^\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]$")
_MAX_XML_BYTES = 8 * 1024 * 1024
_MAX_NODES = 20_000
_MAX_DEPTH = 128


def parse_ui_tree(
    xml_data: bytes,
    *,
    captured_at: float,
    duration_seconds: float,
) -> UiTreeSnapshot:
    if not xml_data:
        raise UiTreeError("UI hierarchy is empty")
    if len(xml_data) > _MAX_XML_BYTES:
        raise UiTreeError(f"UI hierarchy exceeds {_MAX_XML_BYTES} bytes")
    upper = xml_data[:4096].upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise UiTreeError("UI hierarchy contains a forbidden XML declaration")
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as exc:
        raise UiTreeError(f"invalid UI hierarchy XML: {exc}") from exc
    if root.tag != "hierarchy":
        raise UiTreeError(f"unexpected UI hierarchy root: {root.tag}")

    nodes: list[RawUiNode] = []

    def visit(element: ET.Element, parent_id: str | None, node_id: str, depth: int) -> None:
        if depth > _MAX_DEPTH:
            raise UiTreeError(f"UI hierarchy exceeds {_MAX_DEPTH} levels")
        if len(nodes) >= _MAX_NODES:
            raise UiTreeError(f"UI hierarchy exceeds {_MAX_NODES} nodes")
        if element.tag != "node":
            return
        password = _bool_attr(element, "password")
        nodes.append(
            RawUiNode(
                node_id=node_id,
                parent_id=parent_id,
                package_name=element.get("package", ""),
                class_name=element.get("class", ""),
                resource_id=element.get("resource-id", ""),
                text="" if password else element.get("text", ""),
                content_description="" if password else element.get("content-desc", ""),
                bounds=_parse_bounds(element.get("bounds", "")),
                checkable=_bool_attr(element, "checkable"),
                checked=_bool_attr(element, "checked"),
                clickable=_bool_attr(element, "clickable"),
                enabled=_bool_attr(element, "enabled", default=True),
                focusable=_bool_attr(element, "focusable"),
                focused=_bool_attr(element, "focused"),
                scrollable=_bool_attr(element, "scrollable"),
                long_clickable=_bool_attr(element, "long-clickable"),
                selected=_bool_attr(element, "selected"),
                password=password,
            )
        )
        for child_index, child in enumerate(element):
            visit(child, node_id, f"{node_id}.{child_index}", depth + 1)

    for root_index, element in enumerate(root):
        visit(element, None, str(root_index), 1)

    raw_rotation = root.get("rotation")
    try:
        rotation = int(raw_rotation) if raw_rotation is not None else None
    except ValueError:
        rotation = None
    return UiTreeSnapshot(
        nodes=tuple(nodes),
        rotation=rotation,
        sha256=hashlib.sha256(xml_data).hexdigest(),
        captured_at=captured_at,
        duration_seconds=duration_seconds,
    )


def _bool_attr(element: ET.Element, name: str, *, default: bool = False) -> bool:
    value = element.get(name)
    return default if value is None else value.casefold() == "true"


def _parse_bounds(value: str) -> Rect:
    match = _BOUNDS.fullmatch(value)
    if match is None:
        raise UiTreeError(f"invalid UI node bounds: {value!r}")
    try:
        return Rect(*(int(item) for item in match.groups()))
    except ValueError as exc:
        raise UiTreeError(f"invalid UI node bounds: {value!r}") from exc
