# L2 执行层技术设计

| 属性 | 内容 |
| --- | --- |
| 状态 | 已实现，开发阶段；以当前代码为准 |
| 范围 | 四类具体动作的数据模型、单次派发、结果与错误表达 |
| 对上接口 | `vphone.action` 中的 `ActionExecutor`、`Action` / `ActionResult` |
| 对下依赖 | L1 `DeviceSession` 协议；不依赖具体 ADB 实现 |
| 主要实现 | [`src/vphone/action/models.py`](../../src/vphone/action/models.py)、[`executor.py`](../../src/vphone/action/executor.py) |

## 1. 定位与设计目标

L2 将“已经确定的具体动作”转换成一次 L1 设备原语调用，并把执行结果以稳定的数据结构返回。它是决策与设备之间的**薄执行边界**，不解释页面内容，也不保证业务目标达成。

```text
L4 决定意图和下一步（未来）
  ↓
L3 可信控件树优先定位，缺失时视觉兜底（未来）
  ↓ 具体动作，例如 TapAction(Point(400, 600))
L2 校验动作 → 派发一次 → ActionResult
  ↓ DeviceSession 协议
L1 执行 ADB 输入原语 → PrimitiveResult 或 DeviceError
  ↓
Android 当前界面（效果仍需重新观测）
```

当前设计保持同步、单动作、无状态：一个 `ActionExecutor` 持有一台设备会话；每次 `execute` 只处理一个动作。并发串行化由 L1 的同进程设备锁承担，L2 不再维护第二把锁。跨进程设备协调仍不在当前系统内。

## 2. 职责与非职责

| L2 负责 | L2 不负责 |
| --- | --- |
| 建模并校验点击、滑动、按键、文本四类动作 | 从用户自然语言生成动作；识别图像或控件树元素 |
| 将单个动作派发到 `DeviceSession` 对应方法 | 判断坐标是否命中目标、页面是否稳定、是否出现弹窗 |
| 对设备运行故障返回 `ActionResult.error`，记录动作种类和耗时 | 吞掉调用方编程错误、自动重试或回滚可能已生效的输入 |
| 允许调用方设置一次动作的超时 | 动作序列、等待、条件分支、任务状态和 VLM 决策 |

L2 不主动采集截图或 XML，也不根据 `DeviceCapabilities` 自动改写动作。例如 `TextAction` 不会寻找输入框或自动点击焦点；调用前应已确认当前焦点。未来若要新增“点击匹配到的控件”等复合能力，应先明确属于 L3 定位、L4 规划还是 L2 原语，而不是让执行器隐式承担感知工作。

## 3. 公开数据契约

动作对象采用冻结 dataclass，创建时即进行结构校验；`Action` 是四种动作的联合类型。

| 动作 | 参数 | 校验 | L1 派发目标 |
| --- | --- | --- | --- |
| `TapAction` | `point: Point` | 必须是 `Point`；坐标为非负整数 | `device.tap(point)` |
| `SwipeAction` | `start: Point`、`end: Point`、`duration_ms=300` | 起终点为 `Point`，持续时间为 1–10000 ms 的整数 | `device.swipe(start, end, duration_ms=...)` |
| `KeyAction` | `key: KeyCode \| int` | 预定义键或非负整数；布尔值不算整数键码 | `device.key_event(key)` |
| `TextAction` | `text: str` | 非空、可打印字符串 | `device.input_text(text)` |

`Point` 来自 L1，表示设备屏幕像素坐标；类型与非负性校验不等于屏幕内校验。上层应依据**最近一次有效观测**的尺寸和目标边界选择坐标，并考虑页面滚动、动画与旋转造成的失效。`TextAction` 的 `repr` 隐藏文本字段，但这只降低误打印风险，不构成完整的敏感数据保护；文本仍传给 L1、ADB 及设备。

`ActionKind` 分别为 `tap`、`swipe`、`key`、`text`。`ActionResult` 字段含义如下：

| 字段 | 含义 |
| --- | --- |
| `kind` | 被执行的动作类别，不保存坐标或文本 |
| `duration_seconds` | L2 单次派发的墙上耗时；从动作和超时校验完成后开始计时，包含等待 L1 锁和设备调用 |
| `primitive` | L1 正常返回时的 `PrimitiveResult`；含原语名称及 L1 测量的耗时 |
| `error` | L1 抛出的原始 `DeviceError`；没有被转换成字符串或丢失异常类型 |
| `completed` | `error is None`；只表示 L1 正常返回，不是界面效果或任务成功判定 |

由 `ActionExecutor.execute()` 返回的结果在正常路径上具有 `primitive`、没有 `error`；在捕获到设备故障时具有 `error`、没有 `primitive`。`ActionResult` 模型本身没有强制这两个字段互斥，调用方应以执行器返回值为准，不应手工构造后依赖该约定。

## 4. 单次执行语义

执行步骤是确定性的：

1. 通过运行时类型确定 `ActionKind`；不支持的动作立即抛 `TypeError`。
2. 若显式传入 `timeout`，要求它是有限、正的数值；布尔值和无穷大不接受。非法值抛 `TypeError` / `ValueError`，且不会触碰设备。
3. 启动计时，将动作派发到对应的 L1 会话方法；每次恰好调用一个方法。L1 的文本输入可能进一步拆成多条 ADB 命令。
4. L1 正常返回时填充 `primitive`；L1 抛出 `DeviceError` 时填充 `error`。非 `DeviceError` 的编程错误不会被 L2 静默包装。

| 动作 | `timeout=None` 时继承的 L1 默认值 |
| --- | ---: |
| 点击 / 滑动 / 按键 | 5 s |
| 文本 | 10 s |

