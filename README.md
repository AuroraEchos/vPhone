# vPhone

用自然语言驱动你的 Android 手机。

项目已实现 L1 设备层和 L2 基础动作层。设备层通过官方 ADB 提供设备发现、截图、控件树和输入原语；动作层校验并执行已确定的坐标、按键和文本动作。元素匹配、视觉融合与任务决策仍属于后续层级。

## 核心感知原则

截图呈现当前可见页面，控件树提供结构化元素属性与精确边界。两者各有局限：控件树可能缺失、不完整或与当前画面不一致，因此使用前必须评估可信度；截图也需要经过视觉识别才能定位元素。

整体原则是：

> 截图提供可见页面依据；可信控件树优先提供精确元素，缺失时由视觉兜底；VLM 负责语义决策。

未来的感知层会根据当前页面的控件树质量选择不同策略：

- 控件树可信：优先利用节点文本、状态和边界定位精确候选，并用截图核对其是否符合当前可见页面。
- 控件树部分可信：保留可信节点作为锚点，由 OCR 或视觉检测补齐缺失区域；不因为树存在就盲信全部节点。
- 控件树不可用：由截图、OCR 和视觉检测定位候选，再交由 VLM 结合任务语义判断下一步。

原始 XML 不会直接交给模型。感知层会把可信控件树节点、OCR 结果和视觉检测结果转换成统一的候选元素表达，标记来源与置信度；VLM 负责理解任务和选择目标，而不是在已有可靠边界时凭空猜坐标。执行动作后需重新观察页面，确认实际效果。上述质量评估、融合、视觉兜底和语义决策尚未在 L1/L2 实现。

```text
截图 ───────────────→ 可见页面依据 ──────────────┐
                                                  ├─→ 候选元素 → VLM 语义决策 → L2 动作
控件树 → 质量评估 → 可信时优先提供精确元素 ────────┤
             └─ 缺失或质量不足时由视觉检测兜底 ───┘
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

当前实现的技术设计见 [L1 设备层](docs/architecture/l1-device.md)和 [L2 执行层](docs/architecture/l2-action.md)。上述混合感知原则将在后续 L3 设计中落地。
