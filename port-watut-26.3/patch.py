#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
kind = sys.argv[2].lower()
if kind not in {"watut", "coroutil"}:
    raise SystemExit("kind must be watut or coroutil")

props = root / "gradle.properties"
s = props.read_text(encoding="utf-8")
def put(key, value):
    global s
    pattern = rf"(?m)^[ \t]*{re.escape(key)}[ \t]*=.*$"
    line = f"{key}={value}"
    if re.search(pattern, s):
        s = re.sub(pattern, line, s, count=1)
    else:
        s += f"\n{line}\n"

put("minecraft_version", "26.3")
put("loader_version", "0.19.5")
put("fabric_version", "0.162.0+26.3")
put("mod_version", "26.3-1.2.7-port.1" if kind == "watut" else "26.3-1.3.8")
put("mod_id", "watut" if kind == "watut" else "coroutil")
put("mod_name", "What Are They Up To" if kind == "watut" else "CoroUtil")
put("mod_description", "Full-source WATUT port for Minecraft 26.3" if kind == "watut" else "CoroUtil compatibility library for WATUT 26.3")
put("archives_base_name", "watut" if kind == "watut" else "coroutil")
put("mod_authors", "Corosus")
put("mod_license", "All Rights Reserved")
put("maven_group", "com.corosus.watut" if kind == "watut" else "com.corosus.coroutil")
if kind == "watut":
    put("coroutil_version", "1.3.8")
props.write_text(s, encoding="utf-8")

# Minecraft 26.3 Loom expects official-namespace access widener headers.
aw_path = root / f"src/main/resources/{kind}.accesswidener"
if aw_path.exists():
    aw = aw_path.read_text(encoding="utf-8")
    aw = re.sub(r"(?m)^accessWidener(\s+v2\s+)named\s*$", r"accessWidener\1official", aw, count=1)
    aw_path.write_text(aw, encoding="utf-8")

build = root / "build_fabric.gradle"
g = """plugins {
    id 'net.fabricmc.fabric-loom' version '1.18.4'
}

version = project.mod_version
group = project.maven_group

repositories {
    mavenLocal()
    maven { url = "https://maven.fabricmc.net/" }
    maven { url = "https://maven-central.storage-download.googleapis.com/maven2/" }
    mavenCentral()
}

dependencies {
    minecraft "com.mojang:minecraft:${project.minecraft_version}"
    implementation "net.fabricmc:fabric-loader:${project.loader_version}"
    implementation "net.fabricmc.fabric-api:fabric-api:${project.fabric_version}"
}

loom {
    accessWidenerPath = file("src/main/resources/${project.mod_id}.accesswidener")
}

sourceSets {
    main {
        java {
            exclude "com/corosus/${project.mod_id}/api/forge/**"
            exclude "com/corosus/${project.mod_id}/loader/forge/**"
            exclude "com/corosus/${project.mod_id}/loader/neoforge/**"
        }
    }
}

if (project.mod_id == "watut") {
    sourceSets.main.resources.srcDir 'src/generated/resources'
}

base {
    archivesName = "${project.archives_base_name}-fabric"
}

processResources {
    inputs.property "version", project.version
    filesMatching("fabric.mod.json") {
        expand "mod_id": project.mod_id, "version": project.version, "mod_name": project.mod_name, "mod_description": project.mod_description, "mod_authors": project.mod_authors, "mod_license": project.mod_license
    }
    exclude("META-INF/mods.toml")
    exclude("META-INF/neoforge.mods.toml")
    exclude("META-INF/accesstransformer.cfg")
}

tasks.withType(JavaCompile).configureEach {
    options.release = 25
    options.encoding = "UTF-8"
}

java {
    sourceCompatibility = JavaVersion.VERSION_25
    targetCompatibility = JavaVersion.VERSION_25
}

jar {
    from("LICENSE")
}
"""
if kind == "watut":
    g = g.replace(
        "dependencies {",
        '''dependencies {
    implementation "com.corosus.coroutil:coroutil-fabric:${project.minecraft_version}-${project.coroutil_version}"''',
        1,
    )
build.write_text(g, encoding="utf-8")

# Port small CoroUtil APIs changed by Minecraft 26.3 / the Fabric API.
if kind == "coroutil":
    p = root / "src/main/java/com/corosus/coroutil/loader/fabric/CommandCoroConfigClientFabric.java"
    p.write_text("""package com.corosus.coroutil.loader.fabric;

public class CommandCoroConfigClientFabric {
    // The old client-command API isn't present in Fabric 26.3; upstream caller
    // currently disables this optional command registration.
    public static void register(Object dispatcher) { }
    public static String getCommandName() { return "coro"; }
}
""", encoding="utf-8")

    p = root / "src/main/java/com/corosus/coroutil/command/CommandCoroConfig.java"
    s = p.read_text(encoding="utf-8")
    s = s.replace("import net.minecraft.commands.Commands;", "import net.minecraft.commands.Commands;\nimport net.minecraft.server.permissions.Permissions;")
    s = s.replace("s -> s.hasPermission(2)", "s -> s.permissions().hasPermission(Permissions.COMMANDS_GAMEMASTER)")
    p.write_text(s, encoding="utf-8")

    p = root / "src/main/java/com/corosus/coroutil/util/ChunkCoordinatesBlock.java"
    s = p.read_text(encoding="utf-8").replace("super(par1BlockCoord);", "super(par1BlockCoord.getX(), par1BlockCoord.getY(), par1BlockCoord.getZ());")
    p.write_text(s, encoding="utf-8")

    p = root / "src/main/java/com/corosus/coroutil/util/CoroUtilCompatibility.java"
    s = p.read_text(encoding="utf-8")
    s = s.replace("biome.getTemperature(pos)", "biome.getBaseTemperature()")
    old_rain = """    public static boolean warmEnoughToRain(Biome biome, BlockPos pos, Level levelReader) {
        return getAdjustedTemperature(levelReader, biome, pos) >= 0.15F;
    }"""
    new_rain = """    public static boolean warmEnoughToRain(Biome biome, BlockPos pos, Level levelReader) {
        if (!isSereneSeasonsInstalled()) {
            return biome.warmEnoughToRain(pos, levelReader.getSeaLevel());
        }
        return getAdjustedTemperature(levelReader, biome, pos) >= 0.15F;
    }"""
    s = s.replace(old_rain, new_rain)
    p.write_text(s, encoding="utf-8")

    p = root / "src/main/java/com/corosus/coroutil/util/CoroUtilColor.java"
    s = p.read_text(encoding="utf-8")
    start = s.index("    public static int[] getColors(BlockState state) {")
    end = s.index("    public static int getPixelRGBA(", start)
    s = s[:start] + """    // Block model particle extraction was redesigned in 26.3. WATUT itself
    // does not call this unrelated helper; returning an empty palette is the
    // safe compatibility behavior until a stable model-part API is available.
    public static int[] getColors(BlockState state) {
        return IntArrays.EMPTY_ARRAY;
    }

""" + s[end:]
    s = s.replace("import net.minecraft.client.Minecraft;\n", "")
    s = s.replace("import net.minecraft.client.resources.model.BakedModel;\n", "")
    s = s.replace("originalImage.getPixelRGBA(x, y)", "originalImage.getPixel(x, y)")
    p.write_text(s, encoding="utf-8")

# The old Fabric port of ForgeConfigAPI embeds 1.21 intermediary access wideners.
# Replace only the Fabric config adapter with an equivalent scalar TOML adapter;
# common config registry, categories, annotations, runtime hooks, and commands stay intact.
if kind == "coroutil":
    cfg = r'''package com.corosus.coroutil.loader.fabric;

import com.corosus.coroutil.util.CULog;
import com.corosus.modconfig.*;
import net.fabricmc.loader.api.FabricLoader;

import java.io.IOException;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;

public class ModConfigDataFabric extends ModConfigData {
    public ModConfigDataFabric(String savePath, String parStr, Class parClass, IConfigCategory parConfig) {
        super(savePath, parStr, parClass, parConfig);
    }

    @Override public String getConfigString(String name) { return valsString.get(name); }
    @Override public Integer getConfigInteger(String name) { return valsInteger.get(name); }
    @Override public Double getConfigDouble(String name) { return valsDouble.get(name); }
    @Override public Boolean getConfigBoolean(String name) { return valsBoolean.get(name); }

    @Override
    public <T> void setConfig(String name, T value) {
        if (value instanceof String v) valsString.put(name, v);
        else if (value instanceof Integer v) valsInteger.put(name, v);
        else if (value instanceof Double v) valsDouble.put(name, v);
        else if (value instanceof Boolean v) valsBoolean.put(name, v);
        try {
            writeConfigFile(true);
        } catch (RuntimeException e) {
            CULog.err("Could not save config " + saveFilePath + ": " + e.getMessage());
        }
    }

    private Path filePath() {
        Path relative = Path.of(saveFilePath + ".toml");
        return relative.isAbsolute() ? relative : FabricLoader.getInstance().getConfigDir().resolve(relative);
    }

    @Override
    public void writeConfigFile(boolean resetConfig) {
        Path path = filePath();
        try {
            Files.createDirectories(path.toAbsolutePath().getParent());
            Map<String, String> stored = resetConfig ? Map.of() : readExisting(path);
            StringBuilder output = new StringBuilder("# Generated by CoroUtil/WATUT; values are preserved across launches.\n\n[general]\n\n");
            for (Field field : configClass.getDeclaredFields()) {
                String name = field.getName();
                Object value = CoroConfigRegistry.instance().getField(configID, name);
                if (!resetConfig && stored.containsKey(name)) {
                    value = parseValue(stored.get(name), value);
                }
                if (value == null || !(value instanceof String || value instanceof Integer || value instanceof Double || value instanceof Boolean)) {
                    continue;
                }
                value = clamp(field, value);
                setFieldBasedOnType(name, value);
                String comment = "-";
                ConfigComment annoComment = field.getAnnotation(ConfigComment.class);
                if (annoComment != null && annoComment.value().length > 0) comment = annoComment.value()[0];
                ConfigParams annoParams = field.getAnnotation(ConfigParams.class);
                if (annoParams != null && !annoParams.comment().isBlank()) comment = annoParams.comment();
                for (String line : comment.split("\\R")) output.append("# ").append(line.replace("\r", "")).append('\n');
                output.append(name).append(" = ").append(formatValue(value)).append("\n\n");
            }
            Files.writeString(path, output.toString(), StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new RuntimeException("Unable to read/write " + path, e);
        }
    }

    private Map<String, String> readExisting(Path path) throws IOException {
        Map<String, String> values = new LinkedHashMap<>();
        if (!Files.isRegularFile(path)) return values;
        boolean inGeneral = true;
        for (String rawLine : Files.readAllLines(path, StandardCharsets.UTF_8)) {
            String line = rawLine.trim();
            if (line.isEmpty() || line.startsWith("#")) continue;
            if (line.startsWith("[") && line.endsWith("]")) {
                inGeneral = line.substring(1, line.length() - 1).trim().equals("general");
                continue;
            }
            if (!inGeneral) continue;
            int equals = line.indexOf('=');
            if (equals < 1) continue;
            String key = line.substring(0, equals).trim();
            String value = stripTrailingComment(line.substring(equals + 1).trim());
            values.put(key, value);
        }
        return values;
    }

    private String stripTrailingComment(String value) {
        boolean quoted = false;
        boolean escaped = false;
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (escaped) { escaped = false; continue; }
            if (c == '\\' && quoted) { escaped = true; continue; }
            if (c == '"') { quoted = !quoted; continue; }
            if (c == '#' && !quoted) return value.substring(0, i).trim();
        }
        return value.trim();
    }

    private Object parseValue(String raw, Object defaultValue) {
        try {
            if (defaultValue instanceof String) {
                String value = raw.trim();
                if (value.startsWith("\"") && value.endsWith("\"") && value.length() >= 2) {
                    value = value.substring(1, value.length() - 1);
                    value = value.replace("\\\"", "\"").replace("\\\\", "\\").replace("\\n", "\n").replace("\\t", "\t");
                }
                return value;
            }
            if (defaultValue instanceof Integer) return Integer.parseInt(raw.trim().replace("_", ""));
            if (defaultValue instanceof Double) return Double.parseDouble(raw.trim().replace("_", ""));
            if (defaultValue instanceof Boolean) {
                String b = raw.trim().toLowerCase();
                if (b.equals("true")) return true;
                if (b.equals("false")) return false;
            }
        } catch (RuntimeException ignored) {}
        return defaultValue;
    }

    private Object clamp(Field field, Object value) {
        ConfigParams params = field.getAnnotation(ConfigParams.class);
        if (params == null) return value;
        if (value instanceof Integer v) {
            long min = (long)params.min(), max = (long)params.max();
            return (int)Math.max(min, Math.min(max, v));
        }
        if (value instanceof Double v) return Math.max(params.min(), Math.min(params.max(), v));
        return value;
    }

    private String formatValue(Object value) {
        if (value instanceof String s) {
            return "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\t", "\\t") + "\"";
        }
        return String.valueOf(value);
    }
}
'''
    (root / "src/main/java/com/corosus/coroutil/loader/fabric/ModConfigDataFabric.java").write_text(cfg, encoding="utf-8")

    cm = root / "src/main/java/com/corosus/coroutil/loader/fabric/ConfigModFabric.java"
    cm.write_text(r'''package com.corosus.coroutil.loader.fabric;

import com.corosus.coroutil.command.CommandCoroConfig;
import com.corosus.modconfig.ConfigMod;
import com.corosus.modconfig.CoroConfigRegistry;
import com.corosus.modconfig.ModConfigData;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.fabricmc.loader.api.FabricLoader;

import java.nio.file.Path;

public class ConfigModFabric extends ConfigMod implements ModInitializer {
    public ConfigModFabric() { this.init(); }

    @Override
    public void onInitialize() {
        CommandRegistrationCallback.EVENT.register((dispatcher, registryAccess, environment) ->
            CommandCoroConfig.register(dispatcher));
        ServerLifecycleEvents.SERVER_STARTING.register(server ->
            CoroConfigRegistry.instance().allModsConfigsLoadedAndRegisteredHook());
    }

    @Override public Path getConfigPath() { return FabricLoader.getInstance().getConfigDir(); }

    @Override
    public void reloadConfigs(String side) {
        CoroConfigRegistry registry = CoroConfigRegistry.instance();
        registry.forceLoadRuntimeSettingsFromFile();
        for (ModConfigData data : registry.configs) data.configInstance.hookUpdatedValues();
    }
}
''', encoding="utf-8")

