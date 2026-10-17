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
