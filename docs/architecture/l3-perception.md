# L3 纯视觉感知层技术设计

| 属性 | 内容 |
| --- | --- |
| 状态 | 截图观测首版已实现；L4 已接入可配置的多模态决策闭环 |
| 页面依据 | L1 `ScreenFrame` 截图 |
| 对上接口 | `PerceptionEngine.observe()`、`PageObservation` |
| 对下依赖 | L1 `DeviceSession.capture_screen()` |
| 非职责 | 提取控件树、OCR、元素定位、选择或执行动作 |

## 1. 设计原则

> 截图是唯一页面观测输入；多模态模型结合用户任务和当前截图作语义决策。

真实 App 的控件树可能缺失或不可靠，而现代多模态模型可以直接处理页面截图。L3 因此只建立一条清晰的观测路径：从 L1 获取当前完整截图，形成不可变的页面观测，交给 L4。它不预先提取文字、图标、控件属性或点击坐标，也不读取 App 对外暴露的元数据。

```text
L1 截图 → L3 PageObservation → L4 多模态决策
                                      ↓ 具体动作
                                    L2 执行
                                      ↓
                            再次截图并评估实际效果
```

当前代码已有 L4 受限闭环，可基于截图提出一个动作、执行后重新观测。其完成声明不等于独立的业务成功证明，首个固定真机任务及限制见 [L4 决策层](l4-planner.md)。

## 2. 数据契约

`PerceptionEngine.observe(device, screen_timeout=10.0)` 调用一次 L1 `capture_screen()`，返回冻结的 `PageObservation`。此对象只有两个字段：

| 字段 | 语义 |
| --- | --- |
| `observation_id` | 本次观测生成的随机标识，用于区分前后两次观测；不代表截图内容不同 |
| `screen` | 完整 `ScreenFrame`，包含 PNG 字节、尺寸、SHA-256、采集时间与耗时 |

`ScreenFrame.sha256` 标识原始截图字节；相同哈希不证明 App 状态完全相同，不同哈希也可能只是时钟或动画变化。`captured_at` 表示 L1 截图的墙上时钟时间；观测一旦完成，画面仍可能立即变化。L4 在执行任何动作前应考虑观测的新鲜度、风险和是否需要重新截图。`observation_id` 不可用作跨页面的目标定位符。

该契约不含 OCR 文本、元素边界、可点击性、控件角色或树状态。未来若有明确证据表明额外视觉预处理能改善某类任务，应单独论证和验收，而不是让 L3 默认增加一条推理路径。

## 3. 失败语义

L1 截图采集抛 `DeviceError` 时，L3 抛 `PerceptionError("screenshot capture failed")`，保留原始异常链。没有截图，就不生成“当前页面”的观测，更不会复用旧截图或猜测 UI 状态。非法调用或模型构造错误不静默包装成设备故障。

L3 不派发动作，也不根据截图内容判断任务成功。L2 的动作结果仅说明设备原语调用情况；点击、滑动、输入后应重新调用 `observe()`，由 L4 基于新页面判断实际效果。对于付款、删除或发送等不可逆操作，决策和确认策略属于 L4；当前首版没有独立可靠的风险识别器。

## 4. 实现与验证

| 文件 | 职责 |
| --- | --- |
| [`engine.py`](../../src/vphone/perception/engine.py) | 截图调用与错误边界 |
| [`models.py`](../../src/vphone/perception/models.py) | 不可变页面观测契约 |
| [`errors.py`](../../src/vphone/perception/errors.py) | 感知层错误类型 |

```python
from vphone.device import AdbDeviceBackend
from vphone.perception import PerceptionEngine

with AdbDeviceBackend().open("<设备序列号>") as device:
    observation = PerceptionEngine().observe(device)

print(observation.observation_id, observation.screen.width, observation.screen.height)
```

验收场景：一次调用只采集一张当前截图；不同调用得到独立观测 ID；截图失败时明确报错且没有观测对象；真机运行中不发出 UI 树采集命令或其他页面提取请求。

```bash
uv sync --extra dev
uv run --extra dev pytest -q
VPHONE_DEVICE_ID=<设备序列号> uv run --extra dev pytest -q -m android
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
```

真机测试只读，但截图可能包含通知、账号、密码等敏感信息。当前实现不自动模糊、脱敏或持久化截图；调用方也不应把原始截图写入共享日志。生产化前需确定截图访问控制、保留期限及发送给模型服务的隐私边界。

## 5. 后续工作

- 扩展可复现的端到端任务集，评估 L4 在不同 App 和弹窗场景的实际命中率。
- 建立可复现的真机任务集，测量截图理解、坐标命中、动作后验证和失败恢复，而不只看 ADB 命令是否正常返回。
- 面向动画、弹窗、滚动与屏幕旋转，定义观测新鲜度和重新截图策略。
