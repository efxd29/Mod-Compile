# Keyboard Chat Lift — Fabric 26.3 v1.1.2

Fixes the chat-screen Mixin callback signature and improves Android keyboard detection.

- Hook the vanilla chat screen's current render-state method using its Minecraft 26.x render arguments.
- Prefer the focused Zalith `VMActivity`, then SDL's active Activity, rather than a stale launcher screen.
- Use Android IME insets and the actual game-surface bounds whenever they are accessible.
- Continue recalculating the chat input position while the chat is rendered.
- Use an Android-only fallback offset if launcher internals are unavailable, while continuing to retry IME detection.
- Does not alter the Minecraft viewport or add a replacement chat overlay.

## Requirements
- Minecraft Java Edition 26.3
- Fabric Loader 0.19.5 or newer
- Java 25

## Install
Remove previous Keyboard Chat Lift JARs (same mod ID), install `keyboard-chat-lift-1.1.2.jar`, and restart the instance. Test chat with the keyboard at different heights. Build is verified on GitHub Actions; runtime needs confirmation on the target Zalith/Android device.
