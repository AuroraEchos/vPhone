# L1 设备层技术设计

| 属性 | 内容 |
| --- | --- |
| 状态 | 已实现，开发阶段；以当前代码为准 |
| 范围 | Android ADB 后端、设备会话、原始观测与输入原语 |
| 对上接口 | `vphone.device` 中的 `DeviceBackend` / `DeviceSession` 协议、数据模型和错误类型 |
| 主要实现 | [`src/vphone/device/adb/`](../../src/vphone/device/adb/) |
| 运行前提 | Python 3.11+、本机可执行 `adb`、设备已开启 USB 调试并完成授权 |

## 1. 定位与设计原则

L1 是 vPhone 与 Android 设备之间的**同步、无业务语义**边界。它回答“有哪些设备、设备现在是否可用、原始屏幕和控件树是什么、某个输入原语是否正常返回”，不回答“应该点哪里、页面是否完成任务”。

```text
L4 Planner：任务推理与下一步决策
        ↓
L3 Perception：可信控件树优先定位，缺失时视觉兜底（后续层）
        ↓
L2 Action：具体动作校验、派发、结果表达
        ↓ DeviceSession 协议
L1 Device：发现 / 会话 / 截图 / UI XML / 输入原语
        ↓
ADB 客户端 → ADB server → Android 设备
```

层间依赖只向下：L1 不导入 L2–L4，不暴露任意 ADB shell 给上层。`DeviceSession` 是后端无关的协议，当前具体实现是 `AdbDeviceBackend` / `AdbDeviceSession`；上层依赖协议，后续可替换设备后端。

项目感知原则是“截图提供可见页面依据；可信控件树优先提供精确元素，缺失时由视觉兜底；VLM 负责语义决策”。L1 只交付原始截图和控件树，不评估节点可信度，也不执行视觉检测或 VLM 决策。

设计取舍：当前开发验证主要针对单机、单设备，使用同步 API 和标准线程锁，避免在尚无并发吞吐需求时引入 `asyncio`、任务队列或远程设备服务。

## 2. 职责边界

| L1 负责 | L1 不负责 |
| --- | --- |
| 发现 ADB 设备，区分 ready、offline、unauthorized 等状态 | 自动挑选“最合适”的设备、自动授权或恢复离线设备 |
| 为指定 ready 设备创建会话，并在同一 Python 进程内串行访问同一设备 | 跨进程互斥或分布式设备租约 |
| 采集并校验 PNG 截图；采集 UI Automator XML 并转换为原始节点 | 语义元素匹配、树与图像融合、截图与树的时间对齐 |
| 执行坐标点击、滑动、按键、可打印文本输入 | 确认目标控件收到输入、等待页面稳定、动作重试或业务回滚 |
| 提供结构化错误和单次调用的超时参数 | 任务编排、页面状态机、日志脱敏策略的端到端保证 |

控件树可能缺失、过期或不完整。L3 应先判断哪些节点可信：可信节点优先用于精确定位；缺失或质量不足的部分由视觉补齐。L1 不做这项判断。

## 3. 公开契约

接口定义在 [`protocol.py`](../../src/vphone/device/protocol.py)，数据模型在 [`models.py`](../../src/vphone/device/models.py)，错误类型在 [`errors.py`](../../src/vphone/device/errors.py)。

| 接口 | 默认超时 | 返回值 / 关键语义 |
| --- | ---: | --- |
| `DeviceBackend.list_devices()` | 5 s | `list[DeviceDescriptor]`；包括未授权/离线设备，不负责选择 |
| `DeviceBackend.open(device_id)` | 5 s | 校验并打开指定 ready 设备；不会隐式选择第一台 |
| `DeviceSession.health_check()` | 5 s | 当前 `DeviceHealth`；与打开时的 `descriptor` 快照区分 |
| `capture_screen()` | 10 s | PNG `ScreenFrame`：字节、尺寸、SHA-256、采集时间、耗时 |
| `capture_ui_tree()` | 10 s | `UiTreeSnapshot`：原始节点、旋转、SHA-256、采集时间、耗时 |
| `tap(Point)` | 5 s | `PrimitiveResult`；非负整数像素坐标 |
| `swipe(start, end, duration_ms=300)` | 5 s | `PrimitiveResult`；持续时间必须在 1–10000 ms |
| `key_event(KeyCode \| int)` | 5 s | `PrimitiveResult`；预定义键或非负整数键码 |
| `input_text(text)` | 10 s | `PrimitiveResult`；非空、可打印文本，输入到当前焦点 |
| `close()` | — | 关闭会话；之后的设备操作抛出 `DeviceClosedError` |

