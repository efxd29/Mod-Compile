package io.github.efxd29.keyboardchat;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Reads Android's IME bounds from the running launcher using reflection. UI hierarchy reads run on
 * Android's UI thread; the Minecraft render thread never waits for a response.
 */
public final class AndroidImeHeightProvider {
    private static final long REFRESH_INTERVAL_NANOS = 50_000_000L;
    private static final int UNKNOWN = -2;
    private static final int HIDDEN = -1;
    private static final AtomicBoolean REFRESH_QUEUED = new AtomicBoolean(false);
    private static final AtomicLong LAST_REQUEST_NS = new AtomicLong(0L);
    private static final boolean ANDROID_RUNTIME = hasAndroidRuntime();

    private static volatile int overlapPx;
    private static volatile int surfaceHeightPx;
    private static volatile boolean detectionKnown;

    private AndroidImeHeightProvider() {
    }

    /** Converts current keyboard overlap to Minecraft scaled GUI coordinates. */
    public static int getOffsetGui(final int guiHeight) {
        requestRefresh();
        if (guiHeight <= 0) {
            return 0;
        }

        final int overlap = overlapPx;
        final int surfaceHeight = surfaceHeightPx;
        if (detectionKnown && surfaceHeight > 0) {
            if (overlap <= 0) {
                return 0;
            }
            final int converted = (int) Math.ceil((double) overlap * guiHeight / surfaceHeight);
            return Math.max(0, Math.min(Math.max(0, guiHeight - 16), converted + 5));
        }

        // Last-resort Android-only safety positioning while activity/window introspection is
        // unavailable. Keep retrying real IME detection, but don't leave the chat underneath
        // the keyboard in launchers which hide their activity references from reflection.
        // Desktop Minecraft is never affected by this fallback.
        if (ANDROID_RUNTIME) {
            return Math.min(Math.max(0, guiHeight - 16),
                    Math.max(80, Math.round(guiHeight * 0.56F)));
        }
        return 0;
    }

    private static boolean hasAndroidRuntime() {
        try {
            Class.forName("android.app.Activity");
            return true;
        } catch (Throwable ignored) {
            return false;
        }
    }

    private static void requestRefresh() {
        final long now = System.nanoTime();
        final long previous = LAST_REQUEST_NS.get();
        if (now - previous < REFRESH_INTERVAL_NANOS
                || !LAST_REQUEST_NS.compareAndSet(previous, now)
                || !REFRESH_QUEUED.compareAndSet(false, true)) {
            return;
        }

        final Object activity = findCurrentActivity();
        if (activity == null) {
            detectionKnown = false;
            REFRESH_QUEUED.set(false);
            return;
        }

        final Runnable capture = () -> {
            try {
                captureOnUiThread(activity);
            } catch (Throwable ignored) {
                detectionKnown = false;
            } finally {
                REFRESH_QUEUED.set(false);
            }
        };

        try {
            Class.forName("android.app.Activity")
                    .getMethod("runOnUiThread", Runnable.class)
                    .invoke(activity, capture);
        } catch (Throwable ignored) {
            // Some forks use alternate Activity implementations; preserve safety if dispatch fails.
            detectionKnown = false;
            REFRESH_QUEUED.set(false);
        }
    }

    private static void captureOnUiThread(final Object activity) {
        final Object window = invoke(activity, "getWindow");
        final Object decor = invoke(window, "getDecorView");
        if (decor == null) {
            detectionKnown = false;
            return;
        }

        Object gameSurface = readField(activity, "gameSurfaceView");
        if (!isUsableView(gameSurface)) {
            gameSurface = findRenderSurface(decor, 0);
        }
        if (!isUsableView(gameSurface)) {
            gameSurface = decor;
        }

        final int surfaceHeight = intValue(invoke(gameSurface, "getHeight"), 0);
        if (surfaceHeight <= 0) {
            detectionKnown = false;
            return;
        }
        surfaceHeightPx = surfaceHeight;

        int imeTop = getKeyboardTopOnScreen(activity, decor);
        if (imeTop == UNKNOWN) {
            detectionKnown = false;
            return;
        }
        if (imeTop == HIDDEN) {
            overlapPx = 0;
            detectionKnown = true;
            return;
        }

        final int[] surfaceLocation = locationOnScreen(gameSurface);
        final int surfaceBottom = surfaceLocation[1] + surfaceHeight;
        // Use actual overlap rather than full keyboard height, since Zalith can move the game
        // surface upward in response to the IME itself.
        overlapPx = Math.max(0, surfaceBottom - imeTop);
        detectionKnown = true;
    }

