from __future__ import annotations

import hashlib
import os
import time
import uuid
import xml.etree.ElementTree as ET

import pytest

from vphone.device import AdbDeviceBackend
from vphone.device.adb.runner import AdbRunner
from vphone.device.adb.xml_parser import parse_ui_tree

DEVICE_ID = os.getenv("VPHONE_DEVICE_ID")
INPUT_TEST_TEXT = os.getenv("VPHONE_INPUT_TEST_TEXT")


@pytest.mark.android
@pytest.mark.skipif(not DEVICE_ID, reason="VPHONE_DEVICE_ID is not configured")
def test_authorized_device_supports_read_only_observation() -> None:
    backend = AdbDeviceBackend()

    with backend.open(DEVICE_ID) as device:
        health = device.health_check(timeout=5)
        screen = device.capture_screen(timeout=10)
        tree = device.capture_ui_tree(timeout=15)

    assert health.ready is True
    assert screen.width > 0
    assert screen.height > 0
    assert len(screen.sha256) == 64
    assert tree.source == "uiautomator"
    assert len(tree.sha256) == 64


@pytest.mark.android
@pytest.mark.skipif(not DEVICE_ID, reason="VPHONE_DEVICE_ID is not configured")
def test_real_ui_xml_parser_preserves_nodes_and_attributes() -> None:
    runner = AdbRunner()
    remote_path = f"/data/local/tmp/vphone-parser-test-{uuid.uuid4().hex}.xml"
    started = time.monotonic()
    try:
        runner.run(
            ("shell", "uiautomator", "dump", "--compressed", remote_path),
            serial=DEVICE_ID,
            timeout=15,
        )
        result = runner.run(("exec-out", "cat", remote_path), serial=DEVICE_ID, timeout=5)
    finally:
        runner.run(
            ("shell", "rm", "-f", remote_path),
            serial=DEVICE_ID,
            timeout=2,
            check=False,
        )

    xml_data = result.stdout
    snapshot = parse_ui_tree(
        xml_data,
        captured_at=time.time(),
        duration_seconds=time.monotonic() - started,
    )
    root = ET.fromstring(xml_data)
    raw_nodes = list(root.iter("node"))
    expected_identity: list[tuple[str, str | None]] = []

    def record_identity(element: ET.Element, parent_id: str | None, node_id: str) -> None:
        if element.tag != "node":
            return
        expected_identity.append((node_id, parent_id))
        for child_index, child in enumerate(element):
            record_identity(child, node_id, f"{node_id}.{child_index}")

    for root_index, element in enumerate(root):
        record_identity(element, None, str(root_index))

    assert len(snapshot.nodes) == len(raw_nodes)
    assert [(node.node_id, node.parent_id) for node in snapshot.nodes] == expected_identity
    assert snapshot.sha256 == hashlib.sha256(xml_data).hexdigest()
    assert snapshot.rotation == int(root.get("rotation"))

    boolean_fields = {
        "checkable": "checkable",
        "checked": "checked",
        "clickable": "clickable",
        "enabled": "enabled",
        "focusable": "focusable",
        "focused": "focused",
        "scrollable": "scrollable",
        "long_clickable": "long-clickable",
        "selected": "selected",
        "password": "password",
    }
    for raw, parsed in zip(raw_nodes, snapshot.nodes, strict=True):
        assert parsed.package_name == raw.get("package", "")
        assert parsed.class_name == raw.get("class", "")
        assert parsed.resource_id == raw.get("resource-id", "")
        assert (
            f"[{parsed.bounds.left},{parsed.bounds.top}]"
            f"[{parsed.bounds.right},{parsed.bounds.bottom}]" == raw.get("bounds")
        )
        for field_name, attribute_name in boolean_fields.items():
            default = field_name == "enabled"
            raw_value = raw.get(attribute_name)
            expected = default if raw_value is None else raw_value.casefold() == "true"
            assert getattr(parsed, field_name) is expected
        if parsed.password:
            assert parsed.text == ""
            assert parsed.content_description == ""
        else:
            assert parsed.text == raw.get("text", "")
            assert parsed.content_description == raw.get("content-desc", "")


@pytest.mark.android
@pytest.mark.skipif(
    not DEVICE_ID or not INPUT_TEST_TEXT,
    reason="VPHONE_DEVICE_ID and VPHONE_INPUT_TEST_TEXT are not configured",
)
def test_authorized_device_inputs_unicode_into_focused_field() -> None:
    backend = AdbDeviceBackend()

    with backend.open(DEVICE_ID) as device:
        result = device.input_text(INPUT_TEST_TEXT, timeout=15)
        tree = device.capture_ui_tree(timeout=15)

    assert result.operation == "input_text"
    assert any(node.focused and node.text == INPUT_TEST_TEXT for node in tree.nodes)
