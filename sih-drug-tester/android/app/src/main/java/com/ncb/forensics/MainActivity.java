package com.ncb.forensics;

import android.Manifest;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.webkit.GeolocationPermissions;
import android.webkit.PermissionRequest;
import androidx.annotation.NonNull;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import com.getcapacitor.BridgeActivity;
import com.getcapacitor.BridgeWebChromeClient;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public class MainActivity extends BridgeActivity {
    private static final int PERMISSION_REQUEST_CODE = 1001;

    private PermissionRequest pendingPermissionRequest = null;
    private GeolocationPermissions.Callback pendingGeoCallback = null;
    private String pendingGeoOrigin = null;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Proactively request runtime permissions on app launch
        requestRequiredPermissions();

        // Configure BridgeWebChromeClient to safely grant camera, mic, and geolocation
        if (this.bridge != null && this.bridge.getWebView() != null) {
            this.bridge.getWebView().setWebChromeClient(new BridgeWebChromeClient(this.bridge) {
                @Override
                public void onPermissionRequest(final PermissionRequest request) {
                    runOnUiThread(() -> {
                        boolean hasCamera = ContextCompat.checkSelfPermission(
                            MainActivity.this, Manifest.permission.CAMERA
                        ) == PackageManager.PERMISSION_GRANTED;

                        boolean hasAudio = ContextCompat.checkSelfPermission(
                            MainActivity.this, Manifest.permission.RECORD_AUDIO
                        ) == PackageManager.PERMISSION_GRANTED;

                        List<String> resources = Arrays.asList(request.getResources());
                        boolean needsCamera = resources.contains(PermissionRequest.RESOURCE_VIDEO_CAPTURE);
                        boolean needsAudio = resources.contains(PermissionRequest.RESOURCE_AUDIO_CAPTURE);

                        if ((!needsCamera || hasCamera) && (!needsAudio || hasAudio)) {
                            request.grant(request.getResources());
                        } else {
                            pendingPermissionRequest = request;
                            requestRequiredPermissions();
                        }
                    });
                }

                @Override
                public void onGeolocationPermissionsShowPrompt(final String origin, final GeolocationPermissions.Callback callback) {
                    runOnUiThread(() -> {
                        boolean hasFine = ContextCompat.checkSelfPermission(
                            MainActivity.this, Manifest.permission.ACCESS_FINE_LOCATION
                        ) == PackageManager.PERMISSION_GRANTED;

                        boolean hasCoarse = ContextCompat.checkSelfPermission(
                            MainActivity.this, Manifest.permission.ACCESS_COARSE_LOCATION
                        ) == PackageManager.PERMISSION_GRANTED;

                        if (hasFine || hasCoarse) {
                            callback.invoke(origin, true, false);
                        } else {
                            pendingGeoCallback = callback;
                            pendingGeoOrigin = origin;
                            requestRequiredPermissions();
                        }
                    });
                }
            });
        }
    }

    private void requestRequiredPermissions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            String[] requiredPermissions = new String[] {
                Manifest.permission.CAMERA,
                Manifest.permission.RECORD_AUDIO,
                Manifest.permission.MODIFY_AUDIO_SETTINGS,
                Manifest.permission.ACCESS_FINE_LOCATION,
                Manifest.permission.ACCESS_COARSE_LOCATION
            };

            List<String> toRequest = new ArrayList<>();
            for (String perm : requiredPermissions) {
                if (ContextCompat.checkSelfPermission(this, perm) != PackageManager.PERMISSION_GRANTED) {
                    toRequest.add(perm);
                }
            }

            if (!toRequest.isEmpty()) {
                ActivityCompat.requestPermissions(
                    this,
                    toRequest.toArray(new String[0]),
                    PERMISSION_REQUEST_CODE
                );
            }
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == PERMISSION_REQUEST_CODE) {
            boolean hasCamera = ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED;
            boolean hasAudio = ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED;
            boolean hasGeo = ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
                || ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;

            if (pendingPermissionRequest != null) {
                List<String> resources = Arrays.asList(pendingPermissionRequest.getResources());
                boolean needsCamera = resources.contains(PermissionRequest.RESOURCE_VIDEO_CAPTURE);
                boolean needsAudio = resources.contains(PermissionRequest.RESOURCE_AUDIO_CAPTURE);

                if ((!needsCamera || hasCamera) && (!needsAudio || hasAudio)) {
                    pendingPermissionRequest.grant(pendingPermissionRequest.getResources());
                } else {
                    pendingPermissionRequest.deny();
                }
                pendingPermissionRequest = null;
            }

            if (pendingGeoCallback != null) {
                pendingGeoCallback.invoke(pendingGeoOrigin, hasGeo, false);
                pendingGeoCallback = null;
                pendingGeoOrigin = null;
            }

            if (this.bridge != null && this.bridge.getWebView() != null) {
                this.bridge.getWebView().post(() -> {
                    this.bridge.getWebView().evaluateJavascript(
                        "if (window.onNativePermissionsGranted) { window.onNativePermissionsGranted(); }",
                        null
                    );
                });
            }
        }
    }
}