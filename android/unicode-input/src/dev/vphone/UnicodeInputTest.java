package dev.vphone;

import android.util.Base64;
import android.os.Bundle;
import android.os.Build;
import android.view.accessibility.AccessibilityNodeInfo;

import com.android.uiautomator.core.UiObject;
import com.android.uiautomator.core.UiSelector;
import com.android.uiautomator.testrunner.UiAutomatorTestCase;

import java.nio.charset.StandardCharsets;

/** Sets Unicode text on the currently focused accessibility node. */
public final class UnicodeInputTest extends UiAutomatorTestCase {
    public void testInputText() throws Exception {
        String encoded = getParams().getString("text_base64");
        if (encoded == null) {
            throw new AssertionError("missing text_base64 argument");
        }

        byte[] data = Base64.decode(encoded, Base64.NO_WRAP);
        String text = new String(data, StandardCharsets.UTF_8);
        FocusedUiObject focused = new FocusedUiObject();

        if (!focused.waitForExists(1000)) {
            throw new AssertionError("no focused UI node was found");
        }
        if (!focused.setUnicodeText(text)) {
            throw new AssertionError("the focused UI node rejected text");
        }
    }

    private static final class FocusedUiObject extends UiObject {
        FocusedUiObject() {
            super(new UiSelector().focused(true));
        }

        boolean setUnicodeText(String text) {
            AccessibilityNodeInfo node = findAccessibilityNodeInfo(1000);
            if (node == null) {
                return false;
            }
            CharSequence currentValue = node.getText();
            String current = currentValue == null ? "" : currentValue.toString();
            if (Build.VERSION.SDK_INT >= 26 && node.isShowingHintText()) {
                current = "";
            }
            int selectionStart = node.getTextSelectionStart();
            int selectionEnd = node.getTextSelectionEnd();
            String updated = text;
            int cursor = text.length();
            if (!node.isPassword()
                    && selectionStart >= 0
                    && selectionEnd >= selectionStart
                    && selectionEnd <= current.length()) {
                updated = current.substring(0, selectionStart)
                        + text
                        + current.substring(selectionEnd);
                cursor = selectionStart + text.length();
            }

            Bundle arguments = new Bundle();
            arguments.putCharSequence(
                    AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE,
                    updated
            );
            if (!node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, arguments)) {
                return false;
            }

            Bundle selection = new Bundle();
            selection.putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_START_INT, cursor);
            selection.putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_END_INT, cursor);
            node.performAction(AccessibilityNodeInfo.ACTION_SET_SELECTION, selection);
            return true;
        }
    }
}
