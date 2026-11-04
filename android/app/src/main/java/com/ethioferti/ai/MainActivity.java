package com.ethioferti.ai;

import android.app.Activity;
import android.os.Bundle;
import android.os.Handler;
import android.webkit.WebChromeClient;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.PermissionRequest;
import android.content.pm.PackageManager;
import android.Manifest;
import android.view.ViewGroup;
import android.webkit.WebSettings;
import android.widget.Toast;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import java.io.File;
import java.io.InputStream;
import java.io.FileOutputStream;
import java.io.IOException;

public class MainActivity extends Activity {
    private WebView webView;
    private PermissionRequest pendingPermission;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        webView = new WebView(this);
        webView.setLayoutParams(new ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        ));
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setMediaPlaybackRequiresUserGesture(false);

        webView.setWebViewClient(new WebViewClient());

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(PermissionRequest request) {
                runOnUiThread(() -> {
                    boolean needsCamera = false;
                    for (String resource : request.getResources()) {
                        if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(resource)) {
                            needsCamera = true;
                        }
                    }

                    if (!needsCamera ||
                        checkSelfPermission(Manifest.permission.CAMERA)
                            == PackageManager.PERMISSION_GRANTED) {
                        request.grant(request.getResources());
                    } else {
                        pendingPermission = request;
                        requestPermissions(
                            new String[]{Manifest.permission.CAMERA}, 100
                        );
                    }
                });
            }
        });

        try {
            File runtime = new File(getFilesDir(), "ethioferti_runtime");
            if (!runtime.exists()) {
                copyAssets("runtime", runtime);
            }

            // Refresh application code and web interface on every launch.
            // The persistent runtime/data directory is deliberately preserved.
            copyAssets("runtime/app", new File(runtime, "app"));

            if (!Python.isStarted()) {
                Python.start(new AndroidPlatform(this));
            }

            Python.getInstance()
                .getModule("launcher")
                .callAttr("start_server", runtime.getAbsolutePath());

            new Handler().postDelayed(
                () -> webView.loadUrl("http://127.0.0.1:8000/"),
                1500
            );

        } catch (Exception e) {
            Toast.makeText(this, "App startup failed: " + e.getMessage(),
                Toast.LENGTH_LONG).show();
        }
    }

    private void copyAssets(String assetPath, File destination)
            throws IOException {
        String[] children = getAssets().list(assetPath);

        if (children == null || children.length == 0) {
            File parent = destination.getParentFile();
            if (parent != null) parent.mkdirs();

            try (InputStream input = getAssets().open(assetPath);
                 FileOutputStream output = new FileOutputStream(destination)) {
                byte[] buffer = new byte[8192];
                int count;
                while ((count = input.read(buffer)) != -1) {
                    output.write(buffer, 0, count);
                }
            }
            return;
        }

        if (!destination.exists()) destination.mkdirs();

        for (String child : children) {
            copyAssets(assetPath + "/" + child,
                new File(destination, child));
        }
    }

    @Override
    public void onRequestPermissionsResult(
        int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);

        if (requestCode == 100 && pendingPermission != null) {
            if (grantResults.length > 0 &&
                grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                pendingPermission.grant(pendingPermission.getResources());
            } else {
                pendingPermission.deny();
            }
            pendingPermission = null;
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
