# Keyboard Chat Lift — Fabric 26.3

Client-side Fabric mod that raises the **real vanilla chat messages** and the **real vanilla chat input box** while `ChatScreen` is open. It does not resize the window, alter the game viewport, add an overlay, or replace the chat UI.

## Build

- Minecraft: `26.3`
- Fabric Loader: `0.19.5`
- Java toolchain: `25`
- Build: `gradle build`

The output JAR is in `build/libs/keyboard-chat-lift-1.0.0.jar`.

## Install

1. Use Minecraft Java Edition `26.3` with Fabric Loader `0.19.5` or newer and Java 25.
2. Put `keyboard-chat-lift-1.0.0.jar` in the instance's `mods` folder.
3. Fully restart the game/launcher and open chat to test.

## Offset

The offset is recalculated from Minecraft's scaled GUI height: 42% of the scaled height, clamped to 80–240 GUI pixels. It shifts the chat's own bottom coordinate and the input widget/background only. It never changes the game viewport.

Minecraft/Fabric does not expose Android's exact virtual-keyboard/IME bounds to a regular client mod, so the mod cannot precisely detect the keyboard's top edge. If the input is still too low/high for a particular launcher or GUI scale, adjust `HEIGHT_FACTOR`, `MIN_OFFSET`, or `MAX_OFFSET` in `KeyboardChatOffset.java` and rebuild.
