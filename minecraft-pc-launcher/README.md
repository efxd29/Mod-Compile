# Minecraft Java Launcher for Android — private prototype

This branch contains an independent UI overlay and a build workflow for an Android launcher using the upstream PojavLauncher/MojoLauncher Java Edition engine. The goal is a compact, PC-launcher-inspired Java Edition home screen while preserving the existing engine's Microsoft sign-in, profiles/instances, version list, install flow, and MobileGlues renderer integration.

## Build

Push changes to this branch or run **Actions → Android launcher build → Run workflow**. The workflow checks out the upstream engine, applies the overlay without changing the upstream source repository, builds the Full Debug APK, and uploads it as the `minecraft-launcher-debug-apk` artifact.

The GitHub Actions build is the first real compile check. Device behavior, renderer compatibility, sign-in, and launch across Minecraft versions still require testing.

## Scope

- Java Edition only. Bedrock is not included.
- Preserve the upstream engine's supported runtime/version/loading capabilities rather than claiming untested universal compatibility.
- Existing profile/instance editing is used for installation management.
- MobileGlues integration is inherited from the upstream engine; graphics support varies by device/GPU/driver and is not a guarantee against crashes.
- This is a prototype, not a copy of Mojang's original source and not affiliated with or endorsed by Mojang Studios or Microsoft.

## UI overlay layout

`overlay/app_pojavlauncher/src/main/res/layout/fragment_launcher.xml` replaces the engine's main-menu fragment layout. The core launcher view IDs are preserved so the existing Java event handlers keep working. `apply-overlay.sh` copies the overlay and applies app identity changes only in the temporary CI checkout of the engine.
