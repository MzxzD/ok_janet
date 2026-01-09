# Janet Mesh iOS Client

## Quick Setup (Recommended)

### Option 1: Using xcodegen (Automatic)

1. **Install xcodegen** (if not already installed):
   ```bash
   brew install xcodegen
   ```

2. **Generate the Xcode project**:
   ```bash
   cd clients/ios
   xcodegen generate
   ```

3. **Open the project**:
   ```bash
   open JanetMeshClient.xcodeproj
   ```

4. **Build and Run**:
   - Select a simulator or device
   - Press Cmd+R to build and run

### Option 2: Manual Xcode Setup

1. **Open Xcode** and create a new project:
   - File → New → Project
   - Choose "iOS" → "App"
   - Product Name: `JanetMeshClient`
   - Interface: **SwiftUI**
   - Language: **Swift**
   - Save in: `clients/ios/`

2. **Delete the default files** Xcode creates:
   - Delete `ContentView.swift` (we have our own)
   - Keep `JanetMeshClientApp.swift` but replace its contents with our version

3. **Add all Swift files** to the project:
   - Right-click the project in navigator → "Add Files to JanetMeshClient..."
   - Select all these files:
     - `JanetMeshClientApp.swift` (main entry point - replace default)
     - `ContentView.swift`
     - `ChatView.swift`
     - `Message.swift`
     - `WebSocketManager.swift`
     - `ConnectionSettingsView.swift`
     - `ServiceDiscovery.swift`
     - `AudioCapture.swift`
   - Make sure "Copy items if needed" is **unchecked** (files are already in place)
   - Make sure "Add to targets: JanetMeshClient" is **checked**

4. **Configure Info.plist**:
   - The `Info.plist` file is already created with the correct settings
   - If Xcode created its own, replace it with ours or add these keys:
     - `NSAppTransportSecurity` → `NSAllowsLocalNetworking: true`
     - `NSMicrophoneUsageDescription: "Janet needs microphone access for voice input"`

5. **Build and Run**:
   - Connect an iOS device or use the simulator
   - Build the project (Cmd+B)
   - Run (Cmd+R)

## Features

- **Chat Interface**: Modern chat UI with message bubbles
- **WebSocket Connection**: Connects to Janet mesh server
- **Connection Settings**: Configure server URL
- **Real-time Messaging**: Send and receive messages with Janet

## Server Connection

Default server URL: `ws://localhost:8765/ws`

For physical devices, use your Mac's IP address:
`ws://192.168.x.x:8765/ws`

## Troubleshooting

If the chat interface doesn't appear:
1. Check that all files are added to the Xcode project
2. Verify there are no build errors
3. Check the console for runtime errors
4. Ensure the app has network permissions
