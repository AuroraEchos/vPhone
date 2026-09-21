from vphone.device.adb.discovery import parse_devices_output
from vphone.device.models import ConnectionType, DeviceState


def test_parse_devices_output() -> None:
    devices = parse_devices_output(
        """List of devices attached
10AG262J1H003X1 device product:husky model:Pixel_8_Pro device:husky transport_id:1
emulator-5554 offline transport_id:2
192.168.1.2:5555 unauthorized transport_id:3
"""
    )

    assert len(devices) == 3
    assert devices[0].device_id == "10AG262J1H003X1"
    assert devices[0].state is DeviceState.READY
    assert devices[0].connection_type is ConnectionType.USB
    assert devices[0].model == "Pixel 8 Pro"
    assert devices[1].connection_type is ConnectionType.EMULATOR
    assert devices[1].state is DeviceState.OFFLINE
    assert devices[2].connection_type is ConnectionType.NETWORK
    assert devices[2].state is DeviceState.UNAUTHORIZED


def test_parse_devices_output_ignores_daemon_noise() -> None:
    output = """* daemon not running; starting now at tcp:5037
* daemon started successfully
List of devices attached

"""

    assert parse_devices_output(output) == []
