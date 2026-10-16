package io.github.efxd29.keyboardchat;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * Reads the live IME state published by the patched Zalith Android activity.
 *
 * Minecraft runs inside an embedded OpenJDK VM, which cannot directly query Android's
 * android.app.Activity or WindowInsets APIs. The launcher therefore writes a tiny heartbeat
 * file in its app-specific external-files directory. This class only reads that file.
 */
public final class AndroidImeHeightProvider {
    private static final long POLL_INTERVAL_MS = 60L;
    private static final long MAX_STATE_AGE_MS = 2_500L;

    private static volatile long stateTimestampMs;
    private static volatile int imeHeightPx;
    private static volatile int screenHeightPx;
    private static volatile int surfaceShiftPx;

    private AndroidImeHeightProvider() {
    }

    static {
        final Thread reader = new Thread(AndroidImeHeightProvider::pollLoop, "KeyboardChat-IME-bridge");
        reader.setDaemon(true);
        reader.start();
    }

    /**
     * Converts the part of the keyboard that still overlaps the Minecraft surface into GUI units.
     * Zalith already moves the surface by surfaceShiftPx for its own input-area feature, so that
     * amount is subtracted to avoid shifting the vanilla chat twice.
     */
    public static int getOffsetGui(final int guiHeight) {
        if (guiHeight <= 0) {
            return 0;
        }

        final long timestamp = stateTimestampMs;
        final int ime = imeHeightPx;
        final int screen = screenHeightPx;
        final int surfaceShift = surfaceShiftPx;
        if (timestamp <= 0L || System.currentTimeMillis() - timestamp > MAX_STATE_AGE_MS
                || ime <= 0 || screen <= 0) {
            return 0;
        }

        final int uncoveredOverlapPx = Math.max(0, ime - surfaceShift);
        if (uncoveredOverlapPx == 0) {
            return 0;
        }

        final int guiOffset = Math.round(uncoveredOverlapPx * (float) guiHeight / screen);
        // Leave a small gap above the actual keyboard edge for the input box.
        return Math.max(0, Math.min(guiHeight - 16, guiOffset + 5));
    }

    private static void pollLoop() {
        final List<File> paths = candidateFiles();
        while (!Thread.currentThread().isInterrupted()) {
            boolean found = false;
            for (File file : paths) {
                if (readState(file)) {
                    found = true;
                    break;
                }
            }

            if (!found) {
                stateTimestampMs = 0L;
                imeHeightPx = 0;
                screenHeightPx = 0;
                surfaceShiftPx = 0;
            }

            try {
                Thread.sleep(POLL_INTERVAL_MS);
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
                return;
            }
        }
    }

    private static boolean readState(final File file) {
        if (file == null || !file.isFile() || !file.canRead()) {
            return false;
        }

        try (BufferedReader reader = new BufferedReader(new FileReader(file))) {
            final String line = reader.readLine();
            if (line == null) {
                return false;
            }

            final String[] values = line.trim().split(",");
            if (values.length < 4) {
                return false;
            }

            final long timestamp = Long.parseLong(values[0]);
            final int ime = Integer.parseInt(values[1]);
            final int screen = Integer.parseInt(values[2]);
            final int shift = Integer.parseInt(values[3]);
            if (timestamp <= 0L || screen <= 0 || ime < 0 || shift < 0
                    || ime > screen * 2 || shift > screen * 2) {
                return false;
            }

            if (System.currentTimeMillis() - timestamp > MAX_STATE_AGE_MS) {
                return false;
            }

            imeHeightPx = ime;
            screenHeightPx = screen;
            surfaceShiftPx = shift;
            stateTimestampMs = timestamp;
            return true;
        } catch (Throwable ignored) {
            // Ignore partial writes, missing permissions, and stale/incompatible state files.
            return false;
        }
    }

    private static List<File> candidateFiles() {
        final Set<String> roots = new LinkedHashSet<>();
        final String external = System.getenv("EXTERNAL_STORAGE");
        if (external != null && !external.isBlank()) {
            roots.add(external);
        }
        roots.add("/storage/emulated/0");
        roots.add("/sdcard");

        final Set<String> packages = Set.of(
                "com.movtery.zalithlauncher.v2",
                "com.movtery.zalithlauncher.v2.debug",
                "com.movtery.zalithlauncher"
        );

        final List<File> result = new ArrayList<>();
        for (String root : roots) {
            for (String packageName : packages) {
                result.add(new File(root, "Android/data/" + packageName
                        + "/files/keyboard-chat-lift/ime-height.txt"));
            }
        }

        // Also cover launchers that place the game directory directly under the app's external files.
        addUserDirectoryCandidates(result, System.getProperty("user.home"));
        addUserDirectoryCandidates(result, System.getProperty("user.dir"));
        return result;
    }

    private static void addUserDirectoryCandidates(final List<File> result, final String value) {
        if (value == null || value.isBlank()) {
            return;
        }

        File directory = new File(value).getAbsoluteFile();
        for (int i = 0; i < 6 && directory != null; i++, directory = directory.getParentFile()) {
            result.add(new File(directory, "keyboard-chat-lift/ime-height.txt"));
        }
    }
}
