# IME input helper

vPhone packages a minimal, non-visual Android input method. The device backend
installs or upgrades it while opening a session, before an editor is focused.
During a text action, the backend enables and selects the helper long enough to
perform one of two editor operations, then restores the previous input method
and disables the helper:

- `input_text` calls `InputConnection.commitText()` at the current selection.
- `replace_text` selects the focused editor's complete extracted text and then
  calls `commitText()` once. If the editor cannot provide or select its text,
  the operation fails instead of silently appending the replacement.

This uses the same Android editor protocol as an ordinary software keyboard. It
does not inspect accessibility nodes, use the clipboard, or special-case apps.
Both operations require the intended editor to already have input focus.
The broadcast endpoint requires the platform `android.permission.DUMP`
permission, which the ADB shell owns and ordinary applications do not.

To rebuild the packaged APK:

```bash
ANDROID_HOME="$HOME/Android/Sdk" scripts/build-ime-input-helper.sh
```
