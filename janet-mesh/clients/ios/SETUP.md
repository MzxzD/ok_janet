# iOS Client Setup Guide

## Problem
There is no Xcode project file (`.xcodeproj`), so the app cannot be built or run.

## Solution Options

### ✅ Option 1: Use xcodegen (Easiest - Recommended)

xcodegen can automatically generate an Xcode project from the `project.yml` file.

**Steps:**

1. Install xcodegen:
   ```bash
   brew install xcodegen
   ```

2. Generate the project:
   ```bash
   cd /Users/mzxzd/Documents/Development/ok\ JANET/janet-mesh/clients/ios
   xcodegen generate
   ```

3. Open in Xcode:
   ```bash
   open JanetMeshClient.xcodeproj
   ```

4. Build and run (Cmd+R)

### Option 2: Create Project Manually in Xcode

1. Open Xcode
2. File → New → Project
3. Choose "iOS" → "App"
4. Configure:
   - Product Name: `JanetMeshClient`
   - Team: (your team)
   - Organization Identifier: `com.janetmesh`
   - Interface: **SwiftUI**
   - Language: **Swift**
   - Storage: None
5. Save location: `/Users/mzxzd/Documents/Development/ok JANET/janet-mesh/clients/ios/`
6. Delete the default `ContentView.swift` that Xcode creates
7. Add all Swift files to the project (drag and drop or Add Files)
8. Make sure `JanetMeshClientApp.swift` is the main entry point
9. Build and run

## Files to Include

All these Swift files should be in the Xcode project:

- ✅ `JanetMeshClientApp.swift` - Main app entry point
- ✅ `ContentView.swift` - Main view with navigation
- ✅ `ChatView.swift` - Chat interface
- ✅ `Message.swift` - Message model
- ✅ `WebSocketManager.swift` - WebSocket connection manager
- ✅ `ConnectionSettingsView.swift` - Settings view
- ✅ `ServiceDiscovery.swift` - Bonjour/mDNS discovery
- ✅ `AudioCapture.swift` - Audio recording (optional)

## Verification

After setup, you should be able to:
1. Build the project without errors (Cmd+B)
2. Run on simulator or device (Cmd+R)
3. See the chat interface with text input at the bottom
4. See connection status in the navigation bar

## Troubleshooting

**"No such module" errors:**
- Make sure all Swift files are added to the target
- Check that files are in the project navigator

**Build errors:**
- Clean build folder (Shift+Cmd+K)
- Delete derived data
- Rebuild (Cmd+B)

**Chat not showing:**
- Check Xcode console for debug messages (📱 and 💬)
- Verify WebSocket connection status
- Check that ChatView is being rendered
