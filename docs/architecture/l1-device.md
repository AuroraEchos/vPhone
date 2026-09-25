# L1 设备层技术设计

| 属性 | 内容 |
| --- | --- |
| 状态 | 已实现，开发阶段；以当前代码为准 |
| 范围 | Android ADB 后端、设备会话、PNG 截图和输入原语 |
| 对上接口 | `vphone.device` 中的 `DeviceBackend` / `DeviceSession`、数据模型和错误类型 |
| 主要实现 | [`src/vphone/device/adb/`](../../src/vphone/device/adb/) |
| 运行前提 | Python 3.11+、本机 `adb`、设备已开启 USB 调试并授权 |

## 1. 定位与边界

L1 是 vPhone 与 Android 之间的**同步、无业务语义**边界。它回答“设备是否可用、当前截图是什么、某个输入原语是否正常返回”，不回答“页面表示什么、应该点哪里、动作是否完成任务”。项目使用纯视觉感知，L1 不采集 App 控件树或 UI XML。

```text
L4 Planner：任务与截图的多模态决策（后续）
        ↓
L3 Perception：当前截图观测
        ↓
L2 Action：具体动作校验、派发与结果表达
        ↓ DeviceSession 协议
L1 Device：设备发现 / 会话 / 截图 / 输入原语
        ↓
ADB 客户端 → ADB server → Android 设备
```

层间依赖只向下。L1 不导入 L2–L4，也不向上层暴露任意 shell。`DeviceSession` 是后端无关协议，当前实现为 `AdbDeviceBackend` / `AdbDeviceSession`。开发验证以单机、单设备为主，使用同步 API 和进程内锁，不引入 `asyncio` 或设备调度服务。

## 2. 职责

| L1 负责 | L1 不负责 |
| --- | --- |
| 发现设备，区分 ready / offline / unauthorized 等状态 | 自动选择设备、授权或恢复离线设备 |
| 为指定 ready 设备创建会话，并在同进程内串行访问同一设备 | 跨进程设备租约、远程设备服务 |
| 采集并校验 PNG 截图，提供原始字节、尺寸、哈希和时间 | 页面语义理解、目标定位、页面稳定性判断 |
| 执行坐标点击、滑动、按键、可打印文本输入 | 判断点击是否命中、页面是否跳转、任务是否完成 |
| 报告结构化设备错误与原语调用结果 | 自动重试可能已生效的输入或业务回滚 |

## 3. 公开契约

接口定义在 [`protocol.py`](../../src/vphone/device/protocol.py)，模型在 [`models.py`](../../src/vphone/device/models.py)，错误在 [`errors.py`](../../src/vphone/device/errors.py)。

| 接口 | 默认超时 | 返回值 / 关键语义 |
| --- | ---: | --- |
| `DeviceBackend.list_devices()` | 5 s | `list[DeviceDescriptor]`；包含未授权和离线设备 |
| `DeviceBackend.open(device_id)` | 5 s | 校验并打开指定 ready 设备，不隐式选择第一台 |
| `DeviceSession.health_check()` | 5 s | 当前 `DeviceHealth`，区别于打开时的描述快照 |
| `capture_screen()` | 10 s | PNG `ScreenFrame`：字节、尺寸、SHA-256、采集时间、耗时 |
| `tap(Point)` | 5 s | 坐标点击；返回 `PrimitiveResult` |
| `swipe(start, end, duration_ms=300)` | 5 s | 坐标滑动；时长 1–10000 ms |
| `key_event(KeyCode \| int)` | 5 s | 预定义键或非负整数键码 |
| `input_text(text)` | 10 s | 非空、可打印文本，输入到当前焦点 |
| `close()` | — | 关闭会话，不关机、不断开 ADB |

`Point` 与 `Rect` 是像素坐标模型；`Point` 校验非负整数，但不保证落在当前屏幕内。`ScreenFrame.captured_at` 是墙上时钟时间戳，`sha256` 用于标识截图字节，不证明页面处于稳定状态。`DeviceCapabilities` 是静态原语声明，不保证某个 App 或输入框接受所有操作。控件树相关模型、能力位及采集接口已从公开契约移除。

## 4. 实现调用链

### 4.1 设备发现与会话

1. [`AdbRunner`](../../src/vphone/device/adb/runner.py) 定位 `adb`，用参数列表启动子进程，统一处理输出和错误；不调用本机 shell。
2. 发现模块执行 `adb devices -l`，解析序列号、状态与设备元数据。USB / 模拟器 / 网络类型基于序列号形态推断。
3. `open(device_id)` 去除首尾空白、精确匹配设备 ID，仅在状态 ready 时创建会话；未找到、未授权、离线分别抛对应错误。
4. 会话关闭后所有设备操作抛 `DeviceClosedError`。同设备会话共享进程内 `threading.RLock`，使截图和输入不在同进程交错；外部 ADB 和其他进程不受此锁约束。

