# L4 纯视觉决策层技术设计

| 属性 | 内容 |
| --- | --- |
| 状态 | 首版已实现；通过单元测试、合成图坐标探针和固定真机任务验收 |
| 目标 | 将自然语言任务与当前截图转换为**最多一个**受验证的 L2 动作，形成单步闭环 |
| 对上接口 | `PlannerEngine.run(task, device)`、`RunResult` |
| 对下依赖 | L3 `PerceptionEngine`、L2 `ActionExecutor`、L1 `DeviceSession` |
| 模型适配 | `OpenAICompatibleDecisionModel`；端点、模型 ID 与请求选项由 `ModelConfig` 注入 |
| 非目标 | 任意任务的安全自治、批量动作、后台调度、OCR、控件树、自动业务回滚 |

## 1. 设计原则与职责

截图是页面状态的唯一观测输入。L4 每次只根据**本轮完整截图**、任务和简短动作历史请求模型提出一个函数工具调用。模型不直接接触 ADB；本地控制器先解析工具名与 JSON 参数，再把具体动作交给 L2。L2 的正常返回只能说明设备命令执行完毕，不能证明目标 UI 发生变化，因此下一步必须重新截图。

```text
用户任务 + 当前 PageObservation
              ↓
OpenAICompatibleDecisionModel：截图 + 工具定义 → 一个候选决策
              ↓
tools.py：严格解析工具与参数；coordinates.py：坐标边界检查
              ↓
PlannerEngine：动作种类许可 / 次数与时间预算 / 终止状态
              ↓
ActionExecutor：执行一个 L2 动作
              ↓
重新 observe()；不复用上一步的坐标或假定点击已命中
```

层间分工：`provider.py` 只发送请求并接收候选；`tools.py` 只定义/解析模型协议；`engine.py` 决定是否派发；L2 执行；L3 截图。未来更换模型时不应修改 L1–L3。

## 2. 数据契约

### 2.1 模型输入

当前适配器采用 OpenAI 兼容的 Chat Completions 请求格式。每次请求都是由本地重新组装的新调用，不依赖服务端对话记忆；包含任务、当前截图的宽高、此前动作的简短描述及其**设备命令**结果。截图以 PNG base64 数据 URL 作为 `user` 图片块发送，图像细节由配置决定；不发送过去截图、不发送 OCR 或控件树。动作历史不把已输入的文本内容写进描述。