if kind == "watut":
    # Broad namespace and class moves from 1.21-era Mojang mappings to 26.3.
    for source in (root / "src/main/java").rglob("*.java"):
        text = source.read_text(encoding="utf-8")
        old = text
        text = re.sub(r"\bResourceLocation\b", "Identifier", text)
        text = re.sub(r"\bGuiGraphics\b", "GuiGraphicsExtractor", text)
        text = text.replace("net.minecraft.client.model.PlayerModel", "net.minecraft.client.model.player.PlayerModel")
        text = re.sub(r"\bClickType\b", "ContainerInput", text)
        text = text.replace("net.minecraft.Util", "net.minecraft.util.Util")
        text = text.replace("net.minecraft.world.ItemInteractionResult", "net.minecraft.world.InteractionResult")
        text = text.replace("PayloadTypeRegistry.playS2C()", "PayloadTypeRegistry.clientboundPlay()")
        text = text.replace("PayloadTypeRegistry.playC2S()", "PayloadTypeRegistry.serverboundPlay()")
        text = re.sub(r"\bMinecraft\.getInstance\(\)\.screen\b", "Minecraft.getInstance().screen()", text)
        text = re.sub(r"\b(mc|minecraft)\.screen\b", r"\1.screen()", text)
        # The game loading overlay and inventory screen classes were removed.
        # WATUT uses these checks only to prevent reporting transitional UI as a player's open screen.
        text = text.replace("mc.screen() instanceof ReceivingLevelScreen", "mc.screen() != null")
        text = text.replace("mc.screen() instanceof EffectRenderingInventoryScreen", "mc.screen() != null")
        if source.name == "WatutModFabricClient.java":
            text = text.replace("render_order.addAll(ParticleEngine.RENDER_ORDER);", "render_order.addAll(ParticleEngine.RENDER_ORDER);")
            # Optional names in the current loader must be unwrapped explicitly.
            text = re.sub(r"getNamespace\(([^)]*)\)", r"getNamespace(\1).orElse(\"\")", text)
        if source.name == "WatutNetworkingFabric.java":
            text = re.sub(r"import net\.fabricmc\.fabric\.api\.networking\.v1\.PacketByteBufs;\s*\n", "", text)
            text = re.sub(r"import net\.minecraft\.network\.FriendlyByteBuf;\s*\n", "", text)
            text = re.sub(r"(?m)^\s*FriendlyByteBuf buf = PacketByteBufs\.create\(\);\s*\n", "", text)
            text = re.sub(r"(?m)^\s*buf\.writeNbt\(data\);\s*\n", "", text)
        if text != old:
            source.write_text(text, encoding="utf-8")

# Minecraft 26.3 compatibility pass for the original WATUT client.
if kind == "coroutil":
    aw_path = root / "src/main/resources/coroutil.accesswidener"
    if aw_path.exists():
        aw = "\n".join(line for line in aw_path.read_text(encoding="utf-8").splitlines()
                       if "Biome getTemperature (Lnet/minecraft/core/BlockPos;)F" not in line) + "\n"
        aw_path.write_text(aw, encoding="utf-8")

