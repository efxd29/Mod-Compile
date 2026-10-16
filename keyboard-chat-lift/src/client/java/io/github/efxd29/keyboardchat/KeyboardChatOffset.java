package io.github.efxd29.keyboardchat;

/** Provides the current Android-keyboard overlap offset in Minecraft's scaled GUI coordinates. */
public final class KeyboardChatOffset {
    private KeyboardChatOffset() {
    }

    public static int forGuiHeight(final int guiHeight) {
        return AndroidImeHeightProvider.getOffsetGui(guiHeight);
    }
}