    private static int getKeyboardTopOnScreen(final Object activity, final Object decor) {
        try {
            final Object insets = invoke(decor, "getRootWindowInsets");
            if (insets != null) {
                try {
                    final Class<?> typeClass = Class.forName("android.view.WindowInsets$Type");
                    final int imeType = intValue(typeClass.getMethod("ime").invoke(null), 0);
                    final boolean visible = Boolean.TRUE.equals(
                            insets.getClass().getMethod("isVisible", int.class).invoke(insets, imeType));
                    if (!visible) {
                        // Confirm via the visible-frame fallback before declaring the IME hidden;
                        // some launcher versions have stale root insets during keyboard animation.
                        final int fallback = getKeyboardTopFromVisibleFrame(activity, decor);
                        return fallback == UNKNOWN ? HIDDEN : fallback;
                    }

                    final Object imeInsets = insets.getClass().getMethod("getInsets", int.class)
                            .invoke(insets, imeType);
                    final int imeBottom = intValue(readField(imeInsets, "bottom"), 0);
                    if (imeBottom > 0) {
                        final Object root = invoke(decor, "getRootView");
                        final Object rootView = root == null ? decor : root;
                        final int rootHeight = intValue(invoke(rootView, "getHeight"), 0);
                        if (rootHeight > 0) {
                            return locationOnScreen(rootView)[1] + rootHeight - imeBottom;
                        }
                    }
                } catch (Throwable unsupportedImeApi) {
                    // Older Android: use the display-frame path below.
                }
            }
        } catch (Throwable ignored) {
            // Root window insets unavailable: use the compatibility path.
        }

        return getKeyboardTopFromVisibleFrame(activity, decor);
    }

    private static int getKeyboardTopFromVisibleFrame(final Object activity, final Object decor) {
        try {
            final Class<?> rectClass = Class.forName("android.graphics.Rect");
            final Object rect = rectClass.getConstructor().newInstance();
            decor.getClass().getMethod("getWindowVisibleDisplayFrame", rectClass).invoke(decor, rect);
            final int visibleBottom = intValue(readField(rect, "bottom"), 0);

            final Object manager = invoke(activity, "getWindowManager");
            final Object display = invoke(manager, "getDefaultDisplay");
            final Class<?> pointClass = Class.forName("android.graphics.Point");
            final Object point = pointClass.getConstructor().newInstance();
            display.getClass().getMethod("getRealSize", pointClass).invoke(display, point);
            final int screenHeight = intValue(readField(point, "y"), 0);
            if (screenHeight <= 0 || visibleBottom <= 0) {
                return UNKNOWN;
            }

            final int bottomGap = screenHeight - visibleBottom;
            if (bottomGap < Math.max(120, screenHeight / 8)) {
                return HIDDEN;
            }
            return visibleBottom;
        } catch (Throwable ignored) {
            return UNKNOWN;
        }
    }

    /**
     * On modern Android, explicitly unhide only the ActivityThread records needed for locating
     * Zalith's VMActivity. If that is unavailable, prefer SDL's active Activity before a generic
     * foreground activity to avoid measuring the launcher's previous screen.
     */
    private static Object findCurrentActivity() {
        enableActivityThreadReflection();
        Object bestVmActivity = null;
        Object focusedVmActivity = null;
        Object focusedSurfaceActivity = null;
        Object otherSurfaceActivity = null;

        try {
            final Class<?> threadClass = Class.forName("android.app.ActivityThread");
            final Method currentThread = threadClass.getDeclaredMethod("currentActivityThread");
            currentThread.setAccessible(true);
            final Object thread = currentThread.invoke(null);
            final Field activitiesField = threadClass.getDeclaredField("mActivities");
            activitiesField.setAccessible(true);
            final Object activities = activitiesField.get(thread);

            if (activities instanceof Map<?, ?> map) {
                for (Object record : map.values()) {
                    final Object activity = readField(record, "activity");
                    if (activity == null || Boolean.TRUE.equals(readField(record, "paused"))) {
                        continue;
                    }

                    final boolean isVmActivity =
                            activity.getClass().getName().endsWith(".VMActivity");
                    final boolean hasSurface = hasRenderSurface(
                            readField(activity, "gameSurfaceView")) ||
                            hasRenderSurface(invoke(invoke(activity, "getWindow"), "getDecorView"));
                    final boolean focused = hasWindowFocus(activity);

                    if (isVmActivity) {
                        if (focused) {
                            focusedVmActivity = activity;
                            break;
                        }
                        if (bestVmActivity == null) {
                            bestVmActivity = activity;
                        }
                    } else if (hasSurface && focused && focusedSurfaceActivity == null) {
                        focusedSurfaceActivity = activity;
                    } else if (hasSurface && otherSurfaceActivity == null) {
                        otherSurfaceActivity = activity;
                    }
                }
            }
        } catch (Throwable ignored) {
            // The targeted SDL reference below works on launcher builds that restrict hidden APIs.
        }

        if (focusedVmActivity != null) return focusedVmActivity;
        if (bestVmActivity != null) return bestVmActivity;

        final Object sdlActivity = findSdlActivity();
        if (sdlActivity != null) return sdlActivity;
        if (focusedSurfaceActivity != null) return focusedSurfaceActivity;
        return otherSurfaceActivity;
    }