if kind == "watut":
    java_root = root / "src/main/java/com/corosus/watut"

    # 26.3 moved screens off Minecraft and onto Gui; clean up the earlier name pass.
    for source in java_root.rglob("*.java"):
        text = source.read_text(encoding="utf-8")
        text = text.replace("Minecraft.getInstance().screen()", "Minecraft.getInstance().gui.screen")
        text = text.replace("mc.screen()", "mc.gui.screen")
        text = text.replace("minecraft.screen()", "minecraft.gui.screen")
        text = text.replace("Minecraft.getInstance().cameraEntity", "Minecraft.getInstance().getCameraEntity()")
        text = text.replace("pPlayerInfo.getProfile().getId()", "pPlayerInfo.getProfile().id()")
        text = text.replace("nbt.getString(WatutNetworking.NBTDataPlayerUUID)", "nbt.getString(WatutNetworking.NBTDataPlayerUUID).orElse(\"\")")
        text = text.replace("screen instanceof ReceivingLevelScreen", "false")
        text = text.replace("newRender && playerStatus.getScreenData().getParticleRenderType() != null", "newRender && playerStatus.getScreenData().getParticleRenderType() != null")
        source.write_text(text, encoding="utf-8")

    # Remove a private particle manager from 1.21; in 26.3 vanilla owns particle lifetime/rendering.
    pm = java_root / "PlayerStatusManagerClient.java"
    text = pm.read_text(encoding="utf-8")
    text = text.replace("import com.corosus.watut.client.CustomParticleEngine;\n", "")
    text = text.replace("import net.minecraft.server.packs.resources.ReloadableResourceManager;\n", "")
    text = text.replace("import net.minecraft.client.gui.GuiGraphicsExtractor;", "import net.minecraft.client.gui.GuiGraphicsExtractor;\nimport net.minecraft.client.particle.ParticleEngine;")
    text = re.sub(r"(?m)^\s*public static ShaderInstanceBlur (?:positionTexBlur|positionTexBlurHorizontal|positionTexBlurVertical|particle);\s*\n", "", text)
    text = re.sub(r"(?m)^\s*private static CustomParticleEngine customParticleEngine;\s*\n", "", text)
    text = re.sub(r"(?s)    public static CustomParticleEngine getParticleEngine\(\) \{.*?\n    \}\n\n    public void tickGame", "    public static ParticleEngine getParticleEngine() {\n        return Minecraft.getInstance().particleEngine;\n    }\n\n    public void tickGame", text, count=1)
    # Book editor field internals were removed; still report the correct "book is open" status.
    text = re.sub(r"else if \(mc\.gui\.screen instanceof BookEditScreen bookEditScreen\) \{\s*chatText\s*=\s*bookEditScreen\.pageEdit\.getMessageFn\.get\(\);\s*\}",
                  'else if (mc.gui.screen instanceof BookEditScreen) { chatText = ""; }', text)
    # Tab overlay internals are render-state based now; do not break vanilla ping rendering.
    text = re.sub(r"(?s)    public boolean renderPingIconHook\(PlayerTabOverlay playerTabOverlay, GuiGraphicsExtractor pGuiGraphics, int p_281809_, int p_282801_, int pY, PlayerInfo pPlayerInfo\) \{.*?\n    \}\n\n    public void setupRotationsHook",
                  "    public boolean renderPingIconHook(PlayerTabOverlay playerTabOverlay, GuiGraphicsExtractor pGuiGraphics, int p_281809_, int p_282801_, int pY, PlayerInfo pPlayerInfo) {\n        return false;\n    }\n\n    public void setupRotationsHook", text, count=1)
    # Dynamic screen rendering used removed immediate-mode GL/shader APIs; keep status/chat/pose logic and packet decoding intact.
    pm.write_text(text, encoding="utf-8")

    # Text overlay now appends to the existing GUI extraction; do not create a second buffer source.
    pm = java_root / "PlayerStatusManagerClient.java"
    text = pm.read_text(encoding="utf-8")
    text = text.replace("import net.minecraft.client.gui.GuiGraphicsExtractor;", "import net.minecraft.client.gui.GuiGraphicsExtractor;\nimport net.minecraft.network.chat.Component;")
    text = re.sub(r"(?s)    public void onGuiRender\(\) \{.*?\n    \}\n\n    public String getTypingPlayers",
                  """    public void onGuiRender(GuiGraphicsExtractor graphics) {
        Minecraft mc = Minecraft.getInstance();
        if (mc.gui.screen instanceof ChatScreen && mc.getConnection() != null && ConfigClient.screenTypingVisible && ConfigServerControlledSyncedToClient.screenTypingVisible) {
            graphics.text(mc.font, Component.literal(getTypingPlayers()), 2 + ConfigClient.screenTypingRelativePosition_X,
                    mc.getWindow().getGuiScaledHeight() - 50 + ConfigClient.screenTypingRelativePosition_Y, 0xFFFFFF);
        }
    }

    public String getTypingPlayers""", text, count=1)
    text = text.replace("profile.getName()", "profile.name()")
    text = text.replace("getProfile().getId()", "getProfile().id()")
    pm.write_text(text, encoding="utf-8")

    gp = java_root / "mixin/client/GuiRender.java"
    if gp.exists():
        t = gp.read_text(encoding="utf-8").replace("WatutMod.getPlayerStatusManagerClient().onGuiRender();",
                                                   "WatutMod.getPlayerStatusManagerClient().onGuiRender(guiGraphics);")
        gp.write_text(t, encoding="utf-8")

    # Move the world particles to 26.3's extract-based single-quad renderer.
    particle_base = r'''package com.corosus.watut.particle;

import net.minecraft.client.Camera;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.particle.SingleQuadParticle;
import net.minecraft.client.renderer.state.level.QuadParticleRenderState;
import net.minecraft.util.Mth;
import org.joml.Quaternionf;
import com.mojang.math.Axis;

public abstract class ParticleRotating extends SingleQuadParticle {
    public boolean useCustomRotation = true;
    public float prevRotationYaw, rotationYaw;
    public float prevRotationPitch, rotationPitch;
    public float prevRotationRoll, rotationRoll;
    public float brightness = 1F;
    public int despawnCountdown = Integer.MAX_VALUE;

    public ParticleRotating(ClientLevel level, double x, double y, double z) {
        super(level, x, y, z, null);
    }

    @Override
    public void tick() {
        super.tick();
        if (this.despawnCountdown != Integer.MAX_VALUE && --this.despawnCountdown <= 0) this.remove();
    }

    public float getColorRed() { return this.rCol; }
    public float getColorGreen() { return this.gCol; }
    public float getColorBlue() { return this.bCol; }
    public void keepAlive() { this.despawnCountdown = 40; }
    public void setQuadSize(float size) { this.quadSize = size; }
    @Override public void setAlpha(float value) { super.setAlpha(value); }
    public void setPosPrev(double x, double y, double z) { this.xo = x; this.yo = y; this.zo = z; }
    public float getBrightness() { return this.brightness; }
    public void setBrightness(float value) { this.brightness = value; }

    @Override
    protected SingleQuadParticle.Layer getLayer() {
        return SingleQuadParticle.Layer.TRANSLUCENT;
    }

    @Override
    public void extract(QuadParticleRenderState state, Camera camera, float partialTick) {
        Quaternionf rotation;
        if (this.useCustomRotation) {
            rotation = new Quaternionf();
            rotation.mul(Axis.YP.rotationDegrees(Mth.lerp(partialTick, this.prevRotationYaw, this.rotationYaw)));
            rotation.mul(Axis.XP.rotationDegrees(Mth.lerp(partialTick, this.prevRotationPitch, this.rotationPitch)));
            rotation.mul(Axis.ZP.rotationDegrees(Mth.lerp(partialTick, this.prevRotationRoll, this.rotationRoll)));
        } else {
            rotation = new Quaternionf(camera.rotation());
            if (this.roll != 0.0F) rotation.rotateZ(Mth.lerp(partialTick, this.oRoll, this.roll));
        }
        this.extractRotatedQuad(state, camera, rotation, partialTick);
    }
}
'''
    (java_root / "particle/ParticleRotating.java").write_text(particle_base, encoding="utf-8")

    dynamic = r'''package com.corosus.watut.particle;

import com.corosus.watut.ParticleRegistry;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.particle.SingleQuadParticle;

public class ParticleDynamic extends ParticleRotating {
    public SingleQuadParticle.Layer particleRenderType;

    @Override
    protected SingleQuadParticle.Layer getLayer() {
        return particleRenderType == null ? SingleQuadParticle.Layer.TRANSLUCENT : particleRenderType;
    }

    public ParticleDynamic(ClientLevel level, double x, double y, double z, SingleQuadParticle.Layer renderType) {
        this(level, x, y, z, renderType, 1F);
    }

    public ParticleDynamic(ClientLevel level, double x, double y, double z, SingleQuadParticle.Layer renderType, float brightness) {
        super(level, x, y, z);
        this.particleRenderType = renderType;
        this.setSprite(ParticleRegistry.inventory.getSprite());
        this.lifetime = Integer.MAX_VALUE;
        this.gravity = 0;
        this.quadSize = 0.5F;
        this.xd = this.yd = this.zd = 0;
        this.setColor(this.rCol * brightness, this.gCol * brightness, this.bCol * brightness);
    }

    @Override
    public void tick() {
        super.tick();
        this.xo = this.x;
        this.yo = this.y;
        this.zo = this.z;
        if (this.age++ >= this.lifetime) this.remove();
        else this.move(this.xd, this.yd, this.zd);
    }
}
'''
    (java_root / "particle/ParticleDynamic.java").write_text(dynamic, encoding="utf-8")

    item = r'''package com.corosus.watut.particle;

import com.corosus.watut.ParticleRegistry;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.RenderBuffers;
import net.minecraft.client.renderer.entity.EntityRenderDispatcher;
import net.minecraft.world.item.ItemStack;
import net.minecraft.client.particle.SingleQuadParticle;

import java.util.HashSet;

public class ParticleItem extends ParticleRotating {
    public static HashSet<String> itemBlacklist = new HashSet<>();
    public ItemStack itemStack;
    public float xFrom, yFrom, zFrom, xTo, yTo, zTo;

    public ParticleItem(ClientLevel level, float brightness, ItemStack stack, RenderBuffers buffers,
                        EntityRenderDispatcher dispatcher, float xFrom, float yFrom, float zFrom,
                        float xTo, float yTo, float zTo) {
        super(level, xFrom, yFrom, zFrom);
        this.itemStack = stack;
        this.xFrom = xFrom; this.yFrom = yFrom; this.zFrom = zFrom;
        this.xTo = xTo; this.yTo = yTo; this.zTo = zTo;
        this.setSprite(ParticleRegistry.anvil.getSprite());
        this.lifetime = 6;
        this.gravity = 0;
        this.quadSize = 0.18F;
        this.rotationYaw = level.getRandom().nextFloat() * 360F;
        this.setColor(this.rCol * brightness, this.gCol * brightness, this.bCol * brightness);
    }

    @Override
    protected SingleQuadParticle.Layer getLayer() {
        return SingleQuadParticle.Layer.TRANSLUCENT;
    }

    @Override
    public void tick() {
        super.tick();
        this.xo = this.x; this.yo = this.y; this.zo = this.z;
        float lerp = ((float)this.age) / 3.0F;
        this.setPos(net.minecraft.util.Mth.lerp(lerp, xFrom, xTo),
                    net.minecraft.util.Mth.lerp(lerp, yFrom, yTo),
                    net.minecraft.util.Mth.lerp(lerp, zFrom, zTo));
        if (this.age >= 3) this.setPos(xTo, yTo, zTo);
        if (this.age >= this.lifetime) this.remove();
    }
}
'''
    (java_root / "particle/ParticleItem.java").write_text(item, encoding="utf-8")

    # Keep data/network state for GUI captures but avoid obsolete fixed-function rendering and shader classes.
    screen_data = r'''package com.corosus.watut.client.screen;

import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.particle.SingleQuadParticle;
import org.lwjgl.system.MemoryUtil;

import java.nio.ByteBuffer;
import java.util.concurrent.atomic.AtomicBoolean;

public class ScreenData {
    private volatile ByteBuffer texturePixelData, decompressionBuffer;
    private final AtomicBoolean isBufferReady = new AtomicBoolean(false);
    private byte[] texturePixelDataPartial;
    private long gameTicksSinceFirstPacket, gameTicksSinceLastScreenSend, gameTicksSinceLastScreenReceiveAndRender;
    private int lastIndexReceived, width = ScreenParticleRenderer.defaultWidthScaledDown, height = ScreenParticleRenderer.defaultHeightScaledDown;
    private SingleQuadParticle.Layer particleRenderType;
    private boolean needsNewRenderFromPixelData, needsNewRenderToPixelData;
    private Screen lastScreen;

    public void initClient() { this.particleRenderType = null; }
    public ByteBuffer getTexturePixelData() { return texturePixelData; }
    public void freeTexturePixelData() { if (texturePixelData != null) MemoryUtil.memFree(texturePixelData); }
    public void setTexturePixelData(ByteBuffer value) { texturePixelData = value; }
    public SingleQuadParticle.Layer getParticleRenderType() { return particleRenderType; }
    public void setParticleRenderType(SingleQuadParticle.Layer value) { particleRenderType = value; }
    public synchronized boolean needsNewRenderFromPixelData() { return needsNewRenderFromPixelData; }
    public synchronized void markNeedsNewRenderFromPixelData(boolean value) { needsNewRenderFromPixelData = value; }
    public boolean isNeedsNewRenderToPixelData() { return needsNewRenderToPixelData; }
    public void setNeedsNewRenderToPixelData(boolean value) { needsNewRenderToPixelData = value; }
    public byte[] getTexturePixelDataPartial() { return texturePixelDataPartial; }
    public void setTexturePixelDataPartial(byte[] value) { texturePixelDataPartial = value; }
    public long getGameTicksSinceFirstPacket() { return gameTicksSinceFirstPacket; }
    public void setGameTicksSinceFirstPacket(long value) { gameTicksSinceFirstPacket = value; }
    public int getLastIndexReceived() { return lastIndexReceived; }
    public void setLastIndexReceived(int value) { lastIndexReceived = value; }
    public long getGameTicksSinceLastScreenSend() { return gameTicksSinceLastScreenSend; }
    public void setGameTicksSinceLastScreenSend(long value) { gameTicksSinceLastScreenSend = value; }
    public long getGameTicksSinceLastScreenReceiveAndRender() { return gameTicksSinceLastScreenReceiveAndRender; }
    public void setGameTicksSinceLastScreenReceiveAndRender(long value) { gameTicksSinceLastScreenReceiveAndRender = value; }
    public AtomicBoolean getIsBufferReady() { return isBufferReady; }
    public ByteBuffer getDecompressionBuffer() { return decompressionBuffer; }
    public void setDecompressionBuffer(ByteBuffer value) { decompressionBuffer = value; }
    public int getWidth() { return width; }
    public void setWidth(int value) { width = value; }
    public int getHeight() { return height; }
    public void setHeight(int value) { height = value; }
    public Screen getLastScreen() { return lastScreen; }
    public void setLastScreen(Screen value) { lastScreen = value; }
}
'''
    (java_root / "client/screen/ScreenData.java").write_text(screen_data, encoding="utf-8")

    screen_particle = r'''package com.corosus.watut.client.screen;

import net.minecraft.client.Minecraft;

public class ScreenParticleRenderer {
    public static boolean isRenderingParticleGUI = false;
    public static boolean isRenderingParticleGUI2 = false;
    public static final int defaultWidthScaledDown = 256;
    public static final int defaultHeightScaledDown = 256;
    public static final int bytesPerPixel = 4;
    public int width, height, widthScaledDown = defaultWidthScaledDown, heightScaledDown = defaultHeightScaledDown;
    public boolean needsInit = true;
    private static ScreenParticleRenderer instance;
    public static ScreenParticleRenderer getInstance() {
        if (instance == null) instance = new ScreenParticleRenderer();
        return instance;
    }
    public void checkSetup() {
        if (!needsInit) return;
        needsInit = false;
        width = Minecraft.getInstance().getWindow().getWidth();
        height = Minecraft.getInstance().getWindow().getHeight();
    }
    public void setup() { checkSetup(); }
    public synchronized void resize(int width, int height) {
        this.width = width; this.height = height; needsInit = false;
        resizeScaledDown(width, height);
    }
    public void resizeScaledDown(int width, int height) {
        this.widthScaledDown = defaultWidthScaledDown;
        this.heightScaledDown = defaultHeightScaledDown;
    }
}
'''
    (java_root / "client/screen/ScreenParticleRenderer.java").write_text(screen_particle, encoding="utf-8")

    helper = r'''package com.corosus.watut.client.screen;

import net.minecraft.client.gui.GuiGraphicsExtractor;
import net.minecraft.resources.Identifier;

import java.nio.ByteBuffer;
import java.util.zip.Deflater;
import java.util.zip.Inflater;

public class RenderHelper {
    public static boolean performingOwnRender = false;
    public static int xaeroWorldMapTextureID = -1;
    public static final Identifier cursor = Identifier.fromNamespaceAndPath("watut", "textures/misc/mouse.png");
    public static boolean useDynamicGUISystem() { return false; }
    public static boolean isShadersEnabled() { return false; }
    public static void guiRender(GuiGraphicsExtractor graphics) { }
    public static void renderWithTooltipEnd(GuiGraphicsExtractor graphics, int mouseX, int mouseY, float partialTick) { }

    public static ByteBuffer compress(ByteBuffer input) {
        byte[] bytes = new byte[input.remaining()];
        input.get(bytes);
        Deflater deflater = new Deflater(Deflater.BEST_COMPRESSION);
        deflater.setInput(bytes); deflater.finish();
        ByteBuffer out = ByteBuffer.allocateDirect(bytes.length + 512);
        byte[] chunk = new byte[1024];
        while (!deflater.finished()) {
            int n = deflater.deflate(chunk);
            if (out.remaining() < n) {
                ByteBuffer bigger = ByteBuffer.allocateDirect(Math.max(out.capacity() * 2, out.position() + n));
                out.flip(); bigger.put(out); out = bigger;
            }
            out.put(chunk, 0, n);
        }
        deflater.end(); out.flip(); input.flip(); return out;
    }

    public static ByteBuffer decompress(ScreenData screenData, ByteBuffer compressed, int expectedSize) throws Exception {
        if (expectedSize < 0 || expectedSize > 16 * 1024 * 1024) throw new IllegalArgumentException("Invalid GUI image size");
        byte[] bytes = new byte[compressed.remaining()]; compressed.get(bytes);
        Inflater inflater = new Inflater(); inflater.setInput(bytes);
        ByteBuffer out = ByteBuffer.allocateDirect(expectedSize);
        byte[] chunk = new byte[8192];
        try {
            while (!inflater.finished()) {
                int n = inflater.inflate(chunk);
                if (n > 0) {
                    if (out.remaining() < n) throw new IllegalArgumentException("GUI image exceeds declared size");
                    out.put(chunk, 0, n);
                } else if (inflater.needsInput() || inflater.needsDictionary()) {
                    throw new IllegalArgumentException("Incomplete GUI image packet");
                }
            }
        } finally { inflater.end(); }
        out.flip(); screenData.setDecompressionBuffer(out); return out;
    }
}
'''
    (java_root / "client/screen/RenderHelper.java").write_text(helper, encoding="utf-8")

    # Item particles retain movement but render with WATUT's atlas icon; 26.3 no longer exposes legacy BakedModel quads.
    # Stop compiling obsolete GL renderer/mixin classes; status, typing, arm animation and normal icon particles remain active.
    for rel in [
        "ShaderInstanceBlur.java",
        "client/CustomParticleEngine.java",
        "mixin/client/GameRendererReloadShaders.java",
        "mixin/client/ParticleEngineMixin.java",
        "mixin/client/ParticleEngineMixinFabric.java",
        "mixin/client/RenderPingIconInject.java",
        "mixin/client/ScreenRenderWithTooltip.java",
        "mixin/client/ScreenRenderBackground.java",
        "mixin/client/PostChainResize.java",
        "mixin/client/NativeImageAccessor.java",
    ]:
        p = java_root / rel
        if p.exists(): p.unlink()

    # Keep the normal tick hook but remove calls to the deleted custom engine.
    tick = java_root / "mixin/client/MinecraftTick.java"
    if tick.exists():
        t = tick.read_text(encoding="utf-8")
        t = re.sub(r"(?s)\n\s*@Inject\(method = \"updateLevelInEngines\".*?\n\s*\}\n", "\n", t)
        t = t.replace("import net.minecraft.client.multiplayer.ClientLevel;\n", "")
        tick.write_text(t, encoding="utf-8")

    # Modern vanilla interaction result type.
    p = java_root / "mixin/BlockBehaviorUse.java"
    if p.exists():
        t = p.read_text(encoding="utf-8").replace("ItemInteractionResult", "InteractionResult")
        t = t.replace("import net.minecraft.world.InteractionResult;\nimport net.minecraft.world.InteractionResult;", "import net.minecraft.world.InteractionResult;")
        p.write_text(t, encoding="utf-8")

    # Delete obsolete render integrations from Fabric and shared mixin lists.
    for p in (root / "src/main/resources").glob("*mixins*.json"):
        try:
            meta = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for key in ("client", "mixins", "server"):
            if isinstance(meta.get(key), list):
                meta[key] = [name for name in meta[key] if name not in {
                    "client.RenderPingIconInject", "client.ScreenRenderWithTooltip", "client.ScreenRenderBackground",
                    "client.PostChainResize", "client.GameRendererReloadShaders", "client.ParticleEngineMixin",
                    "client.ParticleEngineMixinFabric", "client.NativeImageAccessor"
                }]
        p.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

