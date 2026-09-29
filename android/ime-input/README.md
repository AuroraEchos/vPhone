# IME input helper

vPhone packages a minimal, non-visual Android input method. The device backend
installs or upgrades it while opening a session, before an editor is focused.
During a text action, the backend enables and selects the helper long enough to
call `InputConnection.commitText()` on the focused editor, then restores the
previous input method and disables the helper.

This uses the same Android editor protocol as an ordinary software keyboard. It
does not inspect accessibility nodes, use the clipboard, or special-case apps.
The broadcast endpoint requires the platform `android.permission.DUMP`
permission, which the ADB shell owns and ordinary applications do not.

To rebuild the packaged APK:

```bash
ANDROID_HOME="$HOME/Android/Sdk" scripts/build-ime-input-helper.sh
```
