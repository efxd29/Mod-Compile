package io.github.efxd29.keyboardchat;

import java.io.DataInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * Reads Zalith's existing ChatImeInsetBridge binary state.
 *
 * The embedded Minecraft OpenJDK VM does not expose Android WindowInsets APIs. The paired
 * launcher build publishes actual Android IME geometry to chat-ime-state.bin, using the format
 * [magic:int32 BE][imeBottomPx:int32 BE][physicalHeightPx:int32 BE].
 */
public final class AndroidImeHeightProvider {
    private static final int MAGIC = 0x5A43494D; // "ZCIM"
    private static final long POLL_INTERVAL_MS = 40L;

    private static volatile int imeBottomPx;
    private static volatile int physicalHeightPx;
    private static volatile boolean bridgeFound;

    private AndroidImeHeightProvider() {
    }

    static {
        final Thread reader = new Thread(AndroidImeHeightProvider::pollLoop, "KeyboardChat-IME-bridge");
        reader.setDaemon(true);
        reader.start();
    }

    /** Convert the real docked keyboard inset into Minecraft scaled GUI coordinates. */
    public static int getOffsetGui(final int guiHeight) {
        if (guiHeight <= 0 || !bridgeFound) {
            return 0;
        }

        final int ime = imeBottomPx;
        final int physical = physicalHeightPx;
        if (ime <= 0 || physical <= 0) {
            return 0;
        }

        // Physical IME pixels -> Minecraft scaled GUI pixels, plus a small visible gap.
        final int offset = (int) Math.ceil((double) ime * guiHeight / physical);
        return Math.max(0, Math.min(Math.max(0, guiHeight - 16), offset + 5));
    }

    private static void pollLoop() {
        final List<File> candidates = buildCandidatePaths();
        while (!Thread.currentThread().isInterrupted()) {
            boolean read = false;
            for (File candidate : candidates) {
                if (readState(candidate)) {
                    read = true;
                    break;
                }
            }

            bridgeFound = read;
            if (!read) {
                imeBottomPx = 0;
                physicalHeightPx = 0;
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
        if (file == null || !file.isFile() || !file.canRead() || file.length() < 12L) {
            return false;
        }

        try (DataInputStream input = new DataInputStream(new FileInputStream(file))) {
            final int magic = input.readInt();
            final int ime = input.readInt();
            final int physical = input.readInt();

            if (magic != MAGIC || ime < 0 || physical <= 0
                    || ime > physical * 2L) {
                return false;
            }

            imeBottomPx = ime;
            physicalHeightPx = physical;
            return true;
        } catch (Throwable ignored) {
            // The launcher may be updating the memory-mapped file while this read happens.
            return false;
        }
    }

    private static List<File> buildCandidatePaths() {
        final Set<String> roots = new LinkedHashSet<>();
        roots.add("/data/user/0");
        roots.add("/data/data");
        roots.add("/data/user_de/0");

        final Set<String> packages = new LinkedHashSet<>();
        packages.add("com.movtery.zalithlauncher.v2");
        packages.add("com.movtery.zalithlauncher.v2.debug");
        packages.add("com.movtery.zalithlauncher");

        final List<File> files = new ArrayList<>();
        for (String root : roots) {
            for (String packageName : packages) {
                files.add(new File(root + "/" + packageName + "/files/chat-ime-state.bin"));
            }
        }

        // Allow custom forks to provide the bridge path through a Java launch property.
        final String explicitPath = System.getProperty("keyboardchat.imeBridge");
        if (explicitPath != null && !explicitPath.isBlank()) {
            files.add(0, new File(explicitPath));
        }
        return files;
    }
}
