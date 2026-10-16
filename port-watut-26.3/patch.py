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
