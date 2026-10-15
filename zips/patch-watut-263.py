#!/usr/bin/env python3
"""Port WATUT's client/server activity polling to Fabric tick events for Minecraft 26.3."""
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()

def replace_once(rel, old, new, label):
    p = root / rel
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match in {rel}; got {count}")
    p.write_text(text.replace(old, new))
    print("patched", label)

props = root / "gradle.properties"
ptext = props.read_text()
ptext = ptext.replace("org.gradle.parallel=true", "org.gradle.parallel=true\norg.gradle.caching=true")
ptext = ptext.replace("org.gradle.java.home=C:/Program Files/Microsoft/jdk-25.0.4.101-hotspot\n", "")
for key, val in {
    "minecraft_version": "26.3",
    "loader_version": "0.19.5",
    "fabric_version": "0.162.0+26.3",
    "forgeconfigapiport_version": "26.3.1",
    "mod_version": "26.3-1.2.5-activityfix1",
}.items():
    import re
    pattern = rf"(?m)^{re.escape(key)}=[^\n]*$"
    ptext, n = re.subn(pattern, f"{key}={val}", ptext)
    if n != 1:
        raise SystemExit(f"failed to set {key}: expected one property, got {n}")
props.write_text(ptext)

# Use the public Modrinth Maven mirror for CoroUtil 1.21.4 as compile-time API only.
# Runtime uses the separately installed CoroUtil MC 26.3 JAR.
gradle = root / "build_fabric.gradle"
gtext = gradle.read_text()
gtext = gtext.replace("id 'net.fabricmc.fabric-loom' version '1.17-SNAPSHOT'", "id 'net.fabricmc.fabric-loom' version '1.17.21'")
gtext = gtext.replace("repositories {", 'repositories {\n\tmaven { url "https://api.modrinth.com/maven" }\n\tmavenCentral()', 1)
old_dep = 'implementation "com.corosus.coroutil:CoroUtil:' + "${project.minecraft_version}" + '.0-' + "${project.coroutil_version}" + '"'
if gtext.count(old_dep) != 1:
    raise SystemExit("CoroUtil dependency pattern not found exactly once")
gtext = gtext.replace(old_dep, 'implementation "maven.modrinth:rLLJ1OZM:kGU8LxQf"')
gtext = gtext.replace('implementation "fuzs.forgeconfigapiport:forgeconfigapiport-fabric:' + "${project.forgeconfigapiport_version}" + '"\n', '')
gradle.write_text(gtext)

wrapper = root / "gradle/wrapper/gradle-wrapper.properties"
wtext = wrapper.read_text()
import re
wtext, n = re.subn(r"(?m)^distributionUrl=.*$", "distributionUrl=https\\://services.gradle.org/distributions/gradle-9.7.1-bin.zip", wtext)
if n != 1:
    raise SystemExit("failed to update Gradle wrapper URL")
wrapper.write_text(wtext)

# Runtime version/dependency metadata.
fabric_meta = root / "src/main/resources/fabric.mod.json"
meta = json.loads(fabric_meta.read_text())
meta["depends"]["fabricloader"] = ">=0.19.5"
meta["depends"]["coroutil"] = ">=26.3-1.3.8"
meta["depends"]["minecraft"] = "~26.3"
meta["depends"]["java"] = ">=25"
fabric_meta.write_text(json.dumps(meta, indent=2) + "\n")

# Remove optional hooks that can silently fail on 26.3, and replace them with API tick events.
mixins_path = root / "src/main/resources/watut.mixins.json"
mixins = json.loads(mixins_path.read_text())
for old in ("client.MinecraftTick", "client.ClientPlayerTick"):
    mixins["client"] = [m for m in mixins.get("client", []) if m != old]
for old in ("PlayerTick", "PlayerLoggedIn"):
    mixins["mixins"] = [m for m in mixins.get("mixins", []) if m != old]
mixins_path.write_text(json.dumps(mixins, indent=2) + "\n")

# Client status polling through Fabric's supported end-of-tick callback.
client_file = "src/main/java/com/corosus/watut/client/WatutClientMod.java"
replace_once(client_file,
    "import net.fabricmc.api.ClientModInitializer;\n",
    "import net.fabricmc.api.ClientModInitializer;\nimport net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;\n",
    "client tick import")