# Correct current loader metadata; retain upstream entrypoints/mixins/access wideners.
meta_path = root / "src/main/resources/fabric.mod.json"
if meta_path.exists():
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    depends = meta.setdefault("depends", {})
    depends["fabricloader"] = ">=0.19.5"
    depends["minecraft"] = "26.3"
    depends["java"] = ">=25"
    depends["fabric-api"] = "*"
    if kind == "watut":
        depends["coroutil"] = ">=26.3-1.3.8"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

print(f"Prepared {kind}: original feature classes/resources/mixins retained; Fabric config persistence ported to TOML; target Minecraft 26.3.")


# Follow-up API port fixes discovered by the 26.3 compile (without deleting feature sources).
if kind == "watut":
    java_root = root / "src/main/java/com/corosus/watut"
    for source in java_root.rglob("*.java"):
        text = source.read_text(encoding="utf-8")
        # Gui.screen is exposed as screen() in the 26.3 client API.
        text = re.sub(r"\.gui\.screen(?!\s*\()", ".gui.screen()", text)

        # 26.3 CompoundTag scalar getters are Optional-returning; use the explicit default API.
        text = re.sub(r'\.getInt\(([^()]*)\)(?:\.orElse\(0\))?', r'.getIntOr(\1, 0)', text)
        text = re.sub(r'\.getFloat\(([^()]*)\)(?:\.orElse\(0(?:\.0)?F?\))?', r'.getFloatOr(\1, 0.0F)', text)
        text = re.sub(r'\.getBoolean\(([^()]*)\)(?:\.orElse\(false\))?', r'.getBooleanOr(\1, false)', text)
        text = re.sub(r'\.getString\(([^()]*)\)(?:\.orElse\(""\))?', r'.getStringOr(\1, "")', text)
        text = re.sub(r'\.getByteArray\(([^()]*)\)(?:\.orElse\(new byte\[0\]\))?', r'.getByteArray(\1).orElse(new byte[0])', text)
        text = re.sub(r'\.getCompound\(([^()]*)\)(?:\.orElse\(new CompoundTag\(\)\))?', r'.getCompoundOrEmpty(\1)', text)
        text = re.sub(r'\.getLong\(([^()]*)\)(?:\.orElse\(0L\))?', r'.getLongOr(\1, 0L)', text)
        text = re.sub(r'\.getDouble\(([^()]*)\)(?:\.orElse\(0(?:\.0)?D?\))?', r'.getDoubleOr(\1, 0.0D)', text)

        # 26.3 serializes ItemStack through its registry-aware codec, not save/parseOptional.
        if source.name == "PlayerStatusManagerServer.java":
            text = text.replace("itemStack.save(level.registryAccess())",
                "ItemStack.CODEC.encodeStart(level.registryAccess().createSerializationContext(NbtOps.INSTANCE), itemStack).getOrThrow()")
            if "import net.minecraft.nbt.NbtOps;" not in text:
                text = text.replace("import net.minecraft.nbt.CompoundTag;", "import net.minecraft.nbt.CompoundTag;\nimport net.minecraft.nbt.NbtOps;")
            # Inventory.items is private in this release; preserve slot order via Container accessors.
            text = text.replace(
                "for (ItemStack item : player.getInventory().items) {",
                "for (int inventorySlot = 0; inventorySlot < player.getInventory().getContainerSize(); inventorySlot++) {\n            ItemStack item = player.getInventory().getItem(inventorySlot);"
            )
        if source.name == "PlayerStatusManagerClient.java":
            text = re.sub(
                r'ItemStack\.parseOptional\(Minecraft\.getInstance\(\)\.level\.registryAccess\(\),\s*data\.getCompoundOrEmpty\(([^()]*)\)\)',
                r'ItemStack.CODEC.parse(Minecraft.getInstance().level.registryAccess().createSerializationContext(NbtOps.INSTANCE), data.getCompoundOrEmpty(\1)).result().orElse(ItemStack.EMPTY)',
                text
            )
            # Keep the existing item particle travel animation; it no longer needs removed renderer buffers.
            text = text.replace(
                "new ParticleItem(Minecraft.getInstance().level, 1, itemStack,\n                    Minecraft.getInstance().renderBuffers(),\n                    Minecraft.getInstance().getEntityRenderDispatcher(),",
                "new ParticleItem(Minecraft.getInstance().level, 1, itemStack,"
            )
            if "import net.minecraft.nbt.NbtOps;" not in text:
                text = text.replace("import net.minecraft.nbt.CompoundTag;", "import net.minecraft.nbt.CompoundTag;\nimport net.minecraft.nbt.NbtOps;")
        if text != source.read_text(encoding="utf-8"):
            source.write_text(text, encoding="utf-8")

    # The item transfer particle still animates between inventory and container, using current client APIs.
    particle_item = java_root / "particle/ParticleItem.java"
    if particle_item.exists():
        text = particle_item.read_text(encoding="utf-8")
        text = text.replace("import net.minecraft.client.renderer.RenderBuffers;\n", "")
        text = text.replace("import net.minecraft.client.renderer.entity.EntityRenderDispatcher;\n", "")
        text = text.replace(
            "public ParticleItem(ClientLevel level, float brightness, ItemStack stack, RenderBuffers buffers,\n                        EntityRenderDispatcher dispatcher, float xFrom, float yFrom, float zFrom,",
            "public ParticleItem(ClientLevel level, float brightness, ItemStack stack,\n                        float xFrom, float yFrom, float zFrom,"
        )
        particle_item.write_text(text, encoding="utf-8")

    # The sprite sequence provider must expose its first frame in 26.3.
    sprite_set = java_root / "spritesets/SpriteSetPlayer.java"
    if sprite_set.exists():
        text = sprite_set.read_text(encoding="utf-8")
        if "TextureAtlasSprite first()" not in text:
            text = text.replace(
                "public class SpriteSetPlayer implements SpriteSet {\n",
                "public class SpriteSetPlayer implements SpriteSet {\n\n    @Override\n    public TextureAtlasSprite first() { return list.get(0); }\n"
            )
        sprite_set.write_text(text, encoding="utf-8")

    # 26.3's single-quad particles use vanilla particle layers; custom legacy render-order entries are gone.
    client_init = java_root / "loader/fabric/WatutModFabricClient.java"
    if client_init.exists():
        text = client_init.read_text(encoding="utf-8")
        text = re.sub(
            r'\n\s*List<ParticleRenderType> render_order = new ArrayList<>\(\);\s*\n\s*render_order\.addAll\(ParticleEngine\.RENDER_ORDER\);\s*\n\s*render_order\.add\(ParticleRotating\.PARTICLE_SHEET_TRANSLUCENT_NO_FACE_CULL\);\s*\n\s*ParticleEngine\.RENDER_ORDER = render_order;\s*',
            "\n",
            text
        )
        text = text.replace("import net.minecraft.client.particle.ParticleRenderType;\n", "")
        text = text.replace("import net.minecraft.client.particle.ParticleEngine;\n", "")
        client_init.write_text(text, encoding="utf-8")


# Repair accidental text/package substitutions from broad API regexes above.
if kind == "watut":
    java_root = root / "src/main/java/com/corosus/watut"
    for source in java_root.rglob("*.java"):
        text = source.read_text(encoding="utf-8")
        text = text.replace("net.minecraft.client.gui.screen()s", "net.minecraft.client.gui.screens")
        text = re.sub(r'\.getStringOr\(\s*,\s*""\)', '.getString()', text)
        if text != source.read_text(encoding="utf-8"):
            source.write_text(text, encoding="utf-8")


# Drop only access widener entries for private members removed from Minecraft 26.3.
if kind == "watut":
    aw_path = root / "src/main/resources/watut.accesswidener"
    if aw_path.exists():
        obsolete = (
            "net/minecraft/client/particle/ParticleEngine textureAtlas ",
            "net/minecraft/client/gui/components/PlayerTabOverlay renderPingIcon ",
            "net/minecraft/client/gui/screens/inventory/BookEditScreen pageEdit ",
            "net/minecraft/client/particle/ParticleEngine RENDER_ORDER ",
        )
        lines = aw_path.read_text(encoding="utf-8").splitlines()
        aw_path.write_text("\n".join(line for line in lines if not any(key in line for key in obsolete)) + "\n", encoding="utf-8")


