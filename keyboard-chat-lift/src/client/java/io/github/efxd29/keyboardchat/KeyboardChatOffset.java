package io.github.efxd29.keyboardchat;

/** Reads the live IME height published by Zalith's ChatImeInsetBridge. */
public final class KeyboardChatOffset {
    private KeyboardChatOffset() {
    }

    public static int forGuiHeight(final int guiHeight) {
        return AndroidImeHeightProvider.getOffsetGui(guiHeight);
    }
}
