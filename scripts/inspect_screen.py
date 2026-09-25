"""Print metadata for one screenshot from the first ready Android device."""

from vphone.device import AdbDeviceBackend
from vphone.device.models import DeviceState
from vphone.perception import PerceptionEngine


def main() -> None:
    backend = AdbDeviceBackend()
    ready = [item for item in backend.list_devices() if item.state is DeviceState.READY]
    if not ready:
        raise SystemExit("No authorized Android device found.")

    with backend.open(ready[0].device_id) as device:
        observation = PerceptionEngine().observe(device)

    screen = observation.screen
    print(f"Observation ID: {observation.observation_id}")
    print(f"Screen data length: {len(screen.data)} bytes")
    print(f"PNG signature: {screen.data[:8]!r}")
    print(f"Screen size: {screen.width}x{screen.height}")
    print(f"Screen MIME type: {screen.mime_type}")
    print(f"Screen SHA256: {screen.sha256}")
    print(f"Screen captured at: {screen.captured_at}")
    print(f"Screen command duration: {screen.duration_seconds}s")


if __name__ == "__main__":
    main()