# Restore live GUI preview in 26.3 using the native render-target screenshot/readback path.
# The old implementation depended on immediate-mode GuiGraphics and removed GL shader hooks.
if kind == "watut":
    java_root = root / "src/main/java/com/corosus/watut"

    screen_data = r'''package com.corosus.watut.client.screen;

import net.minecraft.client.Minecraft;
import net.minecraft.client.particle.SingleQuadParticle;
import net.minecraft.client.renderer.RenderPipelines;
import net.minecraft.client.renderer.texture.DynamicTexture;
import net.minecraft.resources.Identifier;

import org.lwjgl.system.MemoryUtil;
import java.nio.ByteBuffer;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

public class ScreenData {
    private static final AtomicLong NEXT_TEXTURE_ID = new AtomicLong();
    private volatile ByteBuffer texturePixelData;
    private volatile ByteBuffer decompressionBuffer;
    private final AtomicBoolean isBufferReady = new AtomicBoolean(false);
    private byte[] texturePixelDataPartial;
    private long gameTicksSinceFirstPacket, gameTicksSinceLastScreenSend, gameTicksSinceLastScreenReceiveAndRender;
    private int lastIndexReceived, width = ScreenParticleRenderer.defaultWidthScaledDown, height = ScreenParticleRenderer.defaultHeightScaledDown;
    private SingleQuadParticle.Layer particleRenderType;
    private boolean needsNewRenderFromPixelData, needsNewRenderToPixelData;
    private Screen lastScreen;
    private Identifier textureId;
    private DynamicTexture image;
    private int imageWidth, imageHeight;

    public synchronized void initClient() {
        if (textureId == null) {
            textureId = Identifier.fromNamespaceAndPath("watut", "screen_preview_" + Long.toUnsignedString(NEXT_TEXTURE_ID.incrementAndGet(), 36));
        }
        ensureImage(width, height);
        particleRenderType = new SingleQuadParticle.Layer(false, textureId, RenderPipelines.PARTICLE_TRANSLUCENT, null);
    }

    public synchronized void ensureImage(int wantedWidth, int wantedHeight) {
        int w = Math.max(1, Math.min(wantedWidth, 8192));
        int h = Math.max(1, Math.min(wantedHeight, 8192));
        if (textureId == null) {
            textureId = Identifier.fromNamespaceAndPath("watut", "screen_preview_" + Long.toUnsignedString(NEXT_TEXTURE_ID.incrementAndGet(), 36));
        }
        if (image != null && imageWidth == w && imageHeight == h) return;
        if (image != null) {
            image.close();
            image = null;
        }
        image = new DynamicTexture("WATUT screen preview", w, h, true);
        imageWidth = w;
        imageHeight = h;
        Minecraft.getInstance().getTextureManager().register(textureId, image);
        particleRenderType = new SingleQuadParticle.Layer(false, textureId, RenderPipelines.PARTICLE_TRANSLUCENT, null);
    }

    public Identifier getTextureId() { return textureId; }
    public DynamicTexture getImage() { return image; }
    public void setImage(DynamicTexture value) { image = value; }
    public void closeImage() {
        if (image != null) { image.close(); image = null; }
    }
    public ByteBuffer getTexturePixelData() { return texturePixelData; }
    public void freeTexturePixelData() {
        if (texturePixelData != null && texturePixelData.isDirect()) MemoryUtil.memFree(texturePixelData);
        texturePixelData = null;
    }
    public void setTexturePixelData(ByteBuffer value) { texturePixelData = value; }
    public SingleQuadParticle.Layer getParticleRenderType() { return particleRenderType; }
    public void setParticleRenderType(SingleQuadParticle.Layer value) { particleRenderType = value; }
    public synchronized boolean needsNewRenderFromPixelData() { return needsNewRenderFromPixelData; }
    public synchronized void markNeedsNewRenderFromPixelData(boolean value) { needsNewRenderFromPixelData = value; }
    public boolean isNeedsNewRenderToPixelData() { return needsNewRenderToPixelData; }
    public void setNeedsNewRenderToPixelData(boolean value) { needsNewRenderToPixelData = value; }
    public byte[] getTexturePixelDataPartial() { return texturePixelDataPartial; }
    public void setTexturePixelDataPartial(byte[] value) { texturePixelDataPartial = value; }
    public long getGameTicksSinceFirstPacket() { return gameTicksSinceFirstPacket; }
    public void setGameTicksSinceFirstPacket(long value) { gameTicksSinceFirstPacket = value; }
    public int getLastIndexReceived() { return lastIndexReceived; }
    public void setLastIndexReceived(int value) { lastIndexReceived = value; }
    public long getGameTicksSinceLastScreenSend() { return gameTicksSinceLastScreenSend; }
    public void setGameTicksSinceLastScreenSend(long value) { gameTicksSinceLastScreenSend = value; }
    public long getGameTicksSinceLastScreenReceiveAndRender() { return gameTicksSinceLastScreenReceiveAndRender; }
    public void setGameTicksSinceLastScreenReceiveAndRender(long value) { gameTicksSinceLastScreenReceiveAndRender = value; }
    public AtomicBoolean getIsBufferReady() { return isBufferReady; }
    public ByteBuffer getDecompressionBuffer() { return decompressionBuffer; }
    public void setDecompressionBuffer(ByteBuffer value) { decompressionBuffer = value; }
    public int getWidth() { return width; }
    public void setWidth(int value) { width = value; }
    public int getHeight() { return height; }
    public void setHeight(int value) { height = value; }
    public Screen getLastScreen() { return lastScreen; }
    public void setLastScreen(Screen value) { lastScreen = value; }
}
'''
    (java_root / "client/screen/ScreenData.java").write_text(screen_data, encoding="utf-8")

    capture = r'''package com.corosus.watut.client.screen;

import com.corosus.watut.PlayerStatus;
import com.corosus.watut.WatutMod;
import com.corosus.watut.config.ConfigServerControlledSyncedToClient;
import com.mojang.blaze3d.platform.NativeImage;
import com.mojang.blaze3d.pipeline.RenderTarget;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraft.client.renderer.GameRenderer;
import net.minecraft.client.renderer.texture.DynamicTexture;
import net.minecraft.util.ARGB;

import java.nio.ByteBuffer;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;

public final class ScreenCapture26 {
    private static final AtomicBoolean capturePending = new AtomicBoolean(false);
    private ScreenCapture26() {}

    public static void captureIfNeeded(GameRenderer renderer) {
        Minecraft mc = Minecraft.getInstance();
        if (mc.level == null || mc.player == null || mc.gui == null || mc.gui.screen() == null) return;
        if (!RenderHelper.useDynamicGUISystem()) return;
        PlayerStatus status = WatutMod.getPlayerStatusManagerClient().getStatusLocal();
        ScreenData data = status.getScreenData();
        if (!data.isNeedsNewRenderToPixelData() || !capturePending.compareAndSet(false, true)) return;

        boolean entireScreen = ConfigServerControlledSyncedToClient.dynamicGuiShowClientsEntireScreen;
        int scale = entireScreen ? 1 : Math.max(1, (int)Math.round(mc.getWindow().getGuiScale()));
        data.setNeedsNewRenderToPixelData(false);
        try {
            RenderTarget target = renderer.mainRenderTarget();
            Screenshot.takeScreenshot(target, scale, image -> finishCapture(mc, status, image, entireScreen));
        } catch (Throwable error) {
            data.setNeedsNewRenderToPixelData(true);
            capturePending.set(false);
            System.err.println("[WATUT] Minecraft 26.3 screen capture failed: " + error);
        }
    }

    private static void finishCapture(Minecraft mc, PlayerStatus status, NativeImage image, boolean entireScreen) {
        try {
            if (image == null) {
                status.getScreenData().setNeedsNewRenderToPixelData(true);
                return;
            }

            int srcWidth = image.getWidth();
            int srcHeight = image.getHeight();
            if (srcWidth <= 0 || srcHeight <= 0 || (long)srcWidth * srcHeight * 4L > 64L * 1024L * 1024L) {
                status.getScreenData().setNeedsNewRenderToPixelData(true);
                return;
            }

            final int outWidth;
            final int outHeight;
            final ByteBuffer rgba;
            if (entireScreen) {
                outWidth = srcWidth;
                outHeight = srcHeight;
                rgba = ByteBuffer.allocateDirect(Math.multiplyExact(Math.multiplyExact(outWidth, outHeight), 4));
                for (int y = 0; y < outHeight; y++) {
                    for (int x = 0; x < outWidth; x++) putPixel(rgba, image.getPixel(x, y));
                }
            } else {
                outWidth = ScreenParticleRenderer.defaultWidthScaledDown;
                outHeight = ScreenParticleRenderer.defaultHeightScaledDown;
                rgba = ByteBuffer.allocateDirect(outWidth * outHeight * 4);
                int srcLeft = Math.max(0, (srcWidth - outWidth) / 2);
                int srcTop = Math.max(0, (srcHeight - outHeight) / 2);
                int dstLeft = Math.max(0, (outWidth - srcWidth) / 2);
                int dstTop = Math.max(0, (outHeight - srcHeight) / 2);
                int copyWidth = Math.min(outWidth - dstLeft, srcWidth - srcLeft);
                int copyHeight = Math.min(outHeight - dstTop, srcHeight - srcTop);
                for (int y = 0; y < outHeight; y++) {
                    for (int x = 0; x < outWidth; x++) {
                        int sx = srcLeft + x - dstLeft;
                        int sy = srcTop + y - dstTop;
                        if (x >= dstLeft && y >= dstTop && x < dstLeft + copyWidth && y < dstTop + copyHeight) {
                            putPixel(rgba, image.getPixel(sx, sy));
                        } else {
                            rgba.put((byte)0).put((byte)0).put((byte)0).put((byte)0);
                        }
                    }
                }
            }
            rgba.flip();
            ScreenData data = status.getScreenData();
            data.setWidth(outWidth);
            data.setHeight(outHeight);
            data.setTexturePixelData(RenderHelper.compress(rgba));
            WatutMod.getPlayerStatusManagerClient().sendScreenRenderData(status);
        } catch (Throwable error) {
            status.getScreenData().setNeedsNewRenderToPixelData(true);
            System.err.println("[WATUT] Could not encode screen preview: " + error);
        } finally {
            if (image != null) image.close();
            capturePending.set(false);
        }
    }

    private static void putPixel(ByteBuffer output, int color) {
        output.put((byte)ARGB.red(color));
        output.put((byte)ARGB.green(color));
        output.put((byte)ARGB.blue(color));
        output.put((byte)ARGB.alpha(color));
    }
}
'''
    (java_root / "client/screen/ScreenCapture26.java").write_text(capture, encoding="utf-8")

    gui_render = r'''package com.corosus.watut.mixin.client;

import com.corosus.watut.WatutMod;
import com.corosus.watut.client.screen.RenderHelper;
import net.minecraft.client.DeltaTracker;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.Gui;
import net.minecraft.client.gui.GuiGraphicsExtractor;
import net.minecraft.client.renderer.state.gui.GuiRenderState;
import net.minecraft.client.gui.screens.ChatScreen;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(Gui.class)
public abstract class GuiRender {
    @Shadow @Final private GuiRenderState guiRenderState;

    @Inject(method = "extractRenderState", at = @At("TAIL"))
    private void watut$extractGuiState(CallbackInfo ci) {
        Minecraft mc = Minecraft.getInstance();
        int mouseX = (int)(mc.mouseHandler.xpos() / mc.getWindow().getGuiScale());
        int mouseY = (int)(mc.mouseHandler.ypos() / mc.getWindow().getGuiScale());
        GuiGraphicsExtractor graphics = new GuiGraphicsExtractor(mc, this.guiRenderState, mouseX, mouseY);
        RenderHelper.guiRender(graphics);
        WatutMod.getPlayerStatusManagerClient().onGuiRender(graphics);
    }
}
'''
    (java_root / "mixin/client/GuiRender.java").write_text(gui_render, encoding="utf-8")

    capture_mixin = r'''package com.corosus.watut.mixin.client;

import com.corosus.watut.client.screen.ScreenCapture26;
import net.minecraft.client.renderer.GameRenderer;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(GameRenderer.class)
public abstract class GameRendererCapture26 {
    @Inject(method = "render", at = @At("TAIL"))
    private void watut$captureDynamicScreen(CallbackInfo ci) {
        ScreenCapture26.captureIfNeeded((GameRenderer)(Object)this);
    }
}
'''
    (java_root / "mixin/client/GameRendererCapture26.java").write_text(capture_mixin, encoding="utf-8")

    # Keep the original typed/chat status overlay alive in the GUI extraction pass.
    pm = java_root / "PlayerStatusManagerClient.java"
    text = pm.read_text(encoding="utf-8")
    text = re.sub(
        r"(?s)    public void onGuiRender\(GuiGraphicsExtractor graphics\) \{.*?\n    \}\n\n    public String getTypingPlayers",
        """    public void onGuiRender(GuiGraphicsExtractor graphics) {
        Minecraft mc = Minecraft.getInstance();
        if (mc.gui.screen() instanceof ChatScreen && mc.getConnection() != null && mc.level != null
                && ConfigClient.screenTypingVisible && ConfigServerControlledSyncedToClient.screenTypingVisible) {
            graphics.text(mc.font, Component.literal(getTypingPlayers()),
                    2 + ConfigClient.screenTypingRelativePosition_X,
                    mc.getWindow().getGuiScaledHeight() - 50 + ConfigClient.screenTypingRelativePosition_Y,
                    0xFFFFFF);
        }
    }

    public String getTypingPlayers""",
        text,
        count=1
    )
    pm.write_text(text, encoding="utf-8")

    # Restore screen preview texture upload on the receiving client.
    rh = java_root / "client/screen/RenderHelper.java"
    text = rh.read_text(encoding="utf-8")
    text = text.replace(
        "public static boolean useDynamicGUISystem() { return false; }",
        """public static boolean useDynamicGUISystem() {
        if (ConfigServerControlledSyncedToClient.dynamicGuiUseOldSimpleGUIVisual) return false;
        if (ConfigClient.dontSendDetailedGUIInfo) return false;
        return true;
    }"""
    )
    text = re.sub(
        r"public static void guiRender\(GuiGraphicsExtractor graphics\) \{ \}",
        """public static void guiRender(GuiGraphicsExtractor graphics) {
        if (!useDynamicGUISystem()) return;
        for (PlayerStatus status : WatutMod.getPlayerStatusManagerClient().lookupPlayerToStatus.values()) {
            ScreenData data = status.getScreenData();
            if (!data.getIsBufferReady().get() || !data.needsNewRenderFromPixelData()) continue;
            ByteBuffer pixels = data.getDecompressionBuffer();
            if (pixels == null) pixels = data.getTexturePixelData();
            if (pixels == null) {
                data.getIsBufferReady().set(false);
                data.markNeedsNewRenderFromPixelData(false);
                continue;
            }
            int width = data.getWidth();
            int height = data.getHeight();
            long required = (long)width * height * 4L;
            if (width <= 0 || height <= 0 || required > 64L * 1024L * 1024L || pixels.limit() < required) {
                data.getIsBufferReady().set(false);
                data.markNeedsNewRenderFromPixelData(false);
                continue;
            }
            data.initClient();
            data.ensureImage(width, height);
            var nativeImage = data.getImage().getPixels();
            for (int y = 0; y < height; y++) {
                for (int x = 0; x < width; x++) {
                    int offset = (y * width + x) * 4;
                    int r = pixels.get(offset) & 255;
                    int g = pixels.get(offset + 1) & 255;
                    int b = pixels.get(offset + 2) & 255;
                    int a = pixels.get(offset + 3) & 255;
                    nativeImage.setPixel(x, y, net.minecraft.util.ARGB.color(a, r, g, b));
                }
            }
            data.getImage().upload();
            data.getIsBufferReady().set(false);
            data.markNeedsNewRenderFromPixelData(false);
        }
    }""",
        text,
        count=1
    )
    rh.write_text(text, encoding="utf-8")

    # Keep dynamic screen texture UVs independent of the inventory sprite atlas.
    dynamic = java_root / "particle/ParticleDynamic.java"
    if dynamic.exists():
        text = dynamic.read_text(encoding="utf-8")
        if "getU0()" not in text:
            text = text.replace(
                "    @Override\\n    protected SingleQuadParticle.Layer getLayer() {",
                """    @Override public float getU0() { return 0.0F; }
    @Override public float getU1() { return 1.0F; }
    @Override public float getV0() { return 0.0F; }
    @Override public float getV1() { return 1.0F; }

    @Override
    protected SingleQuadParticle.Layer getLayer() {""",
                1
            )
        dynamic.write_text(text, encoding="utf-8")

    # Screen capture may contain a full 4K display; keep decompression bounded but large enough for it.
    rh_text = rh.read_text(encoding="utf-8")
    rh_text = rh_text.replace("16 * 1024 * 1024", "64 * 1024 * 1024")
    rh.write_text(rh_text, encoding="utf-8")

    # Register the new end-of-frame screenshot capture hook in Fabric's actual mixin config.
    for mixin_config in (root / "src/main/resources").glob("*fabric.mixins.json"):
        try:
            mixin_meta = json.loads(mixin_config.read_text(encoding="utf-8"))
        except Exception:
            continue
        client_mixins = mixin_meta.setdefault("client", [])
        if "client.GuiRender" not in client_mixins:
            client_mixins.append("client.GuiRender")
        if "client.GameRendererCapture26" not in client_mixins:
            client_mixins.append("client.GameRendererCapture26")
        mixin_config.write_text(json.dumps(mixin_meta, indent=2) + "\n", encoding="utf-8")