显式 `timeout` 原样传给 L1。这个值不是 L2 另起的一层“强制截止时间”；L1 的锁等待、本地解码与多步清理等阶段可能使实际墙上耗时超过数值。`ActionResult.duration_seconds` 与 `PrimitiveResult.duration_seconds` 的测量范围不同，不应直接当作相同指标比较：前者覆盖 L2 调用整体，后者取决于各 L1 原语的实现。

### 4.1 成功、失败与不确定结果

`completed=True` 表示**命令调用正常返回**，不表示按钮被点中、输入框内容正确、页面已经跳转或任务完成。例如点到了空白处，ADB 仍可能返回成功。上层若要求“已到达预期页面”，应在动作后重新采集页面并评估。

`completed=False` 同样不表示动作没有生效。ADB 超时、断线或 Unicode helper 报错时，设备可能已经收到点击、部分文本或整段文本。当前 L2 不自动重试，避免重复点击提交按钮、重复发送消息或重复填入文本。恢复策略应由 L4 根据重新观测的状态和动作风险决定；对不可逆动作尤其不能简单重放。

设备错误的处理边界是 `DeviceError`。例如：

- `DeviceOfflineError` / `DeviceUnauthorizedError`：设备状态异常，先恢复连接或授权。
- `DeviceCommandTimeoutError`：结果不确定，先重新观测；不要推断未执行。
- `InputError`：输入不满足设备侧条件或控件拒绝，检查当前焦点和能力。
- `UiTreeError` / `ScreenshotError`：通常出现在重新观测阶段，不是 L2 派发本身产生的成功判定。

更细的错误定义与 ADB 映射见 [L1 设备层设计](l1-device.md#5-错误超时与资源限制)。

## 5. 与 L3 / L4 的协作约定

项目已确定的感知原则是：“截图提供可见页面依据；可信控件树优先提供精确元素，缺失时由视觉兜底；VLM 负责语义决策”。具体来说，未来 L3 应先评估节点质量，优先将可信节点作为精确候选；节点缺失或不可信的区域由视觉检测补齐。VLM 结合任务和候选决定下一步，已有可靠边界时不必凭空估计坐标。L1/L2 **尚未实现**上述定位、融合、降级或语义决策；L2 只接收最终确定的具体动作。整体原则见 [README](../../README.md#核心感知原则)。

建议未来上层遵守以下调用顺序：

```text
观测页面（截图 / UI 树）
  → 评估观测质量、时间差与目标置信度
  → 选定一个具体动作
  → L2.execute(action)
  → 重新观测并判断效果
  → 继续、修正或安全停止
```

坐标来自过去的观测，天然可能过期；截图和树也不是原子采集。滑动、旋转、弹窗后尤其需要重新定位。只有 L4 能根据任务语义判断“是否值得再试”，L2 不知道某次点击是否具有付款、删除、发送等不可逆后果。

## 6. 使用示例

```python
from vphone.action import ActionExecutor, KeyAction, TapAction, TextAction
from vphone.device import AdbDeviceBackend, KeyCode, Point

with AdbDeviceBackend().open("your-device-id") as device:
    executor = ActionExecutor(device)

    home = executor.execute(KeyAction(KeyCode.HOME))
    if not home.completed:
        raise home.error  # 保留原始设备错误类型

    # 实际坐标应由上层从当前页面观测计算，此处仅演示调用形式。
    tap = executor.execute(TapAction(Point(400, 600)), timeout=5)
    if tap.completed:
        new_screen = device.capture_screen()
        # 上层继续分析 new_screen；tap.completed 并不保证页面已变化。

    # 仅在已确认焦点为目标输入框时执行。
    # result = executor.execute(TextAction("hello"))
```

示例没有自动选设备、等待页面或判断截图内容；这些行为应由未来上层明确实现。生产调用方还应避免把用户输入文本和完整异常直接写入未经脱敏的日志。

## 7. 验证策略与当前边界

| 验证层 | 覆盖重点 |
| --- | --- |
| 单元测试 | 四种模型的类型/边界校验；协议替身上的派发、默认与显式超时、设备错误保留、无重试 |
| 真机集成测试 | 经 L2 发送 HOME 键，再经 L1 采集 PNG；验证跨层基本链路 |
| 手工检查 | 在受控页面测试坐标和文本输入，并通过新截图/UI 树核对实际效果；自动集成测试目前不覆盖全部 UI 语义 |

```bash
uv sync --extra dev
uv run pytest -q tests/unit/action
VPHONE_DEVICE_ID=<设备序列号> uv run pytest -q tests/integration/action
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

设置 `VPHONE_DEVICE_ID` 后，集成测试会真实发送 HOME 键；未设置则按标记跳过。当前没有 L2 对点击命中率、文本最终值或业务成功率的自动化保证。需要这些指标时，应在 L3/L4 建立可复现的页面场景、效果判定与失败分类，而非把 ADB 命令返回码当成成功率。

## 8. 演进决策点

- 若未来需要动作序列、等待或条件重试，先定义幂等性、超时后的不确定状态和回滚规则，再决定放入 L2 扩展模块还是 L4 工作流。
- 若未来需要“按控件 ID 点击”，应保持定位与执行分离：由 L3 解析节点并给出目标或由新的受控 L1 原语支持，避免 L2 内嵌语义查找。
- 若引入更多设备后端，保持 `DeviceSession` 协议一致，并以同一套执行器单元测试验证行为；不要让 L2 依赖 ADB 命令细节。
- 若要暴露给 CLI / Python API / Web UI，应明确哪些动作可被远程触发、如何确认高风险操作及如何处理输入与截图的敏感数据。
