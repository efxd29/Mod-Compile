package com.efxd29.codex;

import android.app.Activity;
import android.app.DownloadManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.provider.OpenableColumns;
import android.view.Gravity;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.DownloadListener;
import android.webkit.JavascriptInterface;
import android.os.Build;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ImageView;
import android.widget.TextView;
import android.widget.Toast;

import java.net.URI;
import java.net.URISyntaxException;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

public class MainActivity extends Activity {
    private static final String PREFS = "codex";
    private static final String KEY_URL = "pairing_url";
    private static final int FILE_CHOOSER_REQUEST = 4301;
    private static final int NOTIFICATION_PERMISSION_REQUEST = 4302;
    private static final String NOTIFICATION_CHANNEL = "codex_replies";

    private SharedPreferences prefs;
    private WebView webView;
    private ValueCallback<Uri[]> filePathCallback;
    private EditText urlInput;
    private String currentPairingUrl;
    private String currentBaseUrl;
    private String currentToken;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        createReplyNotificationChannel();
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission("android.permission.POST_NOTIFICATIONS") != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"}, NOTIFICATION_PERMISSION_REQUEST);
        }
        getWindow().setStatusBarColor(Color.rgb(9, 11, 10));
        getWindow().setNavigationBarColor(Color.rgb(9, 11, 10));
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);

        String incoming = getIntent() != null ? getIntent().getDataString() : null;
        if (incoming != null && incoming.startsWith("codex://connect")) {
            String encoded = Uri.parse(incoming).getQueryParameter("url");
            if (encoded != null) incoming = encoded;
        }
        if (incoming != null && incoming.startsWith("http")) {
            connect(incoming);
        } else {
            showConnectScreen(prefs.getString(KEY_URL, ""));
        }
    }

    private int dp(float value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    private TextView text(String value, float size, int color) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        return view;
    }

    private void showConnectScreen(String previous) {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_VERTICAL);
        root.setPadding(dp(26), dp(28), dp(26), dp(28));
        root.setBackgroundColor(Color.rgb(9, 11, 10));

        ImageView mark = new ImageView(this);
        mark.setImageResource(R.drawable.ic_launcher);
        mark.setScaleType(ImageView.ScaleType.FIT_CENTER);
        LinearLayout.LayoutParams markParams = new LinearLayout.LayoutParams(dp(58), dp(58));
        markParams.bottomMargin = dp(24);
        root.addView(mark, markParams);

        TextView title = text("Connect to Codex", 27, Color.WHITE);
        title.setTypeface(null, android.graphics.Typeface.BOLD);
        root.addView(title);
        TextView subtitle = text("Masukkan pairing URL dari Termux di HP host. Codex tetap berjalan di HP host; aplikasi ini hanya remote control.", 14, Color.rgb(170, 178, 173));
        subtitle.setPadding(0, dp(10), 0, dp(24));
        root.addView(subtitle);

        urlInput = new EditText(this);
        urlInput.setSingleLine(false);
        urlInput.setMinLines(2);
        urlInput.setTextSize(14);
        urlInput.setTextColor(Color.WHITE);
        urlInput.setHintTextColor(Color.rgb(119, 128, 122));
        urlInput.setHint("http://192.168.x.x:8787/?token=...");
        urlInput.setText(previous);
        urlInput.setPadding(dp(14), dp(13), dp(14), dp(13));
        urlInput.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Color.rgb(80, 90, 83)));
        root.addView(urlInput, new LinearLayout.LayoutParams(-1, -2));

        Button connect = new Button(this);
        connect.setText("Connect to host");
        connect.setAllCaps(false);
        connect.setTextColor(Color.WHITE);
        connect.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Color.rgb(16, 163, 127)));
        LinearLayout.LayoutParams buttonParams = new LinearLayout.LayoutParams(-1, dp(52));
        buttonParams.topMargin = dp(18);
        root.addView(connect, buttonParams);
        connect.setOnClickListener(v -> connect(urlInput.getText().toString().trim()));

        Button paste = new Button(this);
        paste.setText("Paste pairing URL");
        paste.setAllCaps(false);
        paste.setTextColor(Color.rgb(220, 226, 222));
        paste.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Color.rgb(34, 40, 36)));
        LinearLayout.LayoutParams pasteParams = new LinearLayout.LayoutParams(-1, dp(48));
        pasteParams.topMargin = dp(8);
        root.addView(paste, pasteParams);
        paste.setOnClickListener(v -> {
            ClipboardManager clipboard = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            if (clipboard != null && clipboard.hasPrimaryClip()) {
                ClipData clip = clipboard.getPrimaryClip();
                if (clip != null && clip.getItemCount() > 0) {
                    CharSequence value = clip.getItemAt(0).coerceToText(this);
                    if (value != null) urlInput.setText(value.toString());
                }
            }
        });

        TextView note = text("Gunakan Wi-Fi yang sama atau jaringan privat Tailscale. Jangan membuka port host ke internet publik.", 12, Color.rgb(129, 139, 132));
        note.setPadding(0, dp(24), 0, 0);
        root.addView(note);
        setContentView(root);
    }

    private void connect(String pairingUrl) {
        try {
            URI uri = new URI(pairingUrl);
            String scheme = uri.getScheme();
            if (!"http".equalsIgnoreCase(scheme) && !"https".equalsIgnoreCase(scheme)) {
                throw new IllegalArgumentException("URL harus diawali http:// atau https://");
            }
            if (uri.getHost() == null || uri.getPort() == 0) {
                // A host may omit an explicit port only when it is a valid full URL.
                if (uri.getHost() == null) throw new IllegalArgumentException("Alamat host tidak valid.");
            }
            String token = Uri.parse(pairingUrl).getQueryParameter("token");
            if (token == null || token.trim().isEmpty()) throw new IllegalArgumentException("Pairing URL tidak memiliki token. Salin URL lengkap dari Termux.");
            String base = scheme + "://" + uri.getRawAuthority();
            currentPairingUrl = pairingUrl;
            currentBaseUrl = base;
            currentToken = token;
            prefs.edit().putString(KEY_URL, pairingUrl).apply();
            showWebView(pairingUrl);
        } catch (URISyntaxException | IllegalArgumentException e) {
            Toast.makeText(this, e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    private void showWebView(String url) {
        webView = new WebView(this);
        webView.setBackgroundColor(Color.rgb(17, 17, 17));
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(false);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setSupportMultipleWindows(false);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setUserAgentString(settings.getUserAgentString() + " CodexAndroid/1.0");

        webView.addJavascriptInterface(this, "CodexNative");
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri target = request.getUrl();
                if ("codex-download".equalsIgnoreCase(target.getScheme())) {
                    startAuthenticatedDownload(target.getQueryParameter("path"));
                    return true;
                }
                String host = target.getHost();
                Uri base = Uri.parse(currentBaseUrl);
                if (host != null && host.equalsIgnoreCase(base.getHost()) && target.getPort() == base.getPort()) return false;
                if ("http".equals(target.getScheme()) || "https".equals(target.getScheme())) {
                    startActivity(new Intent(Intent.ACTION_VIEW, target));
                    return true;
                }
                return true;
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (filePathCallback != null) filePathCallback.onReceiveValue(null);
                filePathCallback = callback;
                Intent intent;
                try {
                    intent = params.createIntent();
                    intent.setAction(Intent.ACTION_OPEN_DOCUMENT);
                    intent.addCategory(Intent.CATEGORY_OPENABLE);
                    intent.setType("*/*");
                    intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                    startActivityForResult(intent, FILE_CHOOSER_REQUEST);
                } catch (ActivityNotFoundException e) {
                    filePathCallback = null;
                    Toast.makeText(MainActivity.this, "File picker tidak tersedia.", Toast.LENGTH_LONG).show();
                    return false;
                }
                return true;
            }
        });
        webView.setDownloadListener((downloadUrl, userAgent, contentDisposition, mimetype, contentLength) -> {
            try {
                DownloadManager.Request request = new DownloadManager.Request(Uri.parse(downloadUrl));
                request.addRequestHeader("Authorization", "Bearer " + currentToken);
                request.setMimeType(mimetype);
                request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, "codex-download-" + System.currentTimeMillis());
                DownloadManager manager = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
                manager.enqueue(request);
                Toast.makeText(this, "Download dimulai.", Toast.LENGTH_SHORT).show();
            } catch (Exception e) {
                Toast.makeText(this, "Download gagal: " + e.getMessage(), Toast.LENGTH_LONG).show();
            }
        });
        setContentView(webView);
        webView.loadUrl(url);
    }

    private void createReplyNotificationChannel() {
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel channel = new NotificationChannel(NOTIFICATION_CHANNEL, "Codex replies", NotificationManager.IMPORTANCE_HIGH);
            channel.setDescription("Notifications when Codex finishes a response");
            NotificationManager manager = getSystemService(NotificationManager.class);
            if (manager != null) manager.createNotificationChannel(channel);
        }
    }

    @JavascriptInterface
    public void notifyReply(String title, String body) {
        runOnUiThread(() -> {
            if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission("android.permission.POST_NOTIFICATIONS") != android.content.pm.PackageManager.PERMISSION_GRANTED) return;
            Intent intent = new Intent(this, MainActivity.class);
            intent.setFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
            PendingIntent pending = PendingIntent.getActivity(this, 1, intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
            Notification.Builder builder = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, NOTIFICATION_CHANNEL)
                : new Notification.Builder(this);
            builder.setSmallIcon(R.drawable.ic_launcher)
                .setContentTitle(title == null || title.isEmpty() ? "Codex selesai membalas" : title)
                .setContentText(body == null || body.isEmpty() ? "Codex sudah menyelesaikan tugas." : body)
                .setStyle(new Notification.BigTextStyle().bigText(body == null ? "Codex sudah menyelesaikan tugas." : body))
                .setContentIntent(pending)
                .setAutoCancel(true);
            NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
            if (manager != null) manager.notify((int) (System.currentTimeMillis() & 0x7fffffff), builder.build());
        });
    }

    private void startAuthenticatedDownload(String relativePath) {
        if (relativePath == null || relativePath.isEmpty()) return;
        try {
            String url = currentBaseUrl + "/api/fs/download?path=" + Uri.encode(relativePath);
            DownloadManager.Request request = new DownloadManager.Request(Uri.parse(url));
            request.addRequestHeader("Authorization", "Bearer " + currentToken);
            request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            String name = relativePath.substring(relativePath.lastIndexOf('/') + 1);
            request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, name);
            DownloadManager manager = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
            manager.enqueue(request);
            Toast.makeText(this, "Download dimulai: " + name, Toast.LENGTH_SHORT).show();
        } catch (Exception e) {
            Toast.makeText(this, "Download gagal: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_CHOOSER_REQUEST) {
            if (filePathCallback == null) return;
            Uri[] results = null;
            if (resultCode == RESULT_OK && data != null) {
                if (data.getClipData() != null) {
                    int count = data.getClipData().getItemCount();
                    results = new Uri[count];
                    for (int i = 0; i < count; i++) results[i] = data.getClipData().getItemAt(i).getUri();
                } else if (data.getData() != null) {
                    results = new Uri[]{data.getData()};
                }
            }
            filePathCallback.onReceiveValue(results);
            filePathCallback = null;
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
            return;
        }
        webView = null;
        showConnectScreen(prefs.getString(KEY_URL, ""));
    }

    @Override
    protected void onDestroy() {
        if (filePathCallback != null) filePathCallback.onReceiveValue(null);
        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}