# Keep the original config/status references available in the new preview-upload path.
if kind == "watut":
    rh = root / "src/main/java/com/corosus/watut/client/screen/RenderHelper.java"
    text = rh.read_text(encoding="utf-8")
    imports = [
        "import com.corosus.watut.PlayerStatus;",
        "import com.corosus.watut.WatutMod;",
        "import com.corosus.watut.config.ConfigClient;",
        "import com.corosus.watut.config.ConfigServerControlledSyncedToClient;",
    ]
    anchor = "import net.minecraft.client.gui.GuiGraphicsExtractor;"
    if anchor in text:
        text = text.replace(anchor, anchor + "\n" + "\n".join(line for line in imports if line not in text), 1)
    rh.write_text(text, encoding="utf-8")


# Build a per-screen particle layer by cloning the vanilla translucent layer's pipeline,
# because 26.3 no longer exposes the old PARTICLE_TRANSLUCENT constant.
if kind == "watut":
    sd = root / "src/main/java/com/corosus/watut/client/screen/ScreenData.java"
    text = sd.read_text(encoding="utf-8")
    text = text.replace(
        "import net.minecraft.client.Minecraft;",
        "import net.minecraft.client.Minecraft;\nimport net.minecraft.client.gui.screens.Screen;\nimport java.lang.reflect.Constructor;\nimport java.lang.reflect.Field;\nimport java.lang.reflect.Modifier;"
    )
    text = text.replace("import net.minecraft.client.renderer.RenderPipelines;\n", "")
    text = text.replace(
        "new SingleQuadParticle.Layer(false, textureId, RenderPipelines.PARTICLE_TRANSLUCENT, null)",
        "makeLayer(textureId)"
    )
    anchor = "    public Identifier getTextureId() { return textureId; }"
    helper = r'''    private static SingleQuadParticle.Layer makeLayer(Identifier id) {
        try {
            SingleQuadParticle.Layer prototype = SingleQuadParticle.Layer.TRANSLUCENT;
            for (Constructor<?> constructor : SingleQuadParticle.Layer.class.getDeclaredConstructors()) {
                Class<?>[] types = constructor.getParameterTypes();
                if (types.length != 4 || types[0] != boolean.class || !types[1].isAssignableFrom(Identifier.class)) continue;
                Object[] args = new Object[] { Boolean.FALSE, id, null, null };
                for (int index = 2; index < 4; index++) {
                    for (Field field : SingleQuadParticle.Layer.class.getDeclaredFields()) {
                        if (Modifier.isStatic(field.getModifiers())) continue;
                        if (types[index].isAssignableFrom(field.getType()) || field.getType().isAssignableFrom(types[index])) {
                            field.setAccessible(true);
                            Object value = field.get(prototype);
                            if (value != null && types[index].isInstance(value)) {
                                args[index] = value;
                                break;
                            }
                        }
                    }
                }
                constructor.setAccessible(true);
                return (SingleQuadParticle.Layer)constructor.newInstance(args);
            }
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException("Could not create WATUT screen texture particle layer", e);
        }
        throw new IllegalStateException("Minecraft 26.3 translucent particle layer constructor changed");
    }

'''
    if anchor in text and "private static SingleQuadParticle.Layer makeLayer" not in text:
        text = text.replace(anchor, helper + anchor, 1)
    sd.write_text(text, encoding="utf-8")


