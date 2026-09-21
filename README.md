# vPhone

用自然语言驱动你的 Android 手机。

当前项目正在从 L1 设备层开始开发。设备层通过官方 ADB 提供设备发现、截图、控件树和基础输入能力，不包含元素匹配、视觉融合或任务决策。

## 开发环境

需要 Python 3.11+、uv 和 Android Platform Tools。

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```

## 设备层示例

```python
from vphone.device import AdbDeviceBackend

backend = AdbDeviceBackend()
devices = backend.list_devices()

with backend.open(devices[0].device_id) as device:
    health = device.health_check()
    screen = device.capture_screen()
    tree = device.capture_ui_tree()

    print(health)
    print(screen.width, screen.height, screen.sha256)
    print(len(tree.nodes))
```

连接真机后，可以显式运行只读集成测试：

```bash
VPHONE_DEVICE_ID=your-device-id uv run pytest -m android
```
