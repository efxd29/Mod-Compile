# Keyboard Chat Lift — Fabric 26.3

Client-side Fabric mod that raises the original vanilla chat messages and chat input above a docked Android virtual keyboard without adding an overlay or resizing Minecraft's GUI viewport.

## Automatic keyboard tracking

While chat is open, the mod polls Android's actual IME/window insets on the Android UI thread. It reads the IME top edge and active game surface's on-screen bounds, then converts only their overlapping area into Minecraft GUI coordinates. This accounts for Zalith's own surface translation so the full keyboard height is not blindly added twice. The vanilla input position is recalculated while rendering, so keyboard-height changes are followed.

Compatibility paths:
- Prefer Android `WindowInsets.Type.ime()` on Android 11+.
- Fall back to Android's visible display frame on older OS/window configurations.
- If neither source is available, no guessed keyboard height is applied.

Floating keyboards may report no docked IME inset, and some launcher/OS combinations may restrict active-Activity reflection. Direct testing in the target launcher is still needed to confirm behavior on that device.

## Requirements

- Minecraft Java Edition `26.3`
- Fabric Loader `0.19.5` or newer
- Java 25

## Install

1. Put `keyboard-chat-lift-1.0.0.jar` in the instance's `mods` folder.
2. Restart the Minecraft instance.
3. Open chat and show the keyboard; then change the keyboard height to verify that chat/input follows it.

## Build

Run `gradle build` from this directory. Output: `build/libs/keyboard-chat-lift-1.0.0.jar`.