`Point`、`Rect` 等 L1 数据模型是冻结的 dataclass；类型和基本数值范围会校验，但 `Point` 不检查屏幕边界。`DeviceCapabilities` 表示后端宣称支持的原语，不保证当前应用、控件或 Android 版本一定接受该操作。例如 `unicode_text=True` 不代表任意输入框均支持无障碍 `ACTION_SET_TEXT`。

`DeviceDescriptor` 保存发现时的设备信息，不会自动刷新；需要实时连通性时调用 `health_check()`。`ScreenFrame.captured_at` 与 `UiTreeSnapshot.captured_at` 是墙上时钟时间戳，主要用于关联和排查，不构成原子快照或强一致性证明。节点 `node_id` 是 XML 遍历路径，只在所属快照内有效，不能跨页面或跨采集持久引用。

## 4. 实现与调用链

### 4.1 发现、打开和会话

1. [`AdbRunner`](../../src/vphone/device/adb/runner.py) 定位 `adb`，以参数列表启动子进程，统一收集输出和映射 ADB 错误；不调用本机 shell。
2. 发现模块执行 `adb devices -l`，解析序列号、状态及设备元数据。USB/模拟器/网络分类基于序列号形态，是便于展示的推断。
3. `open(device_id)` 去除首尾空白、精确匹配设备 ID，仅在状态为 ready 时创建会话；未找到、未授权、离线分别抛对应错误。
4. 会话的 `descriptor` 与 `capabilities` 暴露给上层。上下文管理器退出或显式 `close()` 后不再可用；关闭不关机、不断开 ADB。

所有 `AdbDeviceSession` 通过设备 ID 共享进程内 `threading.RLock`。同一进程对同一设备的截屏、树采集和输入不会交错；不同设备可并行。该锁不跨 Python 进程，外部 `adb` 命令也不受它约束。锁等待时间未计入传给 ADB 的 `timeout`，因此调用的总墙上时间可能超过该值。

### 4.2 原始观测

| 观测 | ADB 路径 | 验证与输出 |
| --- | --- | --- |
| 截图 | `exec-out screencap -p` | 非空、Pillow 校验 PNG 完整性与尺寸；返回原始 PNG 字节及 SHA-256 |
| 控件树 | `shell uiautomator dump --compressed <随机临时路径>`，再 `exec-out cat <路径>` | 解析 `hierarchy` XML；输出节点的原始属性、边界、父子关系和旋转 |

控件树临时文件使用随机路径，避免不同进程因文件名相同而相互覆盖；读取后尽力删除。若设备离线、命令超时或总预算耗尽，清理可能无法完成，需在设备运维中留意 `/data/local/tmp/vphone-window-*.xml`。随机文件名不等于跨进程 UI Automator 互斥。

XML 解析器拒绝超过 8 MiB 的输入、DOCTYPE/ENTITY 声明、超过 20,000 个节点或 128 层深度，并将格式错误归类为 `UiTreeError`。密码节点的 `text` 与 `content_description` 被清空；其他节点属性仍可能包含敏感信息。解析只做结构转换，不做 OCR、语义推断或“元素是否可点”的综合判断。

截图和 XML 是**顺序采集的两个独立样本**。页面动画、弹窗或旋转可能使两者不一致。L3 应检查数据质量、时间差和页面变化：可信节点用于精确候选，缺失或不可信时由视觉检测兜底，必要时重新采集。

### 4.3 输入原语

| 原语 | 实现 | 主要约束 |
| --- | --- | --- |
| 点击 / 滑动 / 按键 | `adb shell input tap/swipe/keyevent` | 坐标是屏幕像素；返回仅说明命令正常结束 |
| ASCII 文本 | `adb shell input text` | 空格转换为 Android `%s`；对远端 shell 参数引用，字面 `%s` 拆成多次命令避免误转义 |
| 非 ASCII 文本 | 推送随项目携带的 UI Automator helper，执行后尽力删除 | Android API 21+、当前焦点可编辑节点支持 `ACTION_SET_TEXT` |

文本仅接受非空且 `str.isprintable()` 为真的字符串；换行、制表符等控制字符不属于当前能力。ASCII 路径使用远端 shell，因此对用户文本做 `shlex.quote`；`AdbRunner` 不调用本机 shell 与远端引用是两个不同的安全边界。包含字面 `%s` 的 ASCII 文本可能拆为多个命令，途中失败时可能只输入前缀。

