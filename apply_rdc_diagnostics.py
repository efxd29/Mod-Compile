#!/usr/bin/env python3
"""Guarded patch for Zalith Launcher 2.6.1: local crash/log export for RDC."""
from pathlib import Path
import sys

ROOT = Path.cwd()
DIAG_REL = Path("ZalithLauncher/src/main/java/com/movtery/zalithlauncher/utils/diagnostics/RdcDiagnostics.kt")

DIAGNOSTICS = r'''/*
 * Unofficial local diagnostics extension for remote troubleshooting.
 * This file is distributed under the launcher project's GPL-3.0-or-later license.
 */
package com.movtery.zalithlauncher.utils.diagnostics

import android.content.ContentValues
import android.content.Context
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import com.movtery.zalithlauncher.BuildConfig
import com.movtery.zalithlauncher.game.path.GamePathManager
import com.movtery.zalithlauncher.path.PathManager
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.RandomAccessFile
import java.util.Date
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.concurrent.TimeUnit
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/** Exports bounded, local-only logs. Accounts, settings, databases and arbitrary files are excluded. */
object RdcDiagnostics {
    private const val MAX_ARCHIVE_BYTES = 20 * 1024 * 1024
    private const val MAX_EACH_FILE = 2 * 1024 * 1024
    private const val MAX_FILES = 50

    private data class Candidate(val entry: String, val file: File, val modified: Long)

    fun export(context: Context, reason: String = "manual-export"): String {
        val app = context.applicationContext
        val stamp = SimpleDateFormat("yyyyMMdd-HHmmss-SSS", Locale.US).format(Date())
        val name = "RenoMC-Diagnostics-" + stamp + ".zip"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val resolver = app.contentResolver
            val values = ContentValues().apply {
                put(MediaStore.MediaColumns.DISPLAY_NAME, name)
                put(MediaStore.MediaColumns.MIME_TYPE, "application/zip")
                put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/RenoMC-Diagnostics")
                put(MediaStore.MediaColumns.IS_PENDING, 1)
            }
            val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
                ?: error("Android couldn't create the diagnostic ZIP")
            try {
                val output = resolver.openOutputStream(uri, "w")
                    ?: error("Android couldn't open the diagnostic ZIP")
                output.use { writeArchive(it, app, reason) }
                val publish = ContentValues().apply { put(MediaStore.MediaColumns.IS_PENDING, 0) }
                resolver.update(uri, publish, null, null)
                return "Download/RenoMC-Diagnostics/" + name
            } catch (t: Throwable) {
                runCatching { resolver.delete(uri, null, null) }
                throw t
            }
        }
        @Suppress("DEPRECATION")
        val targetDir = File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), "RenoMC-Diagnostics")
        if (!targetDir.isDirectory && !targetDir.mkdirs()) error("Cannot create " + targetDir.absolutePath)
        val target = File(targetDir, name)
        target.outputStream().use { writeArchive(it, app, reason) }
        return target.absolutePath
    }

    /** Called best-effort before the existing uncaught-crash flow; errors are deliberately swallowed. */
    @JvmStatic
    fun tryExportCrashSnapshot(context: Context) {
        runCatching { export(context, "uncaught-exception") }
    }

    private fun writeArchive(output: java.io.OutputStream, context: Context, reason: String) {
        ZipOutputStream(output.buffered()).use { zip ->
            val report = listOf(
                "product=Reno MC Diagnostics (unofficial)",
                "reason=" + reason,
                "timestamp=" + SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", Locale.US).format(Date()),
                "app_id=" + context.packageName,
                "app_version=" + BuildConfig.VERSION_NAME,
                "manufacturer=" + Build.MANUFACTURER,
                "device_model=" + Build.MODEL,
                "android_release=" + Build.VERSION.RELEASE,
                "android_sdk=" + Build.VERSION.SDK_INT,
                "supported_abis=" + Build.SUPPORTED_ABIS.joinToString(","),
                "java_version=" + (System.getProperty("java.version") ?: "unknown"),
                "os_arch=" + (System.getProperty("os.arch") ?: "unknown"),
                "launcher_logs=" + (safePath { PathManager.DIR_LAUNCHER_LOGS }?.absolutePath ?: "unavailable"),
                "native_logs=" + (safePath { PathManager.DIR_NATIVE_LOGS }?.absolutePath ?: "unavailable"),
                "current_game_path=" + (runCatching { GamePathManager.currentPath.value }.getOrNull() ?: "unavailable")
            ).joinToString("\n")
            putText(zip, "diagnostics/system-info.txt", report)
            val logcat = collectLogcat(context)
            if (logcat.isNotEmpty()) putText(zip, "diagnostics/logcat-relevant.txt", redact(logcat))
            var budget = MAX_ARCHIVE_BYTES - report.toByteArray(Charsets.UTF_8).size
            val candidates = collectCandidates().sortedWith(
                compareBy<Candidate> {
                    when {
                        it.file.name.equals("launcher_crash.log", true) -> 0
                        it.file.parentFile?.name.equals("crash-reports", true) -> 1
                        it.file.name.equals("latest.log", true) -> 2
                        it.file.name.startsWith("hs_err_pid", true) -> 3
                        else -> 4
                    }
                }.thenByDescending { it.modified }
            )
            for (candidate in candidates) {
                if (budget <= 0) break
                val raw = runCatching { readCapped(candidate.file, minOf(MAX_EACH_FILE, budget)) }.getOrNull() ?: continue
                if (raw.isEmpty()) continue
                val safe = redact(raw.toString(Charsets.UTF_8)).toByteArray(Charsets.UTF_8)
                if (safe.isEmpty()) continue
                zip.putNextEntry(ZipEntry(candidate.entry))
                zip.write(safe, 0, minOf(safe.size, budget))
                zip.closeEntry()
                budget -= minOf(safe.size, budget)
            }
            putText(zip, "diagnostics/README.txt",
                "Generated locally by an unofficial Zalith Launcher diagnostics patch.\n" +
                "Contains selected .log/.txt files, selected logcat lines, and basic device info.\n" +
                "Account databases, launcher settings and arbitrary files are intentionally excluded.\n" +
                "Review the archive before sharing. Some token-like values are redacted.\n")
        }
    }

    private fun putText(zip: ZipOutputStream, name: String, text: String) {
        zip.putNextEntry(ZipEntry(name))
        zip.write(text.toByteArray(Charsets.UTF_8))
        zip.closeEntry()
    }

    private fun collectCandidates(): List<Candidate> {
        val found = mutableListOf<Candidate>()
        val seen = mutableSetOf<String>()
        fun addTree(label: String, root: File?) {
            if (root == null || !root.isDirectory || found.size >= MAX_FILES) return
            runCatching {
                for (file in root.walkTopDown().maxDepth(8)) {
                    if (found.size >= MAX_FILES) break
                    if (!file.isFile || !isLogText(file)) continue
                    val canonical = runCatching { file.canonicalPath }.getOrElse { file.absolutePath }
                    if (!seen.add(canonical)) continue
                    val rel = file.relativeTo(root).path.replace(File.separatorChar, '/').trimStart('/')
                    if (rel.split('/').any { it == ".." }) continue
                    found += Candidate(label + "/" + rel, file, file.lastModified())
                }
            }
        }
        addTree("launcher-logs", safePath { PathManager.DIR_LAUNCHER_LOGS })
        addTree("native-logs", safePath { PathManager.DIR_NATIVE_LOGS })
        val game = runCatching { File(GamePathManager.currentPath.value) }.getOrNull()
        addTree("minecraft-logs", game?.let { File(it, "logs") })
        addTree("minecraft-crash-reports", game?.let { File(it, "crash-reports") })
        if (game?.isDirectory == true) {
            game.listFiles()?.filter { it.isFile && it.name.startsWith("hs_err_pid", true) && it.name.endsWith(".log", true) }
                ?.forEach { file ->
                    if (found.size < MAX_FILES && seen.add(file.absolutePath)) {
                        found += Candidate("minecraft-native-crash/" + file.name, file, file.lastModified())
                    }
                }
        }
        return found
    }

    private fun isLogText(file: File): Boolean {
        val name = file.name.lowercase(Locale.ROOT)
        if (listOf("account", "setting", "token", "password", "credential", "secret", "auth").any { name.contains(it) }) return false
        return file.length() > 0L && (name.endsWith(".log") || name.endsWith(".txt") || name == "latest.log")
    }

    private fun collectLogcat(context: Context): String {
        val temp = runCatching { File.createTempFile("rdc-logcat-", ".txt", context.cacheDir) }.getOrNull() ?: return ""
        return try {
            val process = runCatching {
                ProcessBuilder("/system/bin/logcat", "-d", "-t", "1200", "-v", "threadtime")
                    .redirectErrorStream(true).redirectOutput(temp).start()
            }.getOrNull() ?: return ""
            if (!runCatching { process.waitFor(2, TimeUnit.SECONDS) }.getOrDefault(false)) process.destroyForcibly()
            val raw = readCapped(temp, 1024 * 1024).toString(Charsets.UTF_8)
            val tags = listOf(context.packageName, "AndroidRuntime", "DEBUG", "libc", "AppLog", "Pojav", "SDL", "Zalith", "linker", "crash_dump", "tombstoned")
            redact(raw.lineSequence().filter { line -> tags.any { line.contains(it, true) } }.takeLast(700).joinToString("\n"))
        } catch (_: Throwable) {
            ""
        } finally {
            runCatching { temp.delete() }
        }
    }

    private fun readCapped(file: File, limit: Int): ByteArray {
        if (limit <= 0 || !file.isFile) return ByteArray(0)
        val size = minOf(file.length(), limit.toLong()).toInt()
        val result = ByteArray(size)
        RandomAccessFile(file, "r").use { input ->
            input.seek((file.length() - size).coerceAtLeast(0L))
            input.readFully(result)
        }
        return result
    }

    private fun redact(text: String): String {
        val fields = Regex("""(?i)(access_token|refresh_token|id_token|client_secret|authorization|password|xsts_token|session_token)(\s*[:=]\s*)[^\s,"';}]+""")
            .replace(text, "$1$2<redacted>")
        return Regex("""(?i)Bearer\s+[A-Za-z0-9._~+/-]+=*""").replace(fields, "Bearer <redacted>")
    }

    private fun safePath(block: () -> File): File? = runCatching(block).getOrNull()
}
'''

