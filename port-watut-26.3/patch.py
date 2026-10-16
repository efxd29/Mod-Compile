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

build = root / "build_fabric.gradle"
g = build.read_text(encoding="utf-8")
g = g.replace("id 'fabric-loom' version '1.6-SNAPSHOT'", "id 'net.fabricmc.fabric-loom' version '1.18-SNAPSHOT'")
g = re.sub(r"(?ms)^[ \t]*mappings\(loom\.layered\s*\{.*?^[ \t]*\}\)[ \t]*\n", "", g)
g = g.replace("modImplementation ", "implementation ")
g = g.replace("include(modImplementation(", "include(implementation(")
g = g.replace("it.options.release = 21", "it.options.release = 25")
g = g.replace("JavaVersion.VERSION_21", "JavaVersion.VERSION_25")
build.write_text(g, encoding="utf-8")

# Keep all original entrypoints, mixins, resources, and feature classes.
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

print(f"Prepared {kind}: all original Java/resource/mixin files retained; target 26.3, Java 25, Fabric Loader 0.19.5, Fabric API 0.162.0+26.3")
