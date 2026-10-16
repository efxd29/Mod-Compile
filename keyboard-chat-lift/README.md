# Keyboard Chat Lift — Fabric 26.3 v1.1.1

This build fixes Android Activity lookup and adds a safety fallback for Android launchers where activity/window introspection is restricted.

- Prefer the currently focused Zalith `VMActivity`; do not select a stale launcher screen if a current render surface is available.
- Try the launcher's SDL activity as a compatibility path.
- Prefer real Android IME insets and convert only the keyboard area overlapping the actual game surface.
- Follow the moving input position while chat is rendering.
- If Android reports no usable activity/inset data, use a conservative Android-only fallback offset to keep the vanilla chat from remaining underneath the keyboard while automatic detection continues to retry.
- Desktop Minecraft is unaffected by this fallback.
- The viewport is not resized or squashed by this mod.

## Requirements
- Minecraft Java Edition 26.3
- Fabric Loader 0.19.5 or newer
- Java 25

## Install
Remove older Keyboard Chat Lift JARs first, because all versions share the same mod ID. Put `keyboard-chat-lift-1.1.1.jar` into the instance's `mods` folder, restart, then open chat and test with different keyboard heights.

Exact positioning still depends on Android and launcher behavior. This build has passed compilation but needs an on-device Zalith test for runtime confirmation.
