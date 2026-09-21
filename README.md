# vPhone

用自然语言驱动你的 Android 手机。

当前项目正在从 L1 设备层开始开发。设备层通过官方 ADB 提供设备发现、截图、控件树和基础输入能力，不包含元素匹配、视觉融合或任务决策。

## 核心感知原则

vPhone 始终以截图作为完整页面的事实来源，控件树作为可选的结构化增强信息。系统不能假设所有 Android 应用都能提供完整控件树；当控件树缺失或质量不足时，任务执行必须能够退化为纯视觉感知，而不能因此中断。

整体原则是：

> 视觉兜底，XML 加速；视觉为主，结构为辅。

未来的感知层会根据当前页面的控件树质量选择不同策略：

- 控件树完整：向模型提供截图和经过过滤、脱敏、压缩的结构化节点，利用节点文本、状态和精确边界提高定位准确率。
- 控件树部分可用：以截图、OCR 和视觉识别为主，将输入框、导航栏等有效节点作为辅助锚点。
- 控件树不可用：忽略空节点或无效节点，只依赖截图、OCR 和视觉模型识别界面，并通过坐标执行动作。

原始 XML 不会直接交给模型。感知层会把控件树节点、OCR 结果和视觉检测结果转换成统一的元素表达，并标记元素来源与置信度。L1 只负责忠实提供原始截图和原始控件树；控件树质量评估、视觉识别与信息融合属于后续感知层。

```text
截图 ───────────────────────────────┐
                                    ├─→ 统一页面观察 → 模型决策 → 坐标动作
控件树 → 质量评估 → 过滤/融合 ─────┘
             └─ 不可用时跳过
```

## 开发环境

需要 Python 3.11+、uv、Android Platform Tools 和 Android 5.0+ 设备。

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

    # 当前输入框获得焦点后，可直接输入中文等 Unicode 文本。
    device.input_text("你好，vPhone")

    print(health)
    print(screen.width, screen.height, screen.sha256)
    print(len(tree.nodes))
```

连接真机后，可以显式运行只读集成测试：

```bash
VPHONE_DEVICE_ID=your-device-id uv run pytest -m android
```

若已将焦点放在一个可编辑文本框中，可额外验证输入能力：

```bash
VPHONE_DEVICE_ID=your-device-id \
VPHONE_INPUT_TEST_TEXT='真机中文测试' \
uv run pytest tests/integration/device/test_adb_device.py
```