replace_once(client_file,
    "    public void onInitializeClient() {\n",
    "    public void onInitializeClient() {\n        // Tick all client-side player activity from Fabric's stable event API.\n        ClientTickEvents.END_CLIENT_TICK.register(client -> getPlayerStatusManagerClient().tickGame());\n\n",
    "client tick registration")

# Server player config, join/leave, and activity bookkeeping through supported Fabric callbacks.
server_file = "src/main/java/com/corosus/watut/WatutMod.java"
replace_once(server_file,
    "import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;\n",
    "import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;\nimport net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;\n",
    "server tick import")
replace_once(server_file,
    "import net.fabricmc.fabric.api.networking.v1.ServerPlayNetworking;\n",
    "import net.fabricmc.fabric.api.networking.v1.ServerPlayNetworking;\nimport net.fabricmc.fabric.api.networking.v1.ServerPlayConnectionEvents;\n",
    "join/disconnect event import")
replace_once(server_file,
    "import net.minecraft.server.MinecraftServer;\n",
    "import net.minecraft.server.MinecraftServer;\nimport net.minecraft.server.level.ServerPlayer;\n",
    "ServerPlayer import")
anchor = """        ServerLifecycleEvents.SERVER_STOPPED.register(server -> {
            minecraftServer = null;
            serverManager = null;
        });
"""
addition = anchor + """
        // Avoid silent no-op Player.tick/PlayerList mixins on mappings where injection targets move.
        ServerTickEvents.END_WORLD_TICK.register(world -> {
            for (ServerPlayer player : world.players()) {
                getPlayerStatusManagerServer().tickPlayer(player);
            }
        });
        ServerPlayConnectionEvents.JOIN.register((handler, sender, server) ->
                getPlayerStatusManagerServer().playerLoggedIn(handler.player));
        ServerPlayConnectionEvents.DISCONNECT.register((handler, server) ->
                getPlayerStatusManagerServer().playerLoggedOut(handler.player));
"""
replace_once(server_file, anchor, addition, "server tick and player lifecycle registration")

# Poll every client player once per tick. This replaces the inherited AbstractClientPlayer.tick mixin.
manager_file = "src/main/java/com/corosus/watut/client/status/PlayerStatusClientManager.java"
replace_once(manager_file,
    """        lastLevel = level;

        // Elaborazione e upload delle texture dinamiche ricevute
""",
    """        lastLevel = level;

        // Poll every client player once per tick. This avoids relying on a mixin into
        // AbstractClientPlayer.tick, which can be inherited and have no body to inject into.
        for (Player player : level.players()) {
            tickPlayer(player);
        }

        // Elaborazione e upload delle texture dinamiche ricevute
""",
    "central client-player polling")
replace_once(manager_file,
    """        statusPrevLocal.setPlayerGuiState(statusLocal.getPlayerGuiState());
        Screen currentScreen = InputTracker.getCurrentScreen();

        if (ConfigClient.sendActiveGui && !statusLocal.isIdle()) {
            sendGuiStatus(inputTracker.detectGuiState(currentScreen));
        } else {
            sendGuiStatus(PlayerGuiState.NONE);
        }
""",
    """        statusPrevLocal.setPlayerGuiState(statusLocal.getPlayerGuiState());
        Screen currentScreen = InputTracker.getCurrentScreen();
        PlayerGuiState detectedGuiState = inputTracker.detectGuiState(currentScreen);

        // Opening/closing a GUI is activity in its own right. On MC 26.3 some keyboard
        // paths can bypass the legacy KeyboardHandler mixin, so a screen transition must
        // wake an idle player even when no key callback arrives.
        if (detectedGuiState != statusLocal.getPlayerGuiState()) {
            onAction();
        }

        if (ConfigClient.sendActiveGui && !statusLocal.isIdle()) {
            sendGuiStatus(detectedGuiState);
        } else {
            sendGuiStatus(PlayerGuiState.NONE);
        }
""",
    "GUI transition wakes idle status")

print("WATUT MC 26.3 activity patch applied.")
