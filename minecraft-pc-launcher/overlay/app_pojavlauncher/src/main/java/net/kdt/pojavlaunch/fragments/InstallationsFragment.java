package net.kdt.pojavlaunch.fragments;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.TextUtils;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ImageView;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.HorizontalScrollView;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;

import net.kdt.pojavlaunch.PojavApplication;
import net.kdt.pojavlaunch.Tools;
import net.kdt.pojavlaunch.instances.DisplayInstance;
import net.kdt.pojavlaunch.instances.Instance;
import net.kdt.pojavlaunch.instances.InstanceIconProvider;
import net.kdt.pojavlaunch.instances.Instances;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** A launcher-style installation manager backed by the engine's real profiles. */
public final class InstallationsFragment extends Fragment {
    public static final String TAG = "InstallationsFragment";

    private static final int BG = Color.rgb(24, 27, 24);
    private static final int SURFACE = Color.rgb(39, 43, 39);
    private static final int BORDER = Color.rgb(63, 69, 63);
    private static final int ACCENT = Color.rgb(98, 180, 69);
    private static final int TEXT = Color.rgb(245, 246, 243);
    private static final int MUTED = Color.rgb(181, 190, 180);

    private static final int FILTER_ALL = 0;
    private static final int FILTER_RELEASES = 1;
    private static final int FILTER_SNAPSHOTS = 2;
    private static final int FILTER_MODDED = 3;

    private LinearLayout profileContainer;
    private LinearLayout filterRow;
    private TextView statusText;
    private ProgressBar progressBar;
    private EditText searchField;
    private Button[] filterButtons;
    private Instances loadedData;
    private int activeFilter = FILTER_ALL;
    private String searchQuery = "";

    public InstallationsFragment() { super(); }

    @Nullable
    @Override
    public View onCreateView(@NonNull android.view.LayoutInflater inflater,
                             @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {
        Context c = requireContext();
        ScrollView scroll = new ScrollView(c);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(BG);

        LinearLayout content = new LinearLayout(c);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(c, 16), dp(c, 12), dp(c, 16), dp(c, 24));
        scroll.addView(content, new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        LinearLayout top = new LinearLayout(c);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(Gravity.CENTER_VERTICAL);
        content.addView(top, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(c, 52)));

        TextView back = new TextView(c);
        back.setText("‹");
        back.setTextColor(TEXT);
        back.setTextSize(34);
        back.setGravity(Gravity.CENTER);
        top.addView(back, new LinearLayout.LayoutParams(dp(c, 42),
                ViewGroup.LayoutParams.MATCH_PARENT));
        back.setOnClickListener(v -> Tools.backToMainMenu(requireActivity()));

        TextView title = new TextView(c);
        title.setText("Installations");
        title.setTextColor(TEXT);
        title.setTextSize(23);
        title.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        LinearLayout.LayoutParams titleParams = new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        titleParams.leftMargin = dp(c, 4);
        top.addView(title, titleParams);

        TextView refresh = new TextView(c);
        refresh.setText("↻");
        refresh.setTextColor(TEXT);
        refresh.setTextSize(27);
        refresh.setGravity(Gravity.CENTER);
        refresh.setContentDescription("Refresh installations");
        refresh.setBackground(shape(SURFACE, BORDER, dp(c, 6)));
        top.addView(refresh, new LinearLayout.LayoutParams(dp(c, 42), dp(c, 42)));
        refresh.setOnClickListener(v -> {
            if (progressBar != null) progressBar.setVisibility(View.VISIBLE);
            if (statusText != null) statusText.setText("Refreshing installations…");
            loadProfiles();
        });

        Button add = makeButton(c, "+  New Installation", ACCENT);
        LinearLayout.LayoutParams addParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(c, 50));
        addParams.topMargin = dp(c, 8);
        content.addView(add, addParams);
        add.setOnClickListener(v -> Tools.swapFragment(requireActivity(),
                ProfileTypeSelectFragment.class, ProfileTypeSelectFragment.TAG, null));

        TextView description = new TextView(c);
        description.setText("Manage game versions and launcher profiles");
        description.setTextColor(MUTED);
        description.setTextSize(13);
        LinearLayout.LayoutParams descParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        descParams.topMargin = dp(c, 16);
        content.addView(description, descParams);

