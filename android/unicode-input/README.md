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

The helper only receives base64-encoded UTF-8 text. It does not read existing
text, use the clipboard, or change the selected input method.