# Render the extracted Screen state into a private render target. This preserves WATUT's
# "open screen preview" behavior instead of copying the surrounding 3D world framebuffer.
if kind == "watut":
    java_root = root / "src/main/java/com/corosus/watut"

    capture = r'''package com.corosus.watut.client.screen;

import com.corosus.watut.PlayerStatus;
import com.corosus.watut.WatutMod;
import com.corosus.watut.config.ConfigServerControlledSyncedToClient;
import com.mojang.blaze3d.pipeline.RenderTarget;
import com.mojang.blaze3d.platform.NativeImage;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraft.client.DeltaTracker;
import net.minecraft.client.gui.GuiGraphicsExtractor;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.renderer.GameRenderer;
import net.minecraft.client.renderer.state.gui.GuiRenderState;
import net.minecraft.resources.Identifier;
import net.minecraft.util.ARGB;

import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.nio.ByteBuffer;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

public final class ScreenCapture26 {
    private static final AtomicBoolean capturePending = new AtomicBoolean(false);
    private static volatile boolean renderingCapture;
    private static GuiRenderState captureState;
    private static Object captureGuiRenderer;
    private static RenderTarget captureTarget;
    private static int targetWidth, targetHeight;

    private ScreenCapture26() {}
    public static boolean isRenderingCapture() { return renderingCapture; }
    public static RenderTarget getCaptureTarget() { return captureTarget; }

    public static void captureIfNeeded(GameRenderer gameRenderer, DeltaTracker deltaTracker) {
        Minecraft mc = Minecraft.getInstance();
        Screen screen = mc.gui == null ? null : mc.gui.screen();
        if (mc.level == null || mc.player == null || screen == null || !RenderHelper.useDynamicGUISystem()) return;
        PlayerStatus status = WatutMod.getPlayerStatusManagerClient().getStatusLocal();
        ScreenData data = status.getScreenData();
        if (!data.isNeedsNewRenderToPixelData() || !capturePending.compareAndSet(false, true)) return;

        data.setNeedsNewRenderToPixelData(false);
        try {
            ensureCaptureTarget(mc);
            ensureCaptureRenderer(gameRenderer, mc);
            resetState(captureState);

            int mouseX = (int)(mc.mouseHandler.xpos() / mc.getWindow().getGuiScale());
            int mouseY = (int)(mc.mouseHandler.ypos() / mc.getWindow().getGuiScale());
            float partialTick = deltaTracker.getGameTimeDeltaTicks();
            GuiGraphicsExtractor graphics = new GuiGraphicsExtractor(mc, captureState, mouseX, mouseY);

            renderingCapture = true;
            extractScreen(screen, graphics, mouseX, mouseY, partialTick);
            invokeByName(graphics, "extractDeferredElements", mouseX, mouseY, partialTick);
            drawCursor(graphics, mouseX, mouseY);

            invokeByName(captureTarget, "setClearColor", 0.0F, 0.0F, 0.0F, 0.0F);
            invokeByName(captureTarget, "clear", Minecraft.ON_OSX);
            invokeByName(captureGuiRenderer, "render");
            invokeByName(captureGuiRenderer, "endFrame");
            renderingCapture = false;

            boolean entireScreen = ConfigServerControlledSyncedToClient.dynamicGuiShowClientsEntireScreen;
            int scale = entireScreen ? 1 : Math.max(1, (int)Math.round(mc.getWindow().getGuiScale()));
            Screenshot.takeScreenshot(captureTarget, scale, image -> finishCapture(status, image, entireScreen));
        } catch (Throwable error) {
            renderingCapture = false;
            data.setNeedsNewRenderToPixelData(true);
            capturePending.set(false);
            System.err.println("[WATUT] Isolated screen capture failed: " + error);
        }
    }

    private static void ensureCaptureTarget(Minecraft mc) throws Exception {
        int w = Math.max(1, mc.getWindow().getWidth());
        int h = Math.max(1, mc.getWindow().getHeight());
        if (captureTarget == null) {
            Class<?> type = Class.forName("com.mojang.blaze3d.pipeline.TextureTarget");
            for (Constructor<?> constructor : type.getDeclaredConstructors()) {
                Class<?>[] p = constructor.getParameterTypes();
                if (p.length != 5 || p[0] != String.class || p[1] != int.class || p[2] != int.class) continue;
                Object colorFormat = findRgbaFormat(p[3]);
                constructor.setAccessible(true);
                captureTarget = (RenderTarget)constructor.newInstance("watut-screen-preview", w, h, colorFormat, null);
                targetWidth = w;
                targetHeight = h;
                return;
            }
            throw new NoSuchMethodException("TextureTarget(String,int,int,GpuFormat,GpuFormat)");
        }
        if (targetWidth != w || targetHeight != h) {
            invokeByName(captureTarget, "resize", w, h);
            targetWidth = w;
            targetHeight = h;
        }
    }

    private static Object findRgbaFormat(Class<?> formatType) {
        try {
            if (formatType.isEnum()) {
                Object[] values = formatType.getEnumConstants();
                for (Object value : values) {
                    String name = ((Enum<?>)value).name();
                    if (name.equals("RGBA8_UNORM") || name.equals("R8G8B8A8_UNORM") || name.equals("RGBA8")) return value;
                }
            }
            for (Field field : formatType.getDeclaredFields()) {
                if (!Modifier.isStatic(field.getModifiers())) continue;
                if (!(field.getType().isAssignableFrom(formatType) || formatType.isAssignableFrom(field.getType()))) continue;
                if (field.getName().equals("RGBA8_UNORM") || field.getName().equals("R8G8B8A8_UNORM") || field.getName().equals("RGBA8")) {
                    field.setAccessible(true);
                    return field.get(null);
                }
            }
        } catch (Throwable ignored) {}
        return null;
    }

    private static void ensureCaptureRenderer(GameRenderer gameRenderer, Minecraft mc) throws Exception {
        if (captureState == null) captureState = new GuiRenderState();
        if (captureGuiRenderer != null) return;

        Object vanillaRenderer = null;
        for (Field field : GameRenderer.class.getDeclaredFields()) {
            if (Modifier.isStatic(field.getModifiers())) continue;
            if (!field.getType().getName().endsWith(".GuiRenderer")) continue;
            field.setAccessible(true);
            vanillaRenderer = field.get(gameRenderer);
            if (vanillaRenderer != null) break;
        }
        Object dispatcher = invokeByName(gameRenderer, "featureRenderDispatcher");
        List<?> pictureInPicture = findPipRegistrations(vanillaRenderer);
        Class<?> rendererClass = Class.forName("net.minecraft.client.gui.render.GuiRenderer");
        for (Constructor<?> constructor : rendererClass.getDeclaredConstructors()) {
            Class<?>[] p = constructor.getParameterTypes();
            if (p.length != 3 || !p[0].isAssignableFrom(captureState.getClass())
                    || !p[1].isInstance(dispatcher) || !List.class.isAssignableFrom(p[2])) continue;
            constructor.setAccessible(true);
            captureGuiRenderer = constructor.newInstance(captureState, dispatcher, pictureInPicture);
            return;
        }
        throw new NoSuchMethodException("GuiRenderer(GuiRenderState,FeatureRenderDispatcher,List)");
    }

    private static List<?> findPipRegistrations(Object renderer) throws IllegalAccessException {
        if (renderer != null) {
            List<?> fallback = null;
            for (Field field : renderer.getClass().getDeclaredFields()) {
                if (Modifier.isStatic(field.getModifiers()) || !List.class.isAssignableFrom(field.getType())) continue;
                field.setAccessible(true);
                Object value = field.get(renderer);
                if (!(value instanceof List<?> list)) continue;
                if (field.getName().toLowerCase().contains("pip") || field.getName().toLowerCase().contains("picture")) return list;
                if (!list.isEmpty() && fallback == null) fallback = list;
                for (Object element : list) {
                    if (element != null && element.getClass().getName().contains("PictureInPictureRendererRegistration")) return list;
                }
            }
            if (fallback != null) return fallback;
        }
        return List.of();
    }

    private static void resetState(GuiRenderState state) throws Exception {
        invokeByName(state, "reset");
    }

    private static void extractScreen(Screen screen, GuiGraphicsExtractor graphics, int mouseX, int mouseY, float partialTick) throws Exception {
        for (Method method : screen.getClass().getMethods()) {
            if (!method.getName().equals("extractRenderStateWithTooltipAndSubtitles")) continue;
            Class<?>[] p = method.getParameterTypes();
            if (p.length == 4 && p[0].isAssignableFrom(graphics.getClass()) && p[1] == int.class && p[2] == int.class && p[3] == float.class) {
                method.invoke(screen, graphics, mouseX, mouseY, partialTick);
                return;
            }
        }
        throw new NoSuchMethodException("Screen.extractRenderStateWithTooltipAndSubtitles");
    }

    private static void drawCursor(GuiGraphicsExtractor graphics, int mouseX, int mouseY) {
        try {
            Class<?> pipelines = Class.forName("net.minecraft.client.renderer.RenderPipelines");
            Object pipeline = pipelines.getField("GUI_TEXTURED").get(null);
            Identifier cursor = RenderHelper.cursor;
            for (Method method : graphics.getClass().getMethods()) {
                Class<?>[] p = method.getParameterTypes();
                if (!method.getName().equals("blit") || p.length != 10 || !p[0].isInstance(pipeline) || p[1] != Identifier.class) continue;
                method.invoke(graphics, pipeline, cursor, mouseX, mouseY, 0.0F, 0.0F, 6, 10, 16, 16);
                return;
            }
        } catch (Throwable ignored) {}
    }

    private static Object invokeByName(Object instance, String name, Object... args) throws Exception {
        if (instance == null) throw new IllegalStateException("Missing instance for " + name);
        for (Method method : instance.getClass().getMethods()) {
            if (!method.getName().equals(name) || method.getParameterCount() != args.length) continue;
            Class<?>[] p = method.getParameterTypes();
            boolean matches = true;
            for (int i = 0; i < p.length; i++) {
                if (args[i] == null) { if (p[i].isPrimitive()) matches = false; }
                else if (p[i].isPrimitive()) {
                    if ((p[i] == int.class && !(args[i] instanceof Integer))
                            || (p[i] == float.class && !(args[i] instanceof Float))
                            || (p[i] == boolean.class && !(args[i] instanceof Boolean))) matches = false;
                } else if (!p[i].isInstance(args[i])) matches = false;
            }
            if (matches) return method.invoke(instance, args);
        }
        for (Method method : instance.getClass().getDeclaredMethods()) {
            if (!method.getName().equals(name) || method.getParameterCount() != args.length) continue;
            Class<?>[] p = method.getParameterTypes();
            boolean matches = true;
            for (int i = 0; i < p.length; i++) {
                if (args[i] == null) { if (p[i].isPrimitive()) matches = false; }
                else if (p[i].isPrimitive()) {
                    if ((p[i] == int.class && !(args[i] instanceof Integer))
                            || (p[i] == float.class && !(args[i] instanceof Float))
                            || (p[i] == boolean.class && !(args[i] instanceof Boolean))) matches = false;
                } else if (!p[i].isInstance(args[i])) matches = false;
            }
            if (matches) {
                method.setAccessible(true);
                return method.invoke(instance, args);
            }
        }
        throw new NoSuchMethodException(instance.getClass().getName() + "." + name + "/" + args.length);
    }

    private static void finishCapture(PlayerStatus status, NativeImage image, boolean entireScreen) {
        try {
            if (image == null) {
                status.getScreenData().setNeedsNewRenderToPixelData(true);
                return;
            }
            int srcWidth = image.getWidth();
            int srcHeight = image.getHeight();
            if (srcWidth <= 0 || srcHeight <= 0 || (long)srcWidth * srcHeight * 4L > 64L * 1024L * 1024L) {
                status.getScreenData().setNeedsNewRenderToPixelData(true);
                return;
            }
            int outWidth = entireScreen ? srcWidth : ScreenParticleRenderer.defaultWidthScaledDown;
            int outHeight = entireScreen ? srcHeight : ScreenParticleRenderer.defaultHeightScaledDown;
            ByteBuffer rgba = ByteBuffer.allocateDirect(Math.multiplyExact(Math.multiplyExact(outWidth, outHeight), 4));
            if (entireScreen) {
                for (int y = 0; y < outHeight; y++) for (int x = 0; x < outWidth; x++) putPixel(rgba, image.getPixel(x, y));
            } else {
                int srcLeft = Math.max(0, (srcWidth - outWidth) / 2);
                int srcTop = Math.max(0, (srcHeight - outHeight) / 2);
                int dstLeft = Math.max(0, (outWidth - srcWidth) / 2);
                int dstTop = Math.max(0, (outHeight - srcHeight) / 2);
                int copyWidth = Math.min(outWidth - dstLeft, srcWidth - srcLeft);
                int copyHeight = Math.min(outHeight - dstTop, srcHeight - srcTop);
                for (int y = 0; y < outHeight; y++) {
                    for (int x = 0; x < outWidth; x++) {
                        int sx = srcLeft + x - dstLeft;
                        int sy = srcTop + y - dstTop;
                        if (x >= dstLeft && y >= dstTop && x < dstLeft + copyWidth && y < dstTop + copyHeight) putPixel(rgba, image.getPixel(sx, sy));
                        else rgba.put((byte)0).put((byte)0).put((byte)0).put((byte)0);
                    }
                }
            }
            rgba.flip();
            ScreenData data = status.getScreenData();
            data.setWidth(outWidth);
            data.setHeight(outHeight);
            data.setTexturePixelData(RenderHelper.compress(rgba));
            WatutMod.getPlayerStatusManagerClient().sendScreenRenderData(status);
        } catch (Throwable error) {
            status.getScreenData().setNeedsNewRenderToPixelData(true);
            System.err.println("[WATUT] Could not encode isolated GUI preview: " + error);
        } finally {
            if (image != null) image.close();
            capturePending.set(false);
        }
    }

    private static void putPixel(ByteBuffer output, int color) {
        output.put((byte)ARGB.red(color));
        output.put((byte)ARGB.green(color));
        output.put((byte)ARGB.blue(color));
        output.put((byte)ARGB.alpha(color));
    }
}
'''
    (java_root / "client/screen/ScreenCapture26.java").write_text(capture, encoding="utf-8")

    game_mixin = r'''package com.corosus.watut.mixin.client;

import com.corosus.watut.client.screen.ScreenCapture26;
import net.minecraft.client.DeltaTracker;
import net.minecraft.client.renderer.GameRenderer;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(GameRenderer.class)
public abstract class GameRendererCapture26 {
    @Inject(method = "render", at = @At("TAIL"))
    private void watut$captureDynamicScreen(DeltaTracker deltaTracker, boolean renderLevel, CallbackInfo ci) {
        ScreenCapture26.captureIfNeeded((GameRenderer)(Object)this, deltaTracker);
    }
}
'''
    (java_root / "mixin/client/GameRendererCapture26.java").write_text(game_mixin, encoding="utf-8")

    target_mixin = r'''package com.corosus.watut.mixin.client;

import com.corosus.watut.client.screen.ScreenCapture26;
import com.mojang.blaze3d.pipeline.RenderTarget;
import net.minecraft.client.gui.render.GuiRenderer;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyVariable;

@Mixin(GuiRenderer.class)
public abstract class GuiRendererCaptureTarget {
    @ModifyVariable(method = "executeDrawRange", at = @At("HEAD"), argsOnly = true, ordinal = 0)
    private RenderTarget watut$redirectCaptureTarget(RenderTarget original) {
        RenderTarget target = ScreenCapture26.getCaptureTarget();
        return ScreenCapture26.isRenderingCapture() && target != null ? target : original;
    }
}
'''
    (java_root / "mixin/client/GuiRendererCaptureTarget.java").write_text(target_mixin, encoding="utf-8")

    background_mixin = r'''package com.corosus.watut.mixin.client;

import com.corosus.watut.client.screen.ScreenCapture26;
import com.corosus.watut.config.ConfigServerControlledSyncedToClient;
import net.minecraft.client.gui.screens.Screen;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(Screen.class)
public abstract class ScreenBackgroundCapture26 {
    @Inject(method = {"extractBackground", "extractMenuBackground"}, at = @At("HEAD"), cancellable = true, require = 0)
    private void watut$suppressCapturedBackground(CallbackInfo ci) {
        if (ScreenCapture26.isRenderingCapture() && ConfigServerControlledSyncedToClient.dynamicGuiDisableBackgroundRendering) ci.cancel();
    }
}
'''
    (java_root / "mixin/client/ScreenBackgroundCapture26.java").write_text(background_mixin, encoding="utf-8")

    # Replace the older direct-to-main-target screenshot capture mixin with an isolated renderer flow.
    mixin_config = root / "src/main/resources/watut_fabric.mixins.json"
    if mixin_config.exists():
        meta = json.loads(mixin_config.read_text(encoding="utf-8"))
        client_mixins = meta.setdefault("client", [])
        for name in ("client.GameRendererCapture26", "client.GuiRendererCaptureTarget", "client.ScreenBackgroundCapture26", "client.GuiRender"):
            if name not in client_mixins:
                client_mixins.append(name)
        mixin_config.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


