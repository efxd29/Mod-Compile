# Keyboard Chat Lift — Fabric 26.3 v2.0.0

## Important: requires the paired Zalith IME-bridge launcher build

Previous builds tried to call Android `Activity`/window-inset APIs from the Minecraft OpenJDK VM. That JVM cannot reliably access the Android Compose activity, so the old implementation could resolve the offset to zero. This build does not repeat that approach.

The paired launcher patch writes the current Android IME height, full game-surface height, and Zalith's own surface translation to:

`Android/data/com.movtery.zalithlauncher.v2/files/keyboard-chat-lift/ime-height.txt`

The mod reads that live bridge state, subtracts any surface translation Zalith already applied, converts the remaining overlap into Minecraft GUI coordinates, and raises the native vanilla chat messages/input. The launcher refreshes the state while the keyboard is visible or hidden, including height changes.

## Requirements
- Minecraft Java Edition 26.3
- Fabric Loader 0.19.5 or newer
- Java 25
- The paired Zalith Launcher build from the `keyboard-chat-ime-bridge` branch, built as arm64 Release

The mod intentionally does not guess a fixed screen percentage when the bridge file is absent. An unpatched launcher cannot provide exact IME height to an ordinary Fabric mod, so it returns zero rather than pretending detection succeeded.

## Install
1. Install/update to the paired Zalith Launcher build first.
2. Remove all older Keyboard Chat Lift JARs because they share the mod ID.
3. Put `keyboard-chat-lift-2.0.0.jar` into the Minecraft 26.3 instance's `mods` folder.
4. Restart the launcher and Minecraft, open chat, and change the keyboard height to verify the input stays above the keyboard.

## Build
Run `gradle build`. The output JAR is `build/libs/keyboard-chat-lift-2.0.0.jar`.
