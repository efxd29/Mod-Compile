package io.github.efxd29.keyboardchat;

/**
 * One resolution-aware offset shared by the chat messages, edit box, and edit-box background.
 * Minecraft/Fabric do not expose Android IME bounds to ordinary client mods, so this intentionally
 * uses a scaled-height heuristic rather than pretending to detect the exact keyboard height.
 */
public final class KeyboardChatOffset {
    private static final float HEIGHT_FACTOR = 0.42F;
    private static final int MIN_OFFSET = 80;
    private static final int MAX_OFFSET = 240;

    private KeyboardChatOffset() {
    }

    public static int forGuiHeight(final int guiHeight) {
        final int computed = Math.round(guiHeight * HEIGHT_FACTOR);
        return Math.max(MIN_OFFSET, Math.min(MAX_OFFSET, computed));
    }
}
