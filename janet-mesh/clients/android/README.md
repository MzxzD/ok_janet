# Android Client

Android client for Janet Mesh Network.

## Implementation Notes

The Android client should:
- Use WebSocket client (OkHttp WebSocket)
- Capture audio using AudioRecord
- Play audio responses
- Use NSD (Network Service Discovery) for mDNS/Bonjour

## Dependencies

```gradle
dependencies {
    implementation 'com.squareup.okhttp3:okhttp:4.12.0'
    implementation 'androidx.compose.ui:ui:1.5.0'
    // Add other dependencies as needed
}
```

## TODO

- Implement WebSocket client
- Implement audio capture
- Implement audio playback
- Implement service discovery via NSD
