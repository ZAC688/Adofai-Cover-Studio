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
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.FileInputStream;
import java.io.OutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import org.json.JSONObject;

public class MainActivity extends Activity {
    private final ExecutorService startup = Executors.newSingleThreadExecutor();
    private WebView webView;
    private TextView status;
    private ValueCallback<Uri[]> fileCallback;
    private volatile int runtimePort;
    private volatile String startupFailure;
    private volatile Uri lastSavedDocument;
    private boolean closing;
    private DownloadStore downloads;
    private volatile String pendingSave;
    private static final int PICK_FILE = 21;
    private static final int SAVE_FILE = 22;

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
        try {
            downloads=new DownloadStore(new File(getCacheDir(),"exports"));
            if(state!=null && state.getString("save.id")!=null) {
                try { pendingSave=downloads.restore(state.getString("save.id"),state.getString("save.name"),state.getString("save.mime"),state.getLong("save.size")).id; }
                catch(Exception invalid) { pendingSave=null; }
            }
            downloads.pruneOrphans();
        }
        catch(Exception error) { status.setText("无法准备导出缓存，请检查手机存储空间。"); return; }
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
                if(java.util.Arrays.toString(params.getAcceptTypes()).contains("image/")) {
                    intent.setType("image/*");
                    intent.putExtra(Intent.EXTRA_MIME_TYPES,new String[]{"image/png","image/jpeg"});
                } else intent.setType("*/*");
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
                if(BuildConfig.DEBUG) {
                    try(FileOutputStream ready=new FileOutputStream(new File(getCacheDir(),"runtime-ready.json"))) {
                        ready.write(new JSONObject().put("port",runtimePort).put("pid",android.os.Process.myPid()).toString().getBytes(StandardCharsets.UTF_8));
                        ready.getFD().sync();
                    }
                }
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) webView.loadUrl("http://127.0.0.1:" + runtimePort + "/");
                });
            } catch (Throwable error) {
                startupFailure=error.getClass().getSimpleName()+": "+String.valueOf(error.getMessage());
                android.util.Log.e("AdofaiStartup", "Offline runtime startup failed", error);
                runOnUiThread(() -> {status.setTextIsSelectable(true);status.setText(getString(R.string.startup_failed,startupFailure));});
            }
        });
    }

    private boolean isLocal(Uri uri) {
        return "http".equals(uri.getScheme()) && "127.0.0.1".equals(uri.getHost()) && uri.getPort() == runtimePort;
    }

    private File prepareResources() throws Exception {
        String fingerprint;
        try(InputStream info=getAssets().open("runtime/bundle-info.json");ByteArrayOutputStream bytes=new ByteArrayOutputStream()) {
            byte[] buffer=new byte[4096];int count;
            while((count=info.read(buffer))!=-1)bytes.write(buffer,0,count);
            fingerprint=new JSONObject(bytes.toString("UTF-8")).getString("resourceFingerprint");
        }
        if(!fingerprint.matches("[a-f0-9]{64}"))throw new java.io.IOException("Invalid resource fingerprint");
        File directory = new File(getFilesDir(), "runtime-" + fingerprint);
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
            marker.write(fingerprint.getBytes(StandardCharsets.UTF_8));
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
        if(request==SAVE_FILE && pendingSave!=null) {
            String id=pendingSave;
            pendingSave=null;
            if(result!=RESULT_OK) { downloadResult(id,"cancelled",""); return; }
            Uri destination=data==null?null:data.getData();
            if(destination==null) { downloadResult(id,"error","系统未返回文件位置，请重试保存"); return; }
            startup.execute(()->{
                try {
                    DownloadStore.Transfer transfer=downloads.get(id);
                    try(InputStream input=new FileInputStream(transfer.file);
                        OutputStream output=getContentResolver().openOutputStream(destination,"wt")) {
                        if(output==null) throw new java.io.IOException("无法写入所选位置");
                        byte[] buffer=new byte[65536];int count;
                        while((count=input.read(buffer))!=-1) output.write(buffer,0,count);
                        output.flush();
                    }
                    lastSavedDocument=destination;
                    downloadResult(id,"saved","");
                } catch(Exception error) {
                    downloadResult(id,"error","文件保存失败，请检查所选位置或手机存储空间，再重新导出");
                }
            });
        }
    }

    private void downloadResult(String id,String state,String error) {
        try { downloads.discard(id); } catch(Exception ignored) { /* Private cache can be reclaimed later. */ }
        runOnUiThread(()->{
            if(!isDestroyed() && webView!=null) webView.evaluateJavascript(
                "window.adofaiDownloadResult&&window.adofaiDownloadResult("+JSONObject.quote(id)+","+JSONObject.quote(state)+","+JSONObject.quote(error)+")",null);
        });
    }

    @Override public void onBackPressed() {
        if (closing) return;
        if (runtimePort == 0) { finish(); return; }
        closing = true;
        webView.evaluateJavascript("(()=>{const f=window.adofaiBackRequest||window.adofaiCloseRequest;Promise.resolve(f?f():true).then(ok=>AndroidDevice.closeResult(!!ok)).catch(()=>AndroidDevice.closeResult(false));})()", null);
    }

    public final class DeviceBridge {
        @JavascriptInterface public String version() { return BuildConfig.VERSION_NAME; }
        @JavascriptInterface public void closeResult(boolean saved) {
            runOnUiThread(() -> { closing = false; if (saved) finish(); });
        }
        @JavascriptInterface public String beginDownload(String name,String mime,long size) {
            try {
                String id=downloads.begin(name,mime,size).id;
                return new JSONObject().put("id",id).toString();
            } catch(Exception error) { return failure(error); }
        }
        @JavascriptInterface public String appendDownload(String id,long offset,String encoded) {
            try { return new JSONObject().put("written",downloads.append(id,offset,encoded)).toString(); }
            catch(Exception error) { return failure(error); }
        }
        @JavascriptInterface public String finishDownload(String id) {
            try {
                if(pendingSave!=null) throw new IllegalStateException("请先完成当前文件的保存");
                DownloadStore.Transfer transfer=downloads.complete(id);
                pendingSave=id;
                runOnUiThread(()->{
                    Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT);
                    intent.addCategory(Intent.CATEGORY_OPENABLE);
                    intent.setType(transfer.mime);
                    intent.putExtra(Intent.EXTRA_TITLE,transfer.name);
                    intent.putExtra(android.provider.DocumentsContract.EXTRA_INITIAL_URI,
                        android.provider.DocumentsContract.buildDocumentUri("com.android.externalstorage.documents","primary:Download"));
                    try { startActivityForResult(intent,SAVE_FILE); }
                    catch(android.content.ActivityNotFoundException error) {
                        pendingSave=null;downloadResult(id,"error","无法打开系统保存界面，请确认系统文件管理器可用");
                    }
                });
                return new JSONObject().put("queued",true).toString();
            } catch(Exception error) { return failure(error); }
        }
        @JavascriptInterface public void cancelDownload(String id) {
            if(!id.equals(pendingSave)) { try {downloads.discard(id);} catch(Exception ignored) {} }
        }
        private String failure(Exception error) {
            try {return new JSONObject().put("error",error.getMessage()==null?"文件处理失败，请重试":error.getMessage()).toString();}
            catch(Exception impossible) {return "{\"error\":\"文件处理失败，请重试\"}";}
        }
    }

    public int getRuntimePort() { return runtimePort; }
    public String getStartupFailureForTests() { return BuildConfig.DEBUG?startupFailure:null; }
    public Uri getLastSavedDocumentForTests() { return BuildConfig.DEBUG?lastSavedDocument:null; }
    public WebView getEditorWebView() { return webView; }

    @Override protected void onPause() {
        if(webView!=null && runtimePort!=0) webView.evaluateJavascript("window.adofaiCloseRequest&&window.adofaiCloseRequest()",null);
        super.onPause();
    }

    @Override protected void onSaveInstanceState(Bundle state) {
        if(pendingSave!=null && downloads!=null) {
            try {
                DownloadStore.Transfer transfer=downloads.get(pendingSave);
                state.putString("save.id",transfer.id);state.putString("save.name",transfer.name);
                state.putString("save.mime",transfer.mime);state.putLong("save.size",transfer.expected);
            } catch(Exception ignored) {}
        }
        super.onSaveInstanceState(state);
    }

    @Override protected void onDestroy() {
        if (fileCallback != null) { fileCallback.onReceiveValue(null); fileCallback = null; }
        if (webView != null) {
            webView.removeJavascriptInterface("AndroidDevice");
            webView.destroy();
        }
        if(downloads!=null) {
            try {
                if(pendingSave!=null&&!isFinishing())downloads.detach(pendingSave);
                downloads.close();
            } catch(Exception ignored) {}
        }
        startup.shutdown();
        super.onDestroy();
    }
}
