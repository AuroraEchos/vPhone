"""ADB device discovery and output parsing."""

from __future__ import annotations

from vphone.device.adb.runner import AdbRunner
from vphone.device.models import ConnectionType, DeviceDescriptor, DeviceState


def list_devices(runner: AdbRunner, *, timeout: float = 5.0) -> list[DeviceDescriptor]:
    """Run ADB device discovery and parse its output.

    Args:
        runner: Subprocess boundary used to invoke ADB.
        timeout: Maximum command duration in seconds.

    Returns:
        Descriptors for devices reported by ADB.
    """
    result = runner.run(("devices", "-l"), timeout=timeout)
    return parse_devices_output(result.stdout.decode("utf-8", errors="replace"))


def parse_devices_output(output: str) -> list[DeviceDescriptor]:
    """Parse ``adb devices -l`` text without discarding non-ready devices.

    Args:
        output: Raw decoded ADB listing.

    Returns:
        Device descriptors in listing order.
    """
    devices: list[DeviceDescriptor] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("List of devices", "*")):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        device_id, raw_state = parts[0], parts[1]
        details = {
            key: value for item in parts[2:] if ":" in item for key, value in (item.split(":", 1),)
        }
        devices.append(
            DeviceDescriptor(
                device_id=device_id,
                state=_parse_state(raw_state),
                connection_type=_connection_type(device_id),
                product=details.get("product"),
                model=(details.get("model") or "").replace("_", " ") or None,
                device=details.get("device"),
                transport_id=details.get("transport_id"),
            )
        )
    return devices


def _parse_state(value: str) -> DeviceState:
    """Map an ADB state token to a known state or ``UNKNOWN``."""
    try:
        return DeviceState(value)
    except ValueError:
        return DeviceState.UNKNOWN


def _connection_type(device_id: str) -> ConnectionType:
    """Infer the connection class from the ADB serial format."""
    if device_id.startswith("emulator-"):
        return ConnectionType.EMULATOR
    if ":" in device_id:
        return ConnectionType.NETWORK
    if device_id:
        return ConnectionType.USB
    return ConnectionType.UNKNOWN
