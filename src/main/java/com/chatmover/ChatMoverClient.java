package com.chatmover;

import net.fabricmc.api.ClientModInitializer;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

public class ChatMoverClient implements ClientModInitializer {
    public static final Logger LOGGER = LogManager.getLogger("ChatMover");
    private static int keyboardHeight = 0;

    @Override
    public void onInitializeClient() {
        LOGGER.info("ChatMover Dynamic Initialized!");
    }

    // Method untuk menerima update tinggi keyboard secara real-time dari wrapper/system event Android
    public static void setKeyboardHeight(int height) {
        keyboardHeight = height;
    }

    public static int getKeyboardHeight() {
        return keyboardHeight;
    }
}