    private static void enableActivityThreadReflection() {
        try {
            final Class<?> vmRuntimeClass = Class.forName("dalvik.system.VMRuntime");
            final Method getRuntime = vmRuntimeClass.getDeclaredMethod("getRuntime");
            getRuntime.setAccessible(true);
            final Object runtime = getRuntime.invoke(null);
            final Method exemptions = vmRuntimeClass.getDeclaredMethod(
                    "setHiddenApiExemptions", String[].class);
            exemptions.setAccessible(true);
            exemptions.invoke(runtime, (Object) new String[]{
                    "Landroid/app/ActivityThread;",
                    "Landroid/app/ActivityThread$ActivityClientRecord;"
            });
        } catch (Throwable ignored) {
            // Continue with public/launcher-specific fallbacks if runtime doesn't allow exemptions.
        }
    }

    private static Object findSdlActivity() {
        try {
            final Class<?> sdlActivity = Class.forName("org.libsdl.app.SDLActivity");
            final Object activity = readStaticField(sdlActivity, "mSingleton");
            return activity != null && invoke(activity, "getWindow") != null ? activity : null;
        } catch (Throwable ignored) {
            return null;
        }
    }

    private static boolean hasWindowFocus(final Object activity) {
        final Object decor = invoke(invoke(activity, "getWindow"), "getDecorView");
        return Boolean.TRUE.equals(invoke(decor, "hasWindowFocus"));
    }

    private static boolean isUsableView(final Object view) {
        return view != null && invoke(view, "getHeight") instanceof Number;
    }

    private static boolean hasRenderSurface(final Object view) {
        return view != null && findRenderSurface(view, 0) != null;
    }

    private static Object findRenderSurface(final Object view, final int depth) {
        if (view == null || depth > 12) {
            return null;
        }
        final String name = view.getClass().getName();
        if (name.endsWith("SurfaceView") || name.endsWith("TextureView")) {
            return view;
        }
        final int childCount = intValue(invoke(view, "getChildCount"), 0);
        for (int i = 0; i < childCount; i++) {
            final Object child = invoke(view, "getChildAt", new Class<?>[]{int.class}, i);
            final Object found = findRenderSurface(child, depth + 1);
            if (found != null) return found;
        }
        return null;
    }

    private static int[] locationOnScreen(final Object view) {
        final int[] location = new int[]{0, 0};
        if (view != null) {
            try {
                view.getClass().getMethod("getLocationOnScreen", int[].class)
                        .invoke(view, (Object) location);
            } catch (Throwable ignored) {
            }
        }
        return location;
    }

    private static Object invoke(final Object target, final String name) {
        return invoke(target, name, new Class<?>[0]);
    }

    private static Object invoke(final Object target, final String name,
                                 final Class<?>[] parameterTypes, final Object... arguments) {
        if (target == null) return null;
        try {
            return target.getClass().getMethod(name, parameterTypes).invoke(target, arguments);
        } catch (Throwable ignored) {
            return null;
        }
    }

    private static Object readField(final Object target, final String name) {
        if (target == null) return null;
        Class<?> type = target.getClass();
        while (type != null) {
            try {
                final Field field = type.getDeclaredField(name);
                field.setAccessible(true);
                return field.get(target);
            } catch (Throwable ignored) {
                type = type.getSuperclass();
            }
        }
        return null;
    }

    private static Object readStaticField(final Class<?> type, final String name) {
        try {
            final Field field = type.getDeclaredField(name);
            field.setAccessible(true);
            return field.get(null);
        } catch (Throwable ignored) {
            return null;
        }
    }

    private static int intValue(final Object value, final int fallback) {
        return value instanceof Number number ? number.intValue() : fallback;
    }
}