### 4.2 截图

截图使用 `adb exec-out screencap -p`，校验非空及 PNG 完整性和尺寸，再返回原始 PNG 字节、尺寸、SHA-256、采集时间与耗时。它是 L3 的唯一页面观测来源。截图可能包含通知、账号、密码或其他个人信息；目前没有自动脱敏，不能直接持久化到共享日志。

L1 不获取 UI Automator hierarchy，不解析 XML，也不尝试读取 App 元数据。截图采集失败时，L3 不应沿用旧帧冒充当前页面。

### 4.3 输入原语

| 原语 | 实现 | 主要约束 |
| --- | --- | --- |
| 点击 / 滑动 / 按键 | `adb shell input tap/swipe/keyevent` | 返回只说明命令正常结束，不证明 UI 效果 |
| ASCII 文本 | `adb shell input text` | 空格按 Android `%s` 规则转换；远端 shell 参数经过引用 |
| 非 ASCII 文本 | 临时推送项目自带的 UI Automator 输入 helper | Android API 21+；目标输入框需支持当前焦点上的 `ACTION_SET_TEXT` |

Unicode helper 是**输入实现细节**：它仅对当前焦点的可编辑节点执行文本设置，不采集整页控件树，也不向感知层提供节点数据。因此纯视觉感知与保留 Unicode 输入能力并不冲突。它通常读取当前焦点文字与选区以插入或替换；密码节点或缺少有效选区时可能整段替换。helper 尽力清理临时 JAR，超时或断线时可能留有残余。

文本仅接受非空、`str.isprintable()` 为真的字符串。ASCII 路径中包含字面 `%s` 的输入可能拆为多条命令，途中失败可能只输入前缀。Unicode 路径也不是事务；失败或超时后不能假设输入没有生效。L1 不自动重试，调用方应重新截图确认页面。

## 5. 错误、超时与资源限制

所有设备运行故障继承 `DeviceError`：

| 类别 | 典型错误 | 处理原则 |
| --- | --- | --- |
| 环境 / 选择 | `AdbNotFoundError`、`DeviceNotFoundError`、`DeviceSelectionError` | 检查安装、设备 ID 和连接配置 |
| 状态 | `DeviceUnauthorizedError`、`DeviceOfflineError`、`DeviceClosedError` | 授权、重连或重新打开会话 |
| 命令 | `DeviceCommandError`、`DeviceCommandTimeoutError`、`DeviceProtocolError` | 不推断超时操作一定未生效 |
| 截图 / 输入 | `ScreenshotError`、`InputError`、`UnsupportedCapabilityError` | 区分损坏 PNG、输入拒绝与能力限制 |

非法类型或数值可能直接抛 `TypeError` / `ValueError`，不应作为设备故障重试。ADB 命令失败可能以命令类错误抛出；无效 PNG 等本地校验错误为 `ScreenshotError`。`AdbRunner` 的 `subprocess.run(timeout=...)` 限制单条命令；锁等待、截图解码及多步 Unicode 输入并非严格端到端截止时间。ADB 输出在进程结束后检查单流 32 MiB 上限，不是流式内存硬限制。

## 6. 使用与验证

```python
from vphone.device import AdbDeviceBackend

with AdbDeviceBackend().open("your-device-id") as device:
    health = device.health_check()
    if health.ready:
        frame = device.capture_screen()
        print(frame.width, frame.height, frame.sha256)
```

```bash
uv sync --extra dev
uv run --extra dev pytest -q tests/unit/device
VPHONE_DEVICE_ID=<设备序列号> uv run --extra dev pytest -q tests/integration/device
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
```

普通真机集成测试只读验证设备状态与截图。Unicode 输入测试还需显式设置 `VPHONE_INPUT_TEST_TEXT`，并事先在设备上聚焦一个合适的可编辑输入框；它会真实修改手机内容。移除控件树后，该测试只验证原语返回并可重新截图，**不自动证明文本最终值正确**；需要人工检查或另建视觉端到端场景。

## 7. 当前限制

- 没有跨进程设备租约、自动重连或设备资源调度；多进程/多机共享设备需要额外协调。
- 输入只支持坐标、按键、可打印文本；无直接控件点击、长按、多点触控或剪贴板方案。
- 截图不是页面稳定性证明；滚动、动画、弹窗或旋转后必须重新采集。
- 设备能力是静态声明，不是逐应用、逐输入框的探测结果。
- 尚无截图脱敏、严格端到端超时、流式内存硬限制或产品级隐私策略。
