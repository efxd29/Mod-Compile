# Minecraft Java Launcher for Android — private prototype

Independent Android launcher project for a Java Edition launcher with a PC-launcher-inspired home screen.

## Architecture
- The interface is an overlay; the Java Edition runtime engine is checked out separately at build time.
- The engine supplies Microsoft sign-in, accounts, game instances/profiles, version lists, installation, launch lifecycle, and upstream mod-loader installers.
- MobileGlues is included by the upstream engine. Fresh installs default to its SFPEW compatibility wrapper, which upstream lists for all Minecraft versions; the engine retains fallback behavior when a renderer cannot initialize on a given device.
- Account authentication stays on the supported Microsoft OAuth/device flow; no passwords or tokens are committed to source.

## Build
GitHub Actions builds a Full Debug APK from the branch after each relevant push. The APK is published as `minecraft-launcher-debug-apk` in the run's artifacts (seven-day retention).

## Current scope
- Java Edition only; no Bedrock launcher.
- The upstream engine advertises near-complete version coverage from early historical releases through 26.x snapshots, with Forge/Fabric support. Exact version and loader compatibility remains dependent on the upstream engine and combinations actually tested.
- The home screen exposes Play, Installations (opens the instance/version picker), Skins, Minecraft News, Patch Notes, settings, controls, .jar installation, logs, and game files. Skins opens the official account skin page; Patch Notes opens the official Minecraft changelog archive. The interface remains an iterative mobile adaptation, not a pixel-perfect reproduction of every Windows-launcher screen.
- MobileGlues / SFPEW compatibility depends on device, GPU, driver, Minecraft version, and mods. A successful compile does not substitute for device testing.

## Licensing and identity
This project is not affiliated with or endorsed by Mojang Studios or Microsoft. No proprietary Windows launcher binary or Mojang original source code is included in this branch. The third-party engine is licensed under LGPL-3.0; see `THIRD_PARTY_NOTICES.md` and upstream license notices.
