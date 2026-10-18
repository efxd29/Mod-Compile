# Essentials Fabric — Sudo for Minecraft 26.3

Server-side Fabric mod focused on the /sudo feature discussed for EssentialsX. This is a fresh Fabric implementation of that feature, not a full port of the Bukkit/Paper EssentialsX suite.

## Command

    /sudo <player> <command>

Examples:

    /sudo Steve help
    /sudo Steve say hello
    /sudo Steve gamemode creative

A leading slash on the nested command is optional. The target must be online.

## Security and permissions

- Only sources with Minecraft's built-in admin command permission can invoke /sudo.
- The nested command is executed with a command source created from the target player. It uses the target's own command permissions and player context; it does not simply grant the target operator privileges.
- The mod does not take over the player's authenticated client session, movement, inventory input, or chat-signing session.
- Each /sudo use is recorded in the server log.

## Install

1. Use a Fabric 26.3 server with Java 25, Fabric Loader 0.19.5 or newer, and Fabric API 0.163.0+26.3 or compatible.
2. Download the built essentials-fabric-0.1.0.jar from the GitHub Actions artifact.
3. Place the JAR in the server's mods/ directory and restart the server.

## Build

The GitHub Actions workflow builds this project using Java 25 and Gradle 9.7.1. No Termux or local Android build is needed.
