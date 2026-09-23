# Unicode input helper

Android's `input text` command synthesizes key events and cannot reliably enter
characters such as Chinese. vPhone packages a small dex JAR that uses the
platform UI Automator runtime to set text on the currently focused UI node.

The helper is not installed on the device. The Python backend pushes it to a
unique path under `/data/local/tmp`, runs it once, and removes it.

To rebuild the packaged JAR:

```bash
ANDROID_HOME="$HOME/Android/Sdk" scripts/build-unicode-input-helper.sh
```

The helper receives base64-encoded UTF-8 text and reads the focused node's
current text and selection to preserve surrounding content when possible.
For password fields or unavailable selections, it may replace the entire text.
It does not use the clipboard or change the selected input method.