        searchField = new EditText(c);
        searchField.setSingleLine(true);
        searchField.setTextSize(14);
        searchField.setTextColor(TEXT);
        searchField.setHintTextColor(Color.rgb(137, 147, 136));
        searchField.setHint("Search installations");
        searchField.setPadding(dp(c, 14), 0, dp(c, 14), 0);
        searchField.setBackground(shape(SURFACE, BORDER, dp(c, 6)));
        LinearLayout.LayoutParams searchParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(c, 48));
        searchParams.topMargin = dp(c, 16);
        content.addView(searchField, searchParams);
        searchField.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) {
                searchQuery = s == null ? "" : s.toString().trim().toLowerCase(Locale.ROOT);
                if (loadedData != null && profileContainer != null) renderFilteredProfiles();
            }
            @Override public void afterTextChanged(Editable s) {}
        });

        HorizontalScrollView filterScroll = new HorizontalScrollView(c);
        filterScroll.setHorizontalScrollBarEnabled(false);
        LinearLayout.LayoutParams filterScrollParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(c, 42));
        filterScrollParams.topMargin = dp(c, 8);
        content.addView(filterScroll, filterScrollParams);
        filterRow = new LinearLayout(c);
        filterRow.setOrientation(LinearLayout.HORIZONTAL);
        filterRow.setGravity(Gravity.CENTER_VERTICAL);
        filterScroll.addView(filterRow, new HorizontalScrollView.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.MATCH_PARENT));

        String[] filterLabels = {"All", "Releases", "Snapshots", "Modded"};
        filterButtons = new Button[filterLabels.length];
        for (int i = 0; i < filterLabels.length; i++) {
            final int filter = i;
            Button chip = makeButton(c, filterLabels[i],
                    filter == activeFilter ? ACCENT : SURFACE);
            chip.setTextSize(12);
            LinearLayout.LayoutParams chipParams = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, dp(c, 34));
            if (i > 0) chipParams.leftMargin = dp(c, 8);
            filterRow.addView(chip, chipParams);
            filterButtons[i] = chip;
            chip.setOnClickListener(v -> {
                activeFilter = filter;
                updateFilterButtons();
                if (loadedData != null && profileContainer != null) renderFilteredProfiles();
            });
        }

        LinearLayout loading = new LinearLayout(c);
        loading.setOrientation(LinearLayout.HORIZONTAL);
        loading.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout.LayoutParams loadingParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(c, 42));
        loadingParams.topMargin = dp(c, 8);
        content.addView(loading, loadingParams);

        progressBar = new ProgressBar(c, null, android.R.attr.progressBarStyleSmall);
        loading.addView(progressBar, new LinearLayout.LayoutParams(dp(c, 22), dp(c, 22)));
        statusText = new TextView(c);
        statusText.setText("Loading installations…");
        statusText.setTextColor(MUTED);
        statusText.setTextSize(12);
        LinearLayout.LayoutParams statusParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        statusParams.leftMargin = dp(c, 10);
        loading.addView(statusText, statusParams);

        profileContainer = new LinearLayout(c);
        profileContainer.setOrientation(LinearLayout.VERTICAL);
        LinearLayout.LayoutParams profilesParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        profilesParams.topMargin = dp(c, 4);
        content.addView(profileContainer, profilesParams);
        return scroll;
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);
        loadProfiles();
    }

    private void loadProfiles() {
        PojavApplication.sExecutorService.execute(() -> {
            try {
                Instances data = Instances.loadDisplay();
                new Handler(Looper.getMainLooper()).post(() -> {
                    if (!isAdded() || getView() == null || profileContainer == null) return;
                    renderProfiles(data);
                });
            } catch (IOException error) {
                new Handler(Looper.getMainLooper()).post(() -> {
                    if (!isAdded() || getView() == null || statusText == null) return;
                    if (progressBar != null) progressBar.setVisibility(View.GONE);
                    statusText.setText("Couldn't load installations. Go back and retry.");
                    Tools.showError(requireContext(), error);
                });
            }
        });
    }

    private void renderProfiles(@NonNull Instances data) {
        loadedData = data;
        if (progressBar != null) progressBar.setVisibility(View.GONE);
        updateFilterButtons();
        renderFilteredProfiles();
    }

    private void renderFilteredProfiles() {
        if (loadedData == null || profileContainer == null || !isAdded()) return;
        Context c = requireContext();
        profileContainer.removeAllViews();

        List<Integer> visibleIndices = new ArrayList<>();
        for (int i = 0; i < loadedData.list.size(); i++) {
            DisplayInstance profile = loadedData.list.get(i);
            if (matchesSearchAndFilter(profile)) visibleIndices.add(i);
        }

        if (statusText != null) {
            if (searchQuery.isEmpty() && activeFilter == FILTER_ALL) {
                statusText.setText(loadedData.list.size()
                        + (loadedData.list.size() == 1 ? " installation" : " installations"));
            } else {
                statusText.setText("Showing " + visibleIndices.size() + " of "
                        + loadedData.list.size() + " installations");
            }
        }

        if (loadedData.list.isEmpty()) {
            showEmptyState(c, "No installations yet",
                    "Create an installation to choose a Minecraft Java Edition version or mod loader.");
            return;
        }
        if (visibleIndices.isEmpty()) {
            showEmptyState(c, "No matching installations",
                    "Try another search or choose a different filter.");
            Button clear = makeButton(c, "Clear search and filters", ACCENT);
            LinearLayout.LayoutParams clearParams = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, dp(c, 44));
            clearParams.topMargin = dp(c, 10);
            profileContainer.addView(clear, clearParams);
            clear.setOnClickListener(v -> {
                searchQuery = "";
                activeFilter = FILTER_ALL;
                if (searchField != null) searchField.setText("");
                updateFilterButtons();
                renderFilteredProfiles();
            });
            return;
        }

        for (int index : visibleIndices) {
            DisplayInstance profile = loadedData.list.get(index);
            LinearLayout.LayoutParams cardParams = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            cardParams.bottomMargin = dp(c, 10);
            profileContainer.addView(
                    makeProfileCard(c, profile, index == loadedData.selectedIndex), cardParams);
        }
    }

    private void showEmptyState(Context c, String title, String message) {
        TextView emptyTitle = new TextView(c);
        emptyTitle.setText(title);
        emptyTitle.setTextColor(TEXT);
        emptyTitle.setTextSize(17);
        emptyTitle.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        LinearLayout.LayoutParams titleParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        titleParams.topMargin = dp(c, 18);
        profileContainer.addView(emptyTitle, titleParams);

        TextView emptyHint = new TextView(c);
        emptyHint.setText(message);
        emptyHint.setTextColor(MUTED);
        emptyHint.setTextSize(13);
        emptyHint.setPadding(0, dp(c, 6), 0, dp(c, 16));
        profileContainer.addView(emptyHint, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
    }

    private boolean matchesSearchAndFilter(DisplayInstance profile) {
        String name = profile.name == null ? "" : profile.name;
        String rawVersion = profile.versionId == null ? "" : profile.versionId;
        String loader = getLoaderLabel(rawVersion);
        String searchable = (name + " " + rawVersion + " "
                + getDisplayVersion(rawVersion) + " " + loader).toLowerCase(Locale.ROOT);
        if (!searchQuery.isEmpty() && !searchable.contains(searchQuery)) return false;

        boolean snapshot = isSnapshotVersion(rawVersion);
        boolean modded = isModdedVersion(rawVersion);
        switch (activeFilter) {
            case FILTER_RELEASES:
                return !snapshot && !modded;
            case FILTER_SNAPSHOTS:
                return snapshot;
            case FILTER_MODDED:
                return modded;
            case FILTER_ALL:
            default:
                return true;
        }
    }

    private boolean isSnapshotVersion(String versionId) {
        String id = versionId == null ? "" : versionId.toLowerCase(Locale.ROOT);
        return Instance.VERSION_LATEST_SNAPSHOT.equalsIgnoreCase(id)
                || id.contains("snapshot")
                || java.util.regex.Pattern.compile(".*\\\\d{2}w\\\\d{2}[a-z].*").matcher(id).matches()
                || id.contains("-pre-") || id.contains("-rc")
                || id.contains("experimental");
    }

    private boolean isModdedVersion(String versionId) {
        String id = versionId == null ? "" : versionId.toLowerCase(Locale.ROOT);
        String loader = getLoaderLabel(id);
        return !loader.equals("VANILLA") && !loader.equals("RELEASE")
                && !loader.equals("SNAPSHOT");
    }

    private void updateFilterButtons() {
        if (filterButtons == null) return;
        for (int i = 0; i < filterButtons.length; i++) {
            filterButtons[i].setBackground(shape(
                    i == activeFilter ? ACCENT : SURFACE,
                    i == activeFilter ? ACCENT : BORDER, dp(requireContext(), 5)));
        }
    }

    private View makeProfileCard(Context c, DisplayInstance profile, boolean selected) {
        LinearLayout card = new LinearLayout(c);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(c, 14), dp(c, 13), dp(c, 14), dp(c, 12));
        card.setBackground(shape(selected ? Color.rgb(39, 54, 37) : SURFACE,
                selected ? ACCENT : BORDER, dp(c, 7)));

        String name = profile.name == null ? "" : profile.name.trim();
        String rawVersion = profile.versionId == null ? "Unknown version" : profile.versionId.trim();
        String version = getDisplayVersion(rawVersion);
        String loader = getLoaderLabel(rawVersion);
        if (name.isEmpty() || "New".equalsIgnoreCase(name)) name = version;

        LinearLayout titleLine = new LinearLayout(c);
        titleLine.setOrientation(LinearLayout.HORIZONTAL);
        titleLine.setGravity(Gravity.CENTER_VERTICAL);
        card.addView(titleLine, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        ImageView profileIcon = new ImageView(c);
        profileIcon.setImageDrawable(InstanceIconProvider.fetchIcon(c.getResources(), profile));
        profileIcon.setScaleType(ImageView.ScaleType.CENTER_CROP);
        profileIcon.setContentDescription(name + " icon");
        LinearLayout.LayoutParams iconParams = new LinearLayout.LayoutParams(dp(c, 44), dp(c, 44));
        iconParams.rightMargin = dp(c, 10);
        titleLine.addView(profileIcon, iconParams);

        TextView nameView = new TextView(c);
        nameView.setText(name);
        nameView.setTextColor(TEXT);
        nameView.setTextSize(16);
        nameView.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        nameView.setSingleLine(true);
        nameView.setEllipsize(TextUtils.TruncateAt.END);
        titleLine.addView(nameView, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        TextView loaderBadge = new TextView(c);
        loaderBadge.setText(loader);
        loaderBadge.setTextColor(loader.equals("VANILLA")
                ? Color.rgb(207, 215, 203) : Color.rgb(185, 226, 169));
        loaderBadge.setTextSize(9);
        loaderBadge.setTypeface(Typeface.DEFAULT_BOLD);
        loaderBadge.setPadding(dp(c, 7), dp(c, 4), dp(c, 7), dp(c, 4));
        loaderBadge.setBackground(shape(Color.rgb(42, 47, 41), BORDER, dp(c, 4)));
        titleLine.addView(loaderBadge, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        if (selected) {
            TextView badge = new TextView(c);
            badge.setText("SELECTED");
            badge.setTextColor(Color.rgb(178, 226, 160));
            badge.setTextSize(9);
            badge.setTypeface(Typeface.DEFAULT_BOLD);
            badge.setPadding(dp(c, 8), dp(c, 4), dp(c, 8), dp(c, 4));
            badge.setBackground(shape(Color.rgb(43, 66, 39), ACCENT, dp(c, 4)));
            LinearLayout.LayoutParams selectedParams = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            selectedParams.leftMargin = dp(c, 6);
            titleLine.addView(badge, selectedParams);
        }

        TextView versionView = new TextView(c);
        versionView.setText("Minecraft Java Edition  •  " + version);
        versionView.setTextColor(MUTED);
        versionView.setTextSize(12);
        LinearLayout.LayoutParams versionParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        versionParams.topMargin = dp(c, 5);
        card.addView(versionView, versionParams);

        LinearLayout actions = new LinearLayout(c);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        actions.setGravity(Gravity.END);
        LinearLayout.LayoutParams actionsParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(c, 42));
        actionsParams.topMargin = dp(c, 12);
        card.addView(actions, actionsParams);

        Button edit = makeButton(c, "Edit", Color.rgb(63, 69, 62));
        actions.addView(edit, new LinearLayout.LayoutParams(dp(c, 90),
                ViewGroup.LayoutParams.MATCH_PARENT));
        edit.setOnClickListener(v -> {
            Instances.setSelectedInstance(profile);
            Tools.swapFragment(requireActivity(), InstanceEditorFragment.class,
                    InstanceEditorFragment.TAG, null);
        });

        Button select = makeButton(c, selected ? "Selected" : "Select",
                selected ? Color.rgb(52, 72, 48) : ACCENT);
        LinearLayout.LayoutParams selectParams = new LinearLayout.LayoutParams(dp(c, 102),
                ViewGroup.LayoutParams.MATCH_PARENT);
        selectParams.leftMargin = dp(c, 8);
        actions.addView(select, selectParams);
        select.setEnabled(!selected);
        select.setOnClickListener(v -> {
            Instances.setSelectedInstance(profile);
            Tools.backToMainMenu(requireActivity());
        });

        return card;
    }

    private static String getLoaderLabel(String versionId) {
        String id = versionId == null ? "" : versionId.toLowerCase(java.util.Locale.ROOT);
        if (Instance.VERSION_LATEST_RELEASE.equalsIgnoreCase(id)) return "RELEASE";
        if (Instance.VERSION_LATEST_SNAPSHOT.equalsIgnoreCase(id)) return "SNAPSHOT";
        if (id.contains("legacyfabric") || id.contains("legacy-fabric")) return "LEGACY FABRIC";
        if (id.contains("neoforge")) return "NEOFORGE";
        if (id.contains("fabric")) return "FABRIC";
        if (id.contains("quilt")) return "QUILT";
        if (id.contains("forge")) return "FORGE";
        if (id.contains("optifine")) return "OPTIFINE";
        if (id.contains("liteloader")) return "LITELOADER";
        if (id.contains("bta") || id.contains("better-than-adventure")) return "BTA";
        return "VANILLA";
    }

    private static String getDisplayVersion(String versionId) {
        if (versionId == null || versionId.trim().isEmpty()) return "Unknown version";
        if (Instance.VERSION_LATEST_RELEASE.equalsIgnoreCase(versionId)) return "Latest Release";
        if (Instance.VERSION_LATEST_SNAPSHOT.equalsIgnoreCase(versionId)) return "Latest Snapshot";

        java.util.regex.Matcher matcher = java.util.regex.Pattern
                .compile("(?<!\\\\d)\\\\d+(?:\\\\.\\\\d+){1,3}(?!\\\\d)")
                .matcher(versionId);
        String first = null;
        String last = null;
        while (matcher.find()) {
            if (first == null) first = matcher.group();
            last = matcher.group();
        }
        if (first == null) return versionId;

        String lower = versionId.toLowerCase(java.util.Locale.ROOT);
        // Loader profile IDs may begin with the loader's own version. In those
        // forms the Minecraft target version is the final numeric version.
        if (lower.startsWith("fabric-loader-") || lower.startsWith("quilt-loader-")
                || lower.startsWith("legacy-fabric") || lower.startsWith("legacyfabric")
                || lower.startsWith("neoforge-")) {
            return last;
        }
        return first;
    }

    private static Button makeButton(Context c, String label, int color) {
        Button b = new Button(c);
        b.setText(label);
        b.setTextColor(TEXT);
        b.setTextSize(13);
        b.setAllCaps(false);
        b.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        b.setMinHeight(0);
        b.setMinimumHeight(0);
        b.setPadding(dp(c, 12), 0, dp(c, 12), 0);
        b.setBackground(shape(color, color, dp(c, 5)));
        return b;
    }

    private static GradientDrawable shape(int fill, int stroke, int radius) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(fill);
        drawable.setCornerRadius(radius);
        drawable.setStroke(2, stroke);
        return drawable;
    }

    private static int dp(Context c, int value) {
        return (int) (value * c.getResources().getDisplayMetrics().density + 0.5f);
    }

    @Override
    public void onDestroyView() {
        profileContainer = null;
        filterRow = null;
        filterButtons = null;
        searchField = null;
        loadedData = null;
        statusText = null;
        progressBar = null;
        super.onDestroyView();
    }
}
