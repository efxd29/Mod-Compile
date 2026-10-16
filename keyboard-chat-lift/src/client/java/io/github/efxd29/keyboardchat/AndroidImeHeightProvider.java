package io.github.efxd29.keyboardchat;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Reads Android's real IME bounds using reflection so the mod has no android.jar dependency.
 * UI hierarchy reads are dispatched to the Android UI thread; the game render thread never waits.
 */
public final class AndroidImeHeightProvider {
    private static final long REFRESH_INTERVAL_NANOS = 50_000_000L;
    private static final int UNKNOWN = -2;
    private static final int HIDDEN = -1;
    private static final AtomicBoolean REFRESH_QUEUED = new AtomicBoolean(false);
    private static final AtomicLong LAST_REQUEST_NS = new AtomicLong(0L);

    private static volatile int overlapPx;
    private static volatile int surfaceHeightPx;

    private AndroidImeHeightProvider() {
    }

    /** Converts the current keyboard overlap into scaled Minecraft GUI coordinates. */
    public static int getOffsetGui(final int guiHeight) {
        requestRefresh();
        final int overlap = overlapPx;
        final int surfaceHeight = surfaceHeightPx;
        if (overlap <= 0 || surfaceHeight <= 0 || guiHeight <= 0) {
            return 0;
        }
        final int converted = (int) Math.ceil((double) overlap * guiHeight / surfaceHeight);
        // Five GUI pixels of clearance; never move the input outside the visible GUI.
        return Math.max(0, Math.min(Math.max(0, guiHeight - 16), converted + 5));
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
            overlapPx = 0;
            surfaceHeightPx = 0;
            REFRESH_QUEUED.set(false);
            return;
        }

        final Runnable capture = () -> {
            try {
                captureOnUiThread(activity);
            } catch (Throwable ignored) {
                // Android/launcher API differences must never crash Minecraft.
            } finally {
                REFRESH_QUEUED.set(false);
            }
        };

        try {
            final Class<?> activityClass = Class.forName("android.app.Activity");
            activityClass.getMethod("runOnUiThread", Runnable.class).invoke(activity, capture);
        } catch (Throwable ignored) {
            // Best-effort fallback: some Android runtimes restrict reflective Activity access.
            capture.run();
        }
    }

    private static void captureOnUiThread(final Object activity) {
        final Object window = invoke(activity, "getWindow");
        final Object decor = invoke(window, "getDecorView");
        if (decor == null) {
            overlapPx = 0;
            surfaceHeightPx = 0;
            return;
        }

        Object gameSurface = readField(activity, "gameSurfaceView");
        if (gameSurface == null) {
            gameSurface = findRenderSurface(decor, 0);
        }
        if (gameSurface == null) {
            gameSurface = decor;
        }

        final int surfaceHeight = intValue(invoke(gameSurface, "getHeight"), 0);
        surfaceHeightPx = surfaceHeight;
        if (surfaceHeight <= 0) {
            overlapPx = 0;
            return;
        }

        final int imeTop = getKeyboardTopOnScreen(activity, decor);
        if (imeTop == HIDDEN || imeTop == UNKNOWN) {
            overlapPx = 0;
            return;
        }

        final int[] surfaceLocation = locationOnScreen(gameSurface);
        final int surfaceBottom = surfaceLocation[1] + surfaceHeight;
        // Count only the part of the IME that actually overlaps the rendered game surface.
        // Zalith can translate that surface upward itself; using the full IME height would
        // double-count that movement and over-shift the chat.
        overlapPx = Math.max(0, surfaceBottom - imeTop);
    }

    /** Returns the IME top edge in screen pixels, HIDDEN, or UNKNOWN. */
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
                        return HIDDEN;
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
                    // Some floating IMEs report visibility but no docked bottom inset.
                } catch (Throwable unsupportedImeApi) {
                    // Use the compatibility path on older Android releases.
                }
            }
        } catch (Throwable ignored) {
            // Use the compatibility path when root insets are unavailable.
        }
        return getKeyboardTopFromVisibleFrame(activity, decor);
    }

    /** Compatibility path for Android releases/configurations without WindowInsets.Type.ime(). */
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
            // Avoid treating the navigation bar/status area as a keyboard.
            if (bottomGap < Math.max(120, screenHeight / 8)) {
                return HIDDEN;
            }
            return visibleBottom;
        } catch (Throwable ignored) {
            return UNKNOWN;
        }
    }

    /** Prefer Zalith's VMActivity, then another unpaused Android activity (for launcher forks). */
    private static Object findCurrentActivity() {
        Object foregroundCandidate = null;
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
                    if (activity.getClass().getName().endsWith(".VMActivity")) {
                        return activity;
                    }
                    if (foregroundCandidate == null) {
                        foregroundCandidate = activity;
                    }
                }
            }
        } catch (Throwable ignored) {
            // Android may restrict hidden ActivityThread APIs. Try SDL's activity reference next.
        }

        if (foregroundCandidate != null) {
            return foregroundCandidate;
        }
        try {
            final Class<?> sdlActivity = Class.forName("org.libsdl.app.SDLActivity");
            final Object activity = readStaticField(sdlActivity, "mSingleton");
            if (activity != null) {
                return activity;
            }
        } catch (Throwable ignored) {
            // Other launchers may not bundle SDL.
        }
        return null;
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
            if (found != null) {
                return found;
            }
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

    private static Object invoke(final Object target, final String methodName) {
        return invoke(target, methodName, new Class<?>[0]);
    }

    private static Object invoke(final Object target, final String methodName,
                                 final Class<?>[] parameterTypes, final Object... arguments) {
        if (target == null) {
            return null;
        }
        try {
            return target.getClass().getMethod(methodName, parameterTypes).invoke(target, arguments);
        } catch (Throwable ignored) {
            return null;
        }
    }

    private static Object readField(final Object target, final String name) {
        if (target == null) {
            return null;
        }
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