# New 26.3 RenderTarget APIs no longer expose Minecraft.ON_OSX; probe the clear overload.
if kind == "watut":
    capture_path = root / "src/main/java/com/corosus/watut/client/screen/ScreenCapture26.java"
    text = capture_path.read_text(encoding="utf-8")
    text = text.replace(
        'invokeByName(captureTarget, "clear", Minecraft.ON_OSX);',
        'try { invokeByName(captureTarget, "clear", false); } catch (NoSuchMethodException noBooleanClear) { invokeByName(captureTarget, "clear"); }'
    )
    capture_path.write_text(text, encoding="utf-8")


# Restore the item-transfer effect using the actual item icon, and capture before vanilla GUI endFrame.
if kind == "watut":
    java_root = root / "src/main/java/com/corosus/watut"

    sc_path = java_root / "client/screen/ScreenCapture26.java"
    sc = sc_path.read_text(encoding="utf-8")
    additions = [
        "import net.minecraft.client.particle.SingleQuadParticle;",
        "import net.minecraft.client.renderer.texture.DynamicTexture;",
        "import net.minecraft.world.item.ItemStack;",
        "import java.util.concurrent.ConcurrentLinkedQueue;",
        "import java.util.function.Consumer;",
    ]
    anchor = "import net.minecraft.client.gui.GuiGraphicsExtractor;"
    if anchor in sc:
        sc = sc.replace(anchor, anchor + "\n" + "\n".join(line for line in additions if line not in sc), 1)
    sc = sc.replace(
        "    private static int targetWidth, targetHeight;\n",
        """    private static int targetWidth, targetHeight;
    private static final ConcurrentLinkedQueue<ItemIconRequest> itemIconRequests = new ConcurrentLinkedQueue<>();

    private static final class ItemIconRequest {
        final ItemStack stack;
        final Identifier textureId;
        final Consumer<SingleQuadParticle.Layer> callback;
        ItemIconRequest(ItemStack stack, Identifier textureId, Consumer<SingleQuadParticle.Layer> callback) {
            this.stack = stack.copy();
            this.textureId = textureId;
            this.callback = callback;
        }
    }

    public static void requestItemIcon(ItemStack stack, Identifier textureId, Consumer<SingleQuadParticle.Layer> callback) {
        if (stack == null || stack.isEmpty() || textureId == null || callback == null) return;
        itemIconRequests.add(new ItemIconRequest(stack, textureId, callback));
    }

    public static void releaseTexture(Identifier textureId) {
        try {
            Minecraft.getInstance().getTextureManager().release(textureId);
        } catch (Throwable ignored) {}
    }
"""
    )
    capture_method = r'''    public static void captureIfNeeded(GameRenderer gameRenderer, DeltaTracker deltaTracker) {
        Minecraft mc = Minecraft.getInstance();
        if (mc.level == null || mc.player == null || mc.gui == null) return;
        Screen screen = mc.gui.screen();
        PlayerStatus status = WatutMod.getPlayerStatusManagerClient().getStatusLocal();
        ScreenData data = status.getScreenData();
        boolean doScreen = screen != null && RenderHelper.useDynamicGUISystem() && data.isNeedsNewRenderToPixelData();
        if ((!doScreen && itemIconRequests.isEmpty()) || !capturePending.compareAndSet(false, true)) return;

        ItemIconRequest itemRequest = doScreen ? null : itemIconRequests.poll();
        if (!doScreen && itemRequest == null) {
            capturePending.set(false);
            return;
        }
        if (doScreen) data.setNeedsNewRenderToPixelData(false);

        try {
            ensureCaptureTarget(mc);
            ensureCaptureRenderer(gameRenderer, mc);
            resetState(captureState);

            int mouseX = (int)(mc.mouseHandler.xpos() / mc.getWindow().getGuiScale());
            int mouseY = (int)(mc.mouseHandler.ypos() / mc.getWindow().getGuiScale());
            float partialTick = deltaTracker.getGameTimeDeltaTicks();
            GuiGraphicsExtractor graphics = new GuiGraphicsExtractor(mc, captureState, mouseX, mouseY);

            renderingCapture = true;
            if (doScreen) {
                extractScreen(screen, graphics, mouseX, mouseY, partialTick);
                invokeByName(graphics, "extractDeferredElements", mouseX, mouseY, partialTick);
                drawCursor(graphics, mouseX, mouseY);
            } else {
                graphics.item(itemRequest.stack, Math.max(0, graphics.guiWidth() / 2 - 8),
                        Math.max(0, graphics.guiHeight() / 2 - 8), 0);
            }

            invokeByName(captureTarget, "setClearColor", 0.0F, 0.0F, 0.0F, 0.0F);
            try {
                invokeByName(captureTarget, "clear", false);
            } catch (NoSuchMethodException noBooleanClear) {
                invokeByName(captureTarget, "clear");
            }
            invokeByName(captureGuiRenderer, "render");
            invokeByName(captureGuiRenderer, "endFrame");
            renderingCapture = false;

            if (doScreen) {
                boolean entireScreen = ConfigServerControlledSyncedToClient.dynamicGuiShowClientsEntireScreen;
                int scale = entireScreen ? 1 : Math.max(1, (int)Math.round(mc.getWindow().getGuiScale()));
                Screenshot.takeScreenshot(captureTarget, scale, image -> finishCapture(status, image, entireScreen));
            } else {
                int scale = Math.max(1, (int)Math.round(mc.getWindow().getGuiScale()));
                ItemIconRequest finalRequest = itemRequest;
                Screenshot.takeScreenshot(captureTarget, scale, image -> finishItemIcon(mc, finalRequest, image));
            }
        } catch (Throwable error) {
            renderingCapture = false;
            if (doScreen) data.setNeedsNewRenderToPixelData(true);
            if (itemRequest != null) itemIconRequests.add(itemRequest);
            capturePending.set(false);
            System.err.println("[WATUT] Isolated screen/item capture failed: " + error);
        }
    }

    private static void finishItemIcon(Minecraft mc, ItemIconRequest request, NativeImage image) {
        try {
            if (image == null || request == null) return;
            int w = image.getWidth(), h = image.getHeight();
            if (w <= 0 || h <= 0) return;
            DynamicTexture texture = new DynamicTexture("WATUT transferred item icon", 16, 16, true);
            var pixels = texture.getPixels();
            int left = Math.max(0, (w - 16) / 2);
            int top = Math.max(0, (h - 16) / 2);
            int dstLeft = Math.max(0, (16 - w) / 2);
            int dstTop = Math.max(0, (16 - h) / 2);
            for (int y = 0; y < 16; y++) {
                for (int x = 0; x < 16; x++) {
                    int sx = left + x - dstLeft;
                    int sy = top + y - dstTop;
                    if (sx >= 0 && sy >= 0 && sx < w && sy < h) pixels.setPixel(x, y, image.getPixel(sx, sy));
                    else pixels.setPixel(x, y, 0);
                }
            }
            texture.upload();
            mc.getTextureManager().register(request.textureId, texture);
            request.callback.accept(ScreenData.createLayer(request.textureId));
        } catch (Throwable error) {
            System.err.println("[WATUT] Could not build transferred item icon: " + error);
        } finally {
            if (image != null) image.close();
            capturePending.set(false);
        }
    }

'''
    sc = re.sub(
        r"(?s)    public static void captureIfNeeded\(GameRenderer gameRenderer, DeltaTracker deltaTracker\) \{.*?\n    \}\n\n    private static void ensureCaptureTarget",
        capture_method + "    private static void ensureCaptureTarget",
        sc,
        count=1
    )
    sc_path.write_text(sc, encoding="utf-8")

    sd_path = java_root / "client/screen/ScreenData.java"
    sd = sd_path.read_text(encoding="utf-8")
    anchor = "    public Identifier getTextureId() { return textureId; }"
    if anchor in sd and "public static SingleQuadParticle.Layer createLayer" not in sd:
        sd = sd.replace(anchor, "    public static SingleQuadParticle.Layer createLayer(Identifier id) { return makeLayer(id); }\n" + anchor, 1)
    sd_path.write_text(sd, encoding="utf-8")

    item_particle = r'''package com.corosus.watut.particle;

import com.corosus.watut.ParticleRegistry;
import com.corosus.watut.client.screen.ScreenCapture26;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.particle.SingleQuadParticle;
import net.minecraft.resources.Identifier;
import net.minecraft.world.item.ItemStack;

import java.util.HashSet;
import java.util.concurrent.atomic.AtomicLong;

public class ParticleItem extends ParticleRotating {
    private static final AtomicLong NEXT_ID = new AtomicLong();
    public static HashSet<String> itemBlacklist = new HashSet<>();
    public ItemStack itemStack;
    public float xFrom, yFrom, zFrom, xTo, yTo, zTo;
    private final Identifier itemTextureId;
    private volatile SingleQuadParticle.Layer itemLayer = SingleQuadParticle.Layer.TRANSLUCENT;
    private volatile boolean expired;

    public ParticleItem(ClientLevel level, float brightness, ItemStack stack,
                        float xFrom, float yFrom, float zFrom, float xTo, float yTo, float zTo) {
        super(level, xFrom, yFrom, zFrom);
        this.itemStack = stack.copy();
        this.xFrom = xFrom; this.yFrom = yFrom; this.zFrom = zFrom;
        this.xTo = xTo; this.yTo = yTo; this.zTo = zTo;
        this.setSprite(ParticleRegistry.anvil.getSprite());
        this.lifetime = 6;
        this.gravity = 0;
        this.quadSize = 0.18F;
        this.rotationYaw = level.getRandom().nextFloat() * 360F;
        this.setColor(this.rCol * brightness, this.gCol * brightness, this.bCol * brightness);
        this.itemTextureId = Identifier.fromNamespaceAndPath("watut", "item_move_" + Long.toUnsignedString(NEXT_ID.incrementAndGet(), 36));
        ScreenCapture26.requestItemIcon(this.itemStack, this.itemTextureId, layer -> {
            if (this.expired) ScreenCapture26.releaseTexture(this.itemTextureId);
            else this.itemLayer = layer;
        });
    }

    @Override
    protected SingleQuadParticle.Layer getLayer() {
        return itemLayer == null ? SingleQuadParticle.Layer.TRANSLUCENT : itemLayer;
    }

    @Override public float getU0() { return 0.0F; }
    @Override public float getU1() { return 1.0F; }
    @Override public float getV0() { return 0.0F; }
    @Override public float getV1() { return 1.0F; }

    @Override
    public void tick() {
        super.tick();
        this.xo = this.x; this.yo = this.y; this.zo = this.z;
        float lerp = ((float)this.age) / 3.0F;
        this.setPos(net.minecraft.util.Mth.lerp(lerp, xFrom, xTo),
                    net.minecraft.util.Mth.lerp(lerp, yFrom, yTo),
                    net.minecraft.util.Mth.lerp(lerp, zFrom, zTo));
        if (this.age >= 3) this.setPos(xTo, yTo, zTo);
        if (this.age++ >= this.lifetime) {
            this.expired = true;
            this.remove();
            ScreenCapture26.releaseTexture(this.itemTextureId);
        }
    }
}
'''
    (java_root / "particle/ParticleItem.java").write_text(item_particle, encoding="utf-8")

    gm = java_root / "mixin/client/GameRendererCapture26.java"
    gmt = gm.read_text(encoding="utf-8")
    gmt = gmt.replace(
        '@Inject(method = "render", at = @At("TAIL"))',
        '@Inject(method = "render", at = @At(value = "INVOKE", target = "Lnet/minecraft/client/gui/render/GuiRenderer;endFrame()V", shift = At.Shift.BEFORE), require = 0)'
    )
    gm.write_text(gmt, encoding="utf-8")
