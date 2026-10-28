# GROW Island Offline APK (personal build)

This is an Android WebView wrapper for the original GROW Island SWF, using the open-source Ruffle Flash emulator. The original game file is fetched by the private build process from a third-party archive mirror and is bundled in the resulting APK, alongside Ruffle's JavaScript and WebAssembly files. The installed app does not request Android's INTERNET permission and is designed to run offline.

## Build

The workflow is `.github/workflows/build-grow-island-offline.yml`. It runs on pushes to the `grow-island-offline-apk` branch or by manual workflow dispatch. It downloads Ruffle 0.7.1 from the official Ruffle GitHub release and verifies the published SHA-256 before bundling it. It downloads the SWF from the mirror listed in the build log, checks its SWF signature and plausible file size, and then builds a debug APK with Gradle.

The resulting GitHub Actions artifact is named `GROW-Island-Offline-APK`.

## Important notes

- This is an unofficial personal wrapper and is not affiliated with or endorsed by EYEZMAZE.
- The game content is loaded from an archived SWF. The file is not included in the source repository; it is downloaded for the build and stored only inside the resulting APK artifact.
- Ruffle emulates Flash, so a few rendering or behavior details can differ from Adobe Flash Player. This preserves the original SWF game content rather than recreating its gameplay.
- The source URL is a third-party mirror, not the game's developer. The build validates the SWF header but does not prove the mirror's file is byte-for-byte identical to the developer's original release.
