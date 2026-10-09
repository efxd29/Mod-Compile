package net.kdt.pojavlaunch.fragments;

import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import androidx.activity.OnBackPressedCallback;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;

import net.kdt.pojavlaunch.Tools;

/**
 * In-launcher news/changelog reader. Only Minecraft-owned web pages are kept
 * inside the app; off-site links open in the user's browser.
 */
public final class MinecraftWebFragment extends Fragment {
    public static final String TAG = "MinecraftWebFragment";
    public static final String ARG_TITLE = "minecraft_web_title";
    public static final String ARG_URL = "minecraft_web_url";

    private WebView webView;
    private ProgressBar progressBar;

    public MinecraftWebFragment() {
        super();
    }

    @Nullable
    @Override
    public View onCreateView(@NonNull android.view.LayoutInflater inflater,
                             @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {
        Context context = requireContext();
        String title = getArguments() == null ? "Minecraft" :
                getArguments().getString(ARG_TITLE, "Minecraft");
        String url = getArguments() == null ? null :
                getArguments().getString(ARG_URL);

        LinearLayout root = new LinearLayout(context);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(20, 23, 20));

        LinearLayout header = new LinearLayout(context);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(dp(context, 8), 0, dp(context, 12), 0);
        header.setBackgroundColor(Color.rgb(28, 34, 28));
        root.addView(header, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(context, 54)));

        TextView back = new TextView(context);
        back.setText("‹");
        back.setTextColor(Color.WHITE);
        back.setTextSize(34);
        back.setGravity(Gravity.CENTER);
        header.addView(back, new LinearLayout.LayoutParams(dp(context, 44),
                ViewGroup.LayoutParams.MATCH_PARENT));

        TextView heading = new TextView(context);
        heading.setText(title);
        heading.setTextColor(Color.WHITE);
        heading.setTextSize(17);
        heading.setTypeface(android.graphics.Typeface.create("sans-serif-medium",
                android.graphics.Typeface.NORMAL));
        heading.setSingleLine(true);
        heading.setEllipsize(android.text.TextUtils.TruncateAt.END);
        LinearLayout.LayoutParams headingParams = new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.MATCH_PARENT, 1f);
        headingParams.leftMargin = dp(context, 6);
        header.addView(heading, headingParams);

        progressBar = new ProgressBar(context, null,
                android.R.attr.progressBarStyleHorizontal);
        progressBar.setIndeterminate(true);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            progressBar.setIndeterminateTintList(
                    android.content.res.ColorStateList.valueOf(Color.rgb(112, 190, 91)));
        }
        root.addView(progressBar, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(context, 2)));
        progressBar.setVisibility(View.GONE);

        webView = new WebView(context);
        webView.setBackgroundColor(Color.WHITE);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setSupportMultipleWindows(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            settings.setSafeBrowsingEnabled(true);
        }

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(@NonNull WebView view,
                                                    @NonNull WebResourceRequest request) {
                return routeNavigation(request.getUrl());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                return routeNavigation(Uri.parse(url));
            }

            @Override
            public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
                if (progressBar != null) progressBar.setVisibility(View.VISIBLE);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                if (progressBar != null) progressBar.setVisibility(View.GONE);
            }
        });
        root.addView(webView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        back.setOnClickListener(v -> navigateBack());

        if (url != null && isMinecraftOwnedPage(Uri.parse(url))) {
            webView.loadUrl(url);
        } else {
            heading.setText("Unavailable page");
            webView.loadData(
                    "<html><body style='font-family:sans-serif;padding:24px;color:#222'>"
                            + "<h2>Page unavailable</h2><p>This launcher only opens approved Minecraft pages here.</p>"
                            + "</body></html>", "text/html", "UTF-8");
        }
        return root;
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);
        requireActivity().getOnBackPressedDispatcher().addCallback(
                getViewLifecycleOwner(), new OnBackPressedCallback(true) {
                    @Override
                    public void handleOnBackPressed() {
                        navigateBack();
                    }
                });
    }

    private boolean routeNavigation(Uri uri) {
        if (isMinecraftOwnedPage(uri)) return false;

        String scheme = uri.getScheme();
        if ("http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme)) {
            try {
                startActivity(new Intent(Intent.ACTION_VIEW, uri));
            } catch (Exception ignored) {
                // If no browser is installed, remain on the current page.
            }
        }
        return true;
    }

    private boolean isMinecraftOwnedPage(Uri uri) {
        if (uri == null) return false;
        String scheme = uri.getScheme();
        String host = uri.getHost();
        if (!"https".equalsIgnoreCase(scheme) || host == null) return false;
        String normalizedHost = host.toLowerCase(java.util.Locale.ROOT);
        return normalizedHost.equals("minecraft.net")
                || normalizedHost.endsWith(".minecraft.net");
    }

    private void navigateBack() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else if (isAdded()) {
            Tools.removeCurrentFragment(requireActivity());
        }
    }

    private static int dp(Context context, int value) {
        return (int) (value * context.getResources().getDisplayMetrics().density + 0.5f);
    }

    @Override
    public void onDestroyView() {
        if (webView != null) {
            webView.stopLoading();
            webView.setWebViewClient(null);
            if (webView.getParent() instanceof ViewGroup) {
                ((ViewGroup) webView.getParent()).removeView(webView);
            }
            webView.destroy();
            webView = null;
        }
        progressBar = null;
        super.onDestroyView();
    }
}
