package io.github.efxd29.keyboardchat;

/** Reads the active keyboard overlap from Zalith's Android-to-JVM IME bridge. */
public final class KeyboardChatOffset {
    private KeyboardChatOffset() {
    }

    public static int forGuiHeight(final int guiHeight) {
        return AndroidImeHeightProvider.getOffsetGui(guiHeight);
    }
}
