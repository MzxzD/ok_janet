#!/bin/bash
# Script to help create an Xcode project for Janet Mesh iOS Client

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_NAME="JanetMeshClient"
PROJECT_DIR="$SCRIPT_DIR/$PROJECT_NAME"

echo "📱 Creating Xcode project for Janet Mesh iOS Client"
echo ""

# Check if Xcode is installed
if ! command -v xcodebuild &> /dev/null; then
    echo "❌ Error: Xcode command-line tools not found"
    echo "   Please install Xcode from the App Store and run: xcode-select --install"
    exit 1
fi

# Check if project already exists
if [ -d "$PROJECT_DIR.xcodeproj" ] || [ -d "$PROJECT_DIR.xcworkspace" ]; then
    echo "⚠️  Project already exists at: $PROJECT_DIR"
    read -p "   Do you want to remove it and create a new one? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$PROJECT_DIR.xcodeproj" "$PROJECT_DIR.xcworkspace" "$PROJECT_DIR"
    else
        echo "   Exiting. Please remove the existing project manually if needed."
        exit 0
    fi
fi

echo "📝 Creating project structure..."
mkdir -p "$PROJECT_DIR"

# Create Info.plist
cat > "$PROJECT_DIR/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>$(DEVELOPMENT_LANGUAGE)</string>
    <key>CFBundleDisplayName</key>
    <string>Janet Mesh</string>
    <key>CFBundleExecutable</key>
    <string>$(EXECUTABLE_NAME)</string>
    <key>CFBundleIdentifier</key>
    <string>$(PRODUCT_BUNDLE_IDENTIFIER)</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>$(PRODUCT_NAME)</string>
    <key>CFBundlePackageType</key>
    <string>$(PRODUCT_BUNDLE_PACKAGE_TYPE)</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSRequiresIPhoneOS</key>
    <true/>
    <key>UIApplicationSceneManifest</key>
    <dict>
        <key>UIApplicationSupportsMultipleScenes</key>
        <true/>
    </dict>
    <key>UIApplicationSupportsIndirectInputEvents</key>
    <true/>
    <key>UILaunchScreen</key>
    <dict/>
    <key>UIRequiredDeviceCapabilities</key>
    <array>
        <string>armv7</string>
    </array>
    <key>UISupportedInterfaceOrientations</key>
    <array>
        <string>UIInterfaceOrientationPortrait</string>
        <string>UIInterfaceOrientationLandscapeLeft</string>
        <string>UIInterfaceOrientationLandscapeRight</string>
    </array>
    <key>UISupportedInterfaceOrientations~ipad</key>
    <array>
        <string>UIInterfaceOrientationPortrait</string>
        <string>UIInterfaceOrientationPortraitUpsideDown</string>
        <string>UIInterfaceOrientationLandscapeLeft</string>
        <string>UIInterfaceOrientationLandscapeRight</string>
    </array>
    <key>NSAppTransportSecurity</key>
    <dict>
        <key>NSAllowsLocalNetworking</key>
        <true/>
        <key>NSAllowsArbitraryLoads</key>
        <true/>
    </dict>
    <key>NSMicrophoneUsageDescription</key>
    <string>Janet needs microphone access for voice input</string>
</dict>
</plist>
EOF

echo "✅ Created Info.plist"

# List of Swift files to include
SWIFT_FILES=(
    "JanetMeshClientApp.swift"
    "ContentView.swift"
    "ChatView.swift"
    "Message.swift"
    "WebSocketManager.swift"
    "ConnectionSettingsView.swift"
    "ServiceDiscovery.swift"
    "AudioCapture.swift"
)

echo ""
echo "📋 Swift files to add to project:"
for file in "${SWIFT_FILES[@]}"; do
    if [ -f "$SCRIPT_DIR/$file" ]; then
        echo "   ✓ $file"
    else
        echo "   ✗ $file (missing!)"
    fi
done

echo ""
echo "⚠️  Manual Steps Required:"
echo ""
echo "Since Xcode project files are complex binary/XML structures,"
echo "you need to create the project manually in Xcode:"
echo ""
echo "1. Open Xcode"
echo "2. Choose 'Create a new Xcode project'"
echo "3. Select 'iOS' → 'App'"
echo "4. Fill in:"
echo "   - Product Name: $PROJECT_NAME"
echo "   - Interface: SwiftUI"
echo "   - Language: Swift"
echo "   - Storage: None"
echo "5. Save the project in: $SCRIPT_DIR"
echo "6. Delete the default ContentView.swift that Xcode creates"
echo "7. Add all Swift files from $SCRIPT_DIR to the project:"
for file in "${SWIFT_FILES[@]}"; do
    echo "   - $file"
done
echo "8. Make sure 'JanetMeshClientApp.swift' is set as the main entry point"
echo "9. Build and run (Cmd+R)"
echo ""
echo "Alternatively, if you have 'xcodegen' installed, I can create a project.yml"
echo "file that xcodegen can use to generate the project automatically."