def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, got {count}")
    return text.replace(old, new, 1)

def main():
    props = ROOT / "ZalithLauncher/gradle.properties"
    build = ROOT / "ZalithLauncher/build.gradle.kts"
    about = ROOT / "ZalithLauncher/src/main/java/com/movtery/zalithlauncher/ui/screens/content/settings/AboutInfoScreen.kt"
    app = ROOT / "ZalithLauncher/src/main/java/com/movtery/zalithlauncher/ZLApplication.kt"
    diag = ROOT / DIAG_REL
    required = [props, build, about, app]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        print("ERROR: Not at the root of a full ZalithLauncher2 checkout: " + ", ".join(missing), file=sys.stderr)
        return 2
    prop_text = props.read_text(encoding="utf-8")
    build_text = build.read_text(encoding="utf-8")
    about_text = about.read_text(encoding="utf-8")
    app_text = app.read_text(encoding="utf-8")
    if "launcher_version_name=2.6.1" not in prop_text:
        print("ERROR: source version is not exactly 2.6.1; no changes made", file=sys.stderr); return 2
    if build_text.count('applicationIdSuffix = ".v2"') != 1 or build_text.count('applicationIdSuffix = ".debug"') != 1:
        print("ERROR: application ID suffixes differ; refusing to risk overwriting official app", file=sys.stderr); return 2
    if diag.exists() or "RdcDiagnostics" in about_text or "RdcDiagnostics" in app_text:
        print("ERROR: patch already present or partial; refusing to overwrite", file=sys.stderr); return 2
    pkg_anchor = "package com.movtery.zalithlauncher.ui.screens.content.settings\n\n"
    coroutine_anchor = "import androidx.compose.runtime.remember\n"
    image_anchor = "import coil3.request.ImageRequest\n"
    func_anchor = "    openLink: (url: String) -> Unit\n) {\n    BaseScreen("
    author_anchor = "                        ButtonIconItem(\n                            icon = painterResource(R.drawable.img_avatar_movtery),"
    crash_anchor = "            showLauncherCrash(this@ZLApplication, throwable, th !is SplashException)"
    if any(about_text.count(x) != 1 for x in (pkg_anchor, coroutine_anchor, image_anchor, func_anchor, author_anchor)):
        print("ERROR: AboutInfoScreen source anchors changed; no changes made", file=sys.stderr); return 2
    if app_text.count("import com.movtery.zalithlauncher.utils.logging.Logger\n") != 1 or app_text.count(crash_anchor) != 1:
        print("ERROR: ZLApplication crash-handler anchors changed; no changes made", file=sys.stderr); return 2
    about_text = replace_once(about_text, pkg_anchor, pkg_anchor + "import android.widget.Toast\n", "package/import")
    about_text = replace_once(about_text, coroutine_anchor, coroutine_anchor + "import androidx.compose.runtime.rememberCoroutineScope\n", "coroutine import")
    about_text = replace_once(about_text, image_anchor, image_anchor + "import com.movtery.zalithlauncher.utils.diagnostics.RdcDiagnostics\nimport kotlinx.coroutines.Dispatchers\nimport kotlinx.coroutines.launch\nimport kotlinx.coroutines.withContext\n", "diagnostics imports")
    about_text = replace_once(about_text, func_anchor, "    openLink: (url: String) -> Unit\n) {\n    val rdcContext = LocalContext.current.applicationContext\n    val rdcScope = rememberCoroutineScope()\n\n    BaseScreen(", "screen function")
    card = '''                        ButtonIconItem(
                            icon = painterResource(R.drawable.ic_terminal_outlined),
                            title = "Reno MC Diagnostics (unofficial)",
                            text = "Export recent launcher, Minecraft and native crash logs to Downloads for RDC inspection. Accounts, databases and settings are excluded.",
                            button = {
                                Button(
                                    onClick = {
                                        rdcScope.launch {
                                            val result = withContext(Dispatchers.IO) {
                                                runCatching { RdcDiagnostics.export(rdcContext) }
                                            }
                                            val message = result.fold(
                                                onSuccess = { "Diagnostics saved: " + it },
                                                onFailure = { "Diagnostics export failed: " + (it.message ?: it.javaClass.simpleName) }
                                            )
                                            Toast.makeText(rdcContext, message, Toast.LENGTH_LONG).show()
                                        }
                                    }
                                ) {
                                    Text(text = "Export diagnostics")
                                }
                            }
                        )

'''
    about_text = replace_once(about_text, author_anchor, card + author_anchor, "About diagnostics button")
    app_text = replace_once(app_text, "import com.movtery.zalithlauncher.utils.logging.Logger\n",
        "import com.movtery.zalithlauncher.utils.logging.Logger\nimport com.movtery.zalithlauncher.utils.diagnostics.RdcDiagnostics\n", "crash import")
    app_text = replace_once(app_text, crash_anchor,
        "            // Best-effort local snapshot for RDC; never replace the original crash flow.\n" +
        "            RdcDiagnostics.tryExportCrashSnapshot(this@ZLApplication)\n\n" + crash_anchor, "crash snapshot")

    # All source anchors are verified and all replacements are prepared before any write.
    diag.parent.mkdir(parents=True, exist_ok=True)
    diag.write_text(DIAGNOSTICS, encoding="utf-8")
    about.write_text(about_text, encoding="utf-8")
    app.write_text(app_text, encoding="utf-8")
    props.write_text(prop_text.replace("launcher_name=ZalithLauncher", "launcher_name=Reno MC Diagnostics", 1)
        .replace("launcher_app_name=Zalith Launcher", "launcher_app_name=Reno MC Diagnostics (Unofficial)", 1)
        .replace("launcher_short_name=ZL2", "launcher_short_name=RMC-DIAG", 1), encoding="utf-8")
    print("Patch applied to Zalith Launcher 2.6.1")
    print("Added: diagnostics ZIP export, selected logcat/log files, best-effort crash snapshot")
    print("Package remains the separate debug variant; official app is not replaced.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
