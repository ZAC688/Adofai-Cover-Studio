package com.zac688.adofaicoverstudio;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.TextView;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

public class MainActivity extends Activity {
    private final ExecutorService startup = Executors.newSingleThreadExecutor();
    private WebView webView;
    private TextView status;
    private ValueCallback<Uri[]> fileCallback;
    private volatile int runtimePort;
    private boolean closing;
    private static final int PICK_FILE = 21;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);
        getWindow().setStatusBarColor(Color.rgb(19, 19, 19));
        getWindow().setNavigationBarColor(Color.rgb(19, 19, 19));
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.rgb(19, 19, 19));
        ViewCompat.setOnApplyWindowInsetsListener(root, (view, insets) -> {
            var padding = insets.getInsets(WindowInsetsCompat.Type.systemBars()
                | WindowInsetsCompat.Type.displayCutout() | WindowInsetsCompat.Type.ime());
            view.setPadding(padding.left, padding.top, padding.right, padding.bottom);
            return insets;
        });
        webView = new WebView(this);
        webView.setBackgroundColor(Color.rgb(19, 19, 19));
        root.addView(webView, new FrameLayout.LayoutParams(-1, -1));
        status = new TextView(this);
        status.setTextColor(Color.WHITE);
        status.setTextSize(16);
        status.setGravity(android.view.Gravity.CENTER);
        status.setBackgroundColor(Color.rgb(19, 19, 19));
        status.setText("正在准备离线资源与本机作品…\n首次启动可能需要稍等片刻");
        root.addView(status, new FrameLayout.LayoutParams(-1, -1));
        setContentView(root);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setTextZoom(100);
        settings.setMediaPlaybackRequiresUserGesture(true);
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
        webView.addJavascriptInterface(new DeviceBridge(), "AndroidDevice");
        webView.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return !isLocal(request.getUrl());
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (isLocal(uri) || "blob".equals(uri.getScheme()) || "data".equals(uri.getScheme()) || "about".equals(uri.getScheme())) return null;
                return new WebResourceResponse("text/plain", "UTF-8", 403, "Offline application",
                    java.util.Collections.emptyMap(), new ByteArrayInputStream(new byte[0]));
            }
            @Override public void onPageFinished(WebView view, String url) {
                if (isLocal(Uri.parse(url))) status.setVisibility(android.view.View.GONE);
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                // Android providers often mislabel fonts and .adofai files. The
                // existing editor validates content and size after selection.
                intent.setType("*/*");
                intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, false);
                try { startActivityForResult(intent, PICK_FILE); }
                catch (android.content.ActivityNotFoundException error) {
                    fileCallback.onReceiveValue(null);
                    fileCallback = null;
                    return false;
                }
                return true;
            }
        });
        startup.execute(() -> {
            try {
                File resources = prepareResources();
                if (!Python.isStarted()) Python.start(new AndroidPlatform(getApplicationContext()));
                runtimePort = Python.getInstance().getModule("android_entry").callAttr("start",
                    resources.getAbsolutePath(), new File(getFilesDir(), "work").getAbsolutePath()).toInt();
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) webView.loadUrl("http://127.0.0.1:" + runtimePort + "/");
                });
            } catch (Exception error) {
                android.util.Log.e("AdofaiStartup", "Offline runtime startup failed", error);
                runOnUiThread(() -> status.setText("启动失败，作品数据仍保留。\n请重新打开应用。\n" + error.getClass().getSimpleName()));
            }
        });
    }

    private boolean isLocal(Uri uri) {
        return "http".equals(uri.getScheme()) && "127.0.0.1".equals(uri.getHost()) && uri.getPort() == runtimePort;
    }

    private File prepareResources() throws Exception {
        File directory = new File(getFilesDir(), "runtime-" + BuildConfig.VERSION_NAME);
        File complete = new File(directory, ".complete");
        if (complete.isFile()) return directory;
        if (!directory.isDirectory() && !directory.mkdirs()) throw new java.io.IOException("Cannot prepare resources");
        String prefix = directory.getCanonicalPath() + File.separator;
        try (InputStream asset = getAssets().open("runtime/runtime.zip"); ZipInputStream archive = new ZipInputStream(asset)) {
            ZipEntry entry;
            byte[] buffer = new byte[65536];
            while ((entry = archive.getNextEntry()) != null) {
                File target = new File(directory, entry.getName());
                if (!target.getCanonicalPath().startsWith(prefix)) throw new java.io.IOException("Invalid bundled resource path");
                if (entry.isDirectory()) {
                    if (!target.isDirectory() && !target.mkdirs()) throw new java.io.IOException("Cannot create resource directory");
                } else {
                    File parent = target.getParentFile();
                    if (!parent.isDirectory() && !parent.mkdirs()) throw new java.io.IOException("Cannot create resource directory");
                    try (FileOutputStream output = new FileOutputStream(target)) {
                        int count;
                        while ((count = archive.read(buffer)) != -1) output.write(buffer, 0, count);
                        output.getFD().sync();
                    }
                }
                archive.closeEntry();
            }
        }
        if (!new File(directory, "frontend/dist/index.html").isFile() || !new File(directory, "models/u2netp.onnx").isFile()) {
            throw new java.io.IOException("Bundled resources are incomplete");
        }
        try (FileOutputStream marker = new FileOutputStream(complete)) {
            marker.write(BuildConfig.VERSION_NAME.getBytes(StandardCharsets.UTF_8));
            marker.getFD().sync();
        }
        return directory;
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request == PICK_FILE && fileCallback != null) {
            fileCallback.onReceiveValue(result == RESULT_OK && data != null && data.getData() != null ? new Uri[]{data.getData()} : null);
            fileCallback = null;
        }
    }

    @Override public void onBackPressed() {
        if (closing) return;
        if (runtimePort == 0) { finish(); return; }
        closing = true;
        webView.evaluateJavascript("(()=>{const f=window.adofaiCloseRequest;Promise.resolve(f?f():true).then(ok=>AndroidDevice.closeResult(!!ok)).catch(()=>AndroidDevice.closeResult(false));})()", null);
    }

    public final class DeviceBridge {
        @JavascriptInterface public String version() { return BuildConfig.VERSION_NAME; }
        @JavascriptInterface public void closeResult(boolean saved) {
            runOnUiThread(() -> { closing = false; if (saved) finish(); });
        }
    }

    public int getRuntimePort() { return runtimePort; }
    public WebView getEditorWebView() { return webView; }

    @Override protected void onDestroy() {
        if (fileCallback != null) { fileCallback.onReceiveValue(null); fileCallback = null; }
        if (webView != null) {
            webView.removeJavascriptInterface("AndroidDevice");
            webView.destroy();
        }
        startup.shutdown();
        super.onDestroy();
    }
}