首个验收配置采用 DeepSeek 的 `deepseek-flash`。其官方文档说明了 PNG 图像与函数工具调用能力：[视觉输入](https://api-docs.deepseek.com/guides/vision/) · [工具调用](https://api-docs.deepseek.com/guides/tool_calls/)。适配器在请求中明确提供截图宽高，要求返回该截图内的像素坐标。配置其他模型时，必须单独核对其对图片块、所配置的图像细节、函数工具调用及可选请求字段的支持；仅更改模型 ID 不保证兼容。

### 2.2 工具与终止决策

| 模型工具 | 转换结果 | 首版校验 |
| --- | --- | --- |
| `tap(x,y)` | `TapAction(Point)` | 坐标为整数且处于当前截图范围 |
| `swipe(start_x,start_y,end_x,end_y,duration_ms)` | `SwipeAction` | 起终点在图内；时长 100–2000 ms |
| `press_key(key)` | `KeyAction` | 仅 `BACK`、`HOME`、`ENTER`、`APP_SWITCH`；无 `POWER` 或任意键码 |
| `input_text(text)` | `TextAction` | 非空、可打印、最多 1000 字符；进度日志不记录内容 |
| `finish(answer)` | `FinishDecision` | 非空答案；必须有本轮观测；答案仍需独立验收 |
| `stop(reason)` | `StopDecision` | 明确停止，不派发设备动作 |
| `request_confirmation(question)` | `ConfirmationDecision` | 暂停并返回问题；当前不自动恢复执行 |

首版只使用**当前截图像素坐标**。`tools_for_screen()` 为本轮截图生成动态 `maximum`，`to_screen_point()` 再次验证整数类型和 `< width/height`；越界或非整数值直接拒绝，不截断、不猜测。三张合成图的像素定位偏差为 3、3、2 像素，固定真机任务也完成。

模型可能输出错误 JSON、额外字段、缺失字段、多个工具调用、未知工具或自然语言文本。遇到这种无效候选，适配器最多使用**同一张截图重新请求一次**，明确说明格式错误；这期间不执行设备动作。第二次仍不合法就停止，绝不从自然语言猜动作或补造缺失坐标。官方文档同样提醒工具参数仍需客户端验证。[Chat Completions 接口](https://api-docs.deepseek.com/api/create-chat-completion/)

### 2.3 控制器返回值

`RunResult` 包含 `status`、`message`、`steps` 和 `final_observation`。`steps` 每项记录所依据的观测 ID / 截图哈希、已派发动作和 L2 结果，便于审查决策链；`RunResult` 自身不负责持久化，CLI 的轨迹记录器另行保存截图。`status=finished` 仅表示模型根据最后一张截图宣称完成，不是独立的业务证明。其它状态为 `stopped`、`needs_confirmation`、`action_limit`、`time_limit`、`error`。

### 2.4 本地任务轨迹

CLI 为每次任务在项目根目录创建 `traces/<UTC 时间戳>-<随机 ID>/`。`trajectory.json` 使用版本化结构，包含任务文本、模型 ID、设备 ID、开始/结束时间、最终状态与消息、动作数量，以及按顺序排列的 `turns`。每轮保存观测 ID、截图相对路径、SHA-256、尺寸和采集耗时；随后记录已验证的模型决策及实际派发的 L2 动作结果。截图单独保存在 `screenshots/0001.png` 等文件中，避免把大块 base64 放进 JSON。若模型请求失败，最新截图对应轮次的 `decision` 可以为 `null`。当前不记录模型内部推理或格式修复前的原始响应。

轨迹在开始、每次观测、决策、执行以及结束时原子更新 JSON；正常停止、达到预算、设备错误和用户中断都会写入终态。轨迹不保存 API Key，但**会保存原始截图、任务文本、模型答案及文本输入内容**，属于敏感本地数据。`traces/` 不纳入 Git；共享前需人工检查或脱敏。

## 3. 控制流程与失败语义

`PlannerEngine.run()` 默认最多派发 12 个动作、总时间预算 600 秒、动作后等待 0.5 秒再观察；CLI 可通过 `.env` 覆盖这些预算。到达动作上限后，控制器仍允许一次新的截图与模型判定：如果模型已经能给出答案，就正常完成；如果还要求动作，则返回 `action_limit`，不执行第 13 次。时间预算在每次观测前和模型返回后检查；单个在途网络请求的超时由 `VPHONE_MODEL_TIMEOUT_SECONDS` 控制，整体预算不是强制中断计时器。

截图失败、模型请求失败、连续两次无效决策或设备动作失败都会以 `error` 结束。唯一自动重试是上文所述的无动作模型格式修复；设备动作绝不自动重试。设备超时可能意味着命令已经部分生效，因此不能盲目重发动作。`request_confirmation` 返回给调用方，**目前不会自动询问用户后继续任务**。回调 `on_step` 只用于本地进度输出，不应上传截图或敏感文本。

当前 CLI 接收任意任务文本，可使用点击、滑动、按键及文本输入；模型被要求在后果重大的操作前提出确认，但这不是可靠的安全保证。系统**不能可靠识别任意 App 中每个按钮是否会发送、删除或支付**；因此不要把本版本用于含不可逆步骤的无人值守任务。`allowed_kinds` 可在 Python API 中限制动作类别，但不能单靠它证明某次点击安全。

## 4. 文件组织与运行

| 文件 | 职责 |
| --- | --- |
| [`models.py`](../../src/vphone/planner/models.py) | 决策、步骤记录与运行结果 |
| [`config.py`](../../src/vphone/planner/config.py) | 模型端点与请求选项的环境配置及校验 |
| [`protocol.py`](../../src/vphone/planner/protocol.py) | 可替换的模型决策接口 |
| [`coordinates.py`](../../src/vphone/planner/coordinates.py) | 本轮截图像素坐标校验 |
| [`tools.py`](../../src/vphone/planner/tools.py) | 函数工具 schema 与严格解析 |
| [`provider.py`](../../src/vphone/planner/provider.py) | 发送 PNG 截图、接收一个工具调用 |
| [`engine.py`](../../src/vphone/planner/engine.py) | 观测—决策—派发闭环与预算 |
| [`main.py`](../../src/vphone/main.py) | 接收任务文本的命令行入口 |
| [`trajectory.py`](../../src/vphone/trajectory.py) | 逐轮 JSON 轨迹与截图持久化 |
| [`scripts/probe_coordinates.py`](../../scripts/probe_coordinates.py) | 无触碰合成图坐标探针 |

```bash
uv sync --extra dev
uv run python scripts/probe_coordinates.py
uv run vphone "在系统设置中查看当前电量"
```

根目录 [`.env.example`](../../.env.example) 是可提交的配置模板；本地 `.env` 已被 Git 忽略。`vphone` 从当前工作目录向上寻找 `.env` 并加载，再由 `ModelConfig.from_env()` 读取配置；已有进程环境变量优先。必填字段是 `API_KEY`、`VPHONE_MODEL_BASE_URL`、`VPHONE_MODEL_ID`。可选字段是 `VPHONE_MODEL_TIMEOUT_SECONDS`（默认 90）、`VPHONE_MODEL_MAX_OUTPUT_TOKENS`（默认 4096）、`VPHONE_MODEL_REASONING_EFFORT` 和 `VPHONE_MODEL_IMAGE_DETAIL`（后两者未设置时不发送）。示例配置的图片细节为 `original`。任务预算可设置 `VPHONE_MAX_ACTIONS`（默认 12）、`VPHONE_MAX_SECONDS`（默认 600）和 `VPHONE_SETTLE_SECONDS`（默认 0.5）。设备动作不自动重试；CLI 的进度日志只输出动作类型及设备命令结果，不打印输入文本。

运行前应确认手机已授权，必要时设置 `VPHONE_DEVICE_ID`；脚本只在恰有一台 ready 设备时自动选择。真机截图会发给所配置的模型服务，请仅在允许传输当前页面的设备上运行。不要把 `.env`、截图、模型完整请求或响应写进提交及共享日志。更换端点后先运行无触碰坐标探针，再做受限真机验收。

## 5. 验收记录与后续边界

- 离线单测覆盖坐标边界、工具类型与字段校验、单动作闭环、动作上限、多工具调用拒绝、禁用动作不派发等路径；全量测试另覆盖 L1–L3 回归。
- 三张合成 PNG 分别在 `(295,640)`、`(120,250)`、`(470,950)` 放置品红圆点，模型像素误差为 3、3、2；该探针不接触手机。
- 真机 `10AG262J1H003X1` 从桌面开始，模型执行 8 次动作到达系统“电池”页，回答“当前电量为 67%（正在充电）”；结束截图独立核对显示“当前电量 67%（正在充电）”。
- 过程中曾观察到模型给出不符合契约的坐标或字段；控制器均停止，没有自动猜测或执行无效候选。当前可靠性仍需通过多轮、多设备、不同 App 的任务集量化，不能从单次成功推断通用成功率。

后续可评估：页面稳定等待、模型输出一次修复机会、坐标局部放大与裁剪的显式变换、不可逆操作的人类确认机制、任务级成功率与费用/延迟监控。这些不是首版默认行为。