Unicode helper 将 UTF-8 文本以 Base64 参数传递，读取**当前焦点节点的现有文本与选区**，通常尝试在选区插入或替换；密码节点或无法获得有效选区时可能替换整段文本。它调用 `ACTION_SET_TEXT`，随后尽力设置光标，不能保证所有应用接受或光标更新成功。它不安装应用、不使用剪贴板，也不更改用户输入法，但会短暂上传 JAR；超时或断线时残留临时 JAR 的风险与 XML 相同。

两条文本路径都不是事务：失败或超时可能已经产生部分输入。L1 因此不自动重试。调用者也不应把包含密码或令牌的原始文本、命令参数、截图、XML 或异常消息直接写入可共享日志。

## 5. 错误、超时与资源限制

所有设备运行故障继承 `DeviceError`，方便上层统一捕获，同时保留可区分的子类：

| 类别 | 典型错误 | 上层处理原则 |
| --- | --- | --- |
| 环境 / 选择 | `AdbNotFoundError`、`DeviceNotFoundError`、`DeviceSelectionError` | 检查 ADB 安装、设备 ID 与连接配置 |
| 设备状态 | `DeviceUnauthorizedError`、`DeviceOfflineError`、`DeviceClosedError` | 请求用户授权、重连或重新打开会话；不要盲目重放输入 |
| 命令 | `DeviceCommandError`、`DeviceCommandTimeoutError`、`DeviceProtocolError` | 记录错误类别并重新观测设备状态；超时不能推断“未执行” |
| 观测 / 输入 | `ScreenshotError`、`UiTreeError`、`InputError`、`UnsupportedCapabilityError` | 区分损坏数据、树不可用和控件拒绝输入；由上层决定降级 |

调用方传入的非法类型或数值也可能直接抛 `TypeError` / `ValueError`，这类编程错误不应当作设备故障重试。`UnsupportedCapabilityError` 已定义，当前 ADB 会话尚未进行逐操作能力探测，因此不能依赖它覆盖不支持的控件情形。截图的 ADB 失败可能仍以命令类错误抛出；只有无效 PNG 等数据校验错误才是 `ScreenshotError`。UI 树采集会将相关设备错误包装为 `UiTreeError`，原始原因可从异常链查看。

`AdbRunner` 用 `subprocess.run(timeout=...)` 限制**单条 ADB 命令**。控件树采集和文本输入为多步操作，使用单调时钟把剩余预算传给后续命令；清理为尽力而为。超时不是严格的端到端执行截止时间：获取进程锁、截图解码与 XML 解析等本地阶段不完全受该参数约束。ADB stdout/stderr 在子进程结束后检查单流 32 MiB 上限；这不是流式内存硬限制。XML 另有解析前的 8 MiB 限制。

## 6. 使用与验证

```python
from vphone.device import AdbDeviceBackend, Point

backend = AdbDeviceBackend()
for item in backend.list_devices():
    print(item.device_id, item.state)

with backend.open("your-device-id") as device:
    health = device.health_check()
    if health.ready:
        frame = device.capture_screen()
        tree = device.capture_ui_tree(timeout=15)
        print(frame.width, frame.height, len(tree.nodes))
        # 坐标必须由上层依据当前页面确定；下面只是 API 示例。
        # device.tap(Point(400, 600))
```

开发机准备：执行 `uv sync --extra dev`，确认 `adb devices -l` 中目标设备为 `device`。验证分层如下：

```bash
uv run pytest -q tests/unit/device
VPHONE_DEVICE_ID=<设备序列号> uv run pytest -q tests/integration/device
uv run ruff check .
uv run ruff format --check .
```

普通真机集成测试验证授权状态、PNG、XML 和解析一致性。Unicode 输入测试还需要 `VPHONE_INPUT_TEST_TEXT`，并要求事先在设备上聚焦一个**空的、可编辑的**输入框；否则测试按设计跳过。该测试会实际修改手机输入框内容，不应在未知页面上运行。

## 7. 当前限制与后续演进

- 控件树质量受 Android 应用无障碍实现影响；无节点或错误节点不等于页面不可操作。L3 负责落实“可信控件树优先、视觉兜底”的质量评估与降级策略。
- 没有截图与 XML 的原子快照、跨进程设备租约或会话重连机制；多进程/多机共享设备前需要重新设计协调方式。
- 输入只支持坐标、按键、可打印文本；没有直接控件点击、长按、多点触控或剪贴板方案。
- 设备能力目前是静态声明，不是逐应用、逐控件的探测结果。
- 若未来要对延迟、内存或隐私给出硬保证，应增加流式输出限制、端到端截止时间、脱敏观测与设备资源回收机制，而不是把当前实现描述为已具备这些保证。
