# vPhone

用自然语言驱动 Android 手机。项目处于 `dev` 阶段，尚未形成端到端自然语言 Demo。

## 当前架构

vPhone 采用**纯视觉感知**：截图是页面状态的唯一观测输入。L3 交付当前完整截图；未来 L4 的多模态模型直接结合截图和用户任务理解页面、选择动作。项目不采集 App 控件树，也不运行 OCR。

```text
L5 接口层       CLI / Python API / 可选 Web UI（后续）
L4 决策层       多模态模型理解任务与截图，选择具体动作（后续）
L3 感知层       当前截图观测（当前首版）
L2 执行层       校验并派发具体点击、滑动、按键、文本动作
L1 设备层       ADB 设备发现、截图和输入原语
```

运行链路是：采集截图 → 由上层判断下一步 → L2 执行动作 → 重新截图确认效果。当前尚无 L4，因此目标选择与结果判断仍由开发者或测试代码完成。截图本身不提供可点击性或元素语义；未来模型需要基于当前截图判断，也不能复用旧坐标。

## 开发环境

需要 Python 3.11+、uv、Android Platform Tools，以及已授权的 Android 设备。

```bash
uv sync --extra dev
uv run --extra dev pytest -q
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
```

## 真机观察示例

```python
from vphone.device import AdbDeviceBackend
from vphone.perception import PerceptionEngine

backend = AdbDeviceBackend()
devices = backend.list_devices()

with backend.open(devices[0].device_id) as device:
    observation = PerceptionEngine().observe(device)

print(observation.screen.width, observation.screen.height)
print(observation.screen.sha256, observation.observation_id)
```

示例仅用于本地调试。截图可能包含个人信息，不要直接写入共享日志或提交到仓库。真实设备只读集成测试需显式设置设备 ID：

```bash
VPHONE_DEVICE_ID=<设备序列号> uv run --extra dev pytest -q -m android
```

技术设计见 [L1 设备层](docs/architecture/l1-device.md)、[L2 执行层](docs/architecture/l2-action.md)和 [L3 感知层](docs/architecture/l3-perception.md)；开发流程见 [开发规范](DEVELOPMENT.md)。
