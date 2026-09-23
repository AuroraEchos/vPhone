# L2 Action

L2 接收已经确定的具体动作，使用 L1 `DeviceSession` 执行，并给上层返回结构化结果。
执行器只依赖设备层协议，不依赖 ADB 实现。

## 职责

- 表达并校验点击、滑动、按键、文本输入四种动作。
- 将动作派发到对应的 L1 原语。
- 记录动作种类、耗时、L1 原语结果或原始 `DeviceError`。
- 允许调用方为单次动作指定超时；未指定时使用 L1 默认值。

## 不负责

- 不根据文字、控件树或图像寻找目标；上层应先确定坐标。
- 不判断界面是否达到预期状态，也不自动截图或采集控件树。
- 不在失败或超时后自动重试。输入可能已经部分生效，重放可能造成重复操作。
- 不提供动作序列编排、等待策略或业务决策。

`TapAction` 和 `SwipeAction` 使用非负像素坐标。L2 校验类型和数值范围，但不采集屏幕来判断坐标是否越界；提供坐标的上层负责使用当前页面尺寸。`TextAction` 向当前焦点输入可打印文本，不负责寻找或聚焦输入框。Unicode 输入还要求焦点控件支持 L1 的无障碍文本操作。

## 执行结果

`ActionResult.completed=True` 只表示 L1 调用正常返回，**不代表按钮确实被点中、文本确实出现在目标控件中，或任务已经完成**。上层若需要验证效果，应在动作后重新观察页面。

设备层抛出的 `DeviceError` 放在 `ActionResult.error` 中，并保留原始异常类型；此时 `completed=False`。尤其在超时后，不能断定设备没有执行该动作。动作类型错误和非法超时属于调用方错误，会在调用设备前直接抛出 `TypeError` 或 `ValueError`。执行结果只保存动作种类，不保存文本内容。

## 使用示例

```python
from vphone.action import ActionExecutor, KeyAction, TapAction
from vphone.device import AdbDeviceBackend, KeyCode, Point

with AdbDeviceBackend().open("your-device-id") as device:
    executor = ActionExecutor(device)
    home = executor.execute(KeyAction(KeyCode.HOME))
    tap = executor.execute(TapAction(Point(400, 600)), timeout=5)

    print(home.completed, tap.completed)
    if tap.error is not None:
        print(type(tap.error).__name__, tap.error)
```

离线测试使用假设备会话验证派发、校验和失败路径。设置 `VPHONE_DEVICE_ID` 后，`android` 标记的集成测试会在真机上发送 HOME 键并采集截图。
