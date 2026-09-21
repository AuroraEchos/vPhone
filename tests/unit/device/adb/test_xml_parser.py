from __future__ import annotations

import pytest

from vphone.device.adb.xml_parser import parse_ui_tree
from vphone.device.errors import UiTreeError
from vphone.device.models import Rect


def test_parse_ui_tree_preserves_structure_and_redacts_passwords() -> None:
    snapshot = parse_ui_tree(
        b"""<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="1">
  <node index="0" text="Root" resource-id="root" class="android.view.View"
        package="example" content-desc="" checkable="false" checked="false"
        clickable="false" enabled="true" focusable="false" focused="false"
        scrollable="false" long-clickable="false" password="false" selected="false"
        bounds="[0,0][1080,2400]">
    <node index="0" text="secret" resource-id="password" class="android.widget.EditText"
          package="example" content-desc="account password" checkable="false"
          checked="false" clickable="true" enabled="true" focusable="true"
          focused="true" scrollable="false" long-clickable="true" password="true"
          selected="false" bounds="[20,30][500,100]" />
  </node>
</hierarchy>""",
        captured_at=1.0,
        duration_seconds=0.2,
    )

    assert snapshot.rotation == 1
    assert len(snapshot.nodes) == 2
    assert snapshot.nodes[0].node_id == "0"
    assert snapshot.nodes[1].parent_id == "0"
    assert snapshot.nodes[1].bounds == Rect(20, 30, 500, 100)
    assert snapshot.nodes[1].password is True
    assert snapshot.nodes[1].text == ""
    assert snapshot.nodes[1].content_description == ""


def test_parse_ui_tree_rejects_malformed_xml() -> None:
    with pytest.raises(UiTreeError, match="invalid UI hierarchy XML"):
        parse_ui_tree(b"<hierarchy>", captured_at=1.0, duration_seconds=0.1)


def test_parse_ui_tree_rejects_invalid_bounds() -> None:
    xml = b'<hierarchy><node bounds="not-bounds" /></hierarchy>'

    with pytest.raises(UiTreeError, match="invalid UI node bounds"):
        parse_ui_tree(xml, captured_at=1.0, duration_seconds=0.1)


def test_parse_ui_tree_rejects_doctype() -> None:
    xml = b'<!DOCTYPE hierarchy><hierarchy rotation="0" />'

    with pytest.raises(UiTreeError, match="forbidden"):
        parse_ui_tree(xml, captured_at=1.0, duration_seconds=0.1)


def test_parse_ui_tree_rejects_doctype_after_initial_scan_window() -> None:
    xml = b" " * 4096 + b'<!DOCTYPE hierarchy><hierarchy rotation="0" />'

    with pytest.raises(UiTreeError, match="forbidden"):
        parse_ui_tree(xml, captured_at=1.0, duration_seconds=0.1)
