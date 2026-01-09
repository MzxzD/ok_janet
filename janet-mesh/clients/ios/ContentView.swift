import SwiftUI

struct ContentView: View {
    @StateObject private var serviceDiscovery = ServiceDiscovery()
    @StateObject private var webSocketManager = WebSocketManager()
    @StateObject private var audioCapture = AudioCapture()
    @State private var serverURL = "ws://localhost:8765/ws"
    @State private var showConnectionSettings = false
    
    var body: some View {
        NavigationView {
            ChatView(webSocketManager: webSocketManager)
                .navigationTitle("Janet")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .navigationBarLeading) {
                        HStack(spacing: 6) {
                            Circle()
                                .fill(webSocketManager.isConnected ? Color.green : Color.red)
                                .frame(width: 8, height: 8)
                            Text(webSocketManager.isConnected ? "Connected" : "Disconnected")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button(action: {
                            showConnectionSettings = true
                        }) {
                            Image(systemName: "gear")
                        }
                    }
                }
                .sheet(isPresented: $showConnectionSettings) {
                    ConnectionSettingsView(
                        serverURL: $serverURL,
                        webSocketManager: webSocketManager,
                        isPresented: $showConnectionSettings
                    )
                }
                .onAppear {
                    print("📱 ContentView appeared")
                    print("📱 ChatView should be visible")
                    
                    // Start service discovery
                    if #available(iOS 14.0, *) {
                        serviceDiscovery.startDiscovery()
                    }
                    
                    // Auto-connect on appear if not connected
                    if !webSocketManager.isConnected {
                        // Try to use discovered service first, otherwise use default URL
                        if #available(iOS 14.0, *), let firstService = serviceDiscovery.discoveredServices.first,
                           let serviceURL = serviceDiscovery.getServiceURL(from: firstService) {
                            print("📱 Found service, connecting to: \(serviceURL)")
                            serverURL = serviceURL
                            webSocketManager.connect(to: serviceURL)
                        } else {
                            print("📱 No service discovered, attempting to connect to: \(serverURL)")
                            // If localhost, warn user
                            if serverURL.contains("localhost") {
                                print("⚠️ WARNING: localhost won't work on physical device. Use Settings to enter server IP (e.g., ws://192.168.0.52:8765)")
                            }
                            webSocketManager.connect(to: serverURL)
                        }
                    }
                }
                .onChange(of: serviceDiscovery.discoveredServices) { services in
                    // Auto-connect when service is discovered
                    if !webSocketManager.isConnected, let firstService = services.first,
                       #available(iOS 14.0, *) {
                        print("📱 Service discovered, resolving...")
                        serviceDiscovery.getServiceURL(from: firstService) { serviceURL in
                            if let url = serviceURL {
                                print("📱 Service resolved, connecting to: \(url)")
                                DispatchQueue.main.async {
                                    serverURL = url
                                    webSocketManager.connect(to: url)
                                }
                            } else {
                                print("⚠️ Could not resolve service URL")
                            }
                        }
                    }
                }
        }
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}
