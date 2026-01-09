import SwiftUI

struct ConnectionSettingsView: View {
    @Binding var serverURL: String
    @ObservedObject var webSocketManager: WebSocketManager
    @Binding var isPresented: Bool
    @State private var tempServerURL: String
    
    init(serverURL: Binding<String>, webSocketManager: WebSocketManager, isPresented: Binding<Bool>) {
        self._serverURL = serverURL
        self.webSocketManager = webSocketManager
        self._isPresented = isPresented
        self._tempServerURL = State(initialValue: serverURL.wrappedValue)
    }
    
    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("Connection")) {
                    TextField("Server URL", text: $tempServerURL)
                        .autocapitalization(.none)
                        .disableAutocorrection(true)
                        .keyboardType(.URL)
                    
                    HStack {
                        Circle()
                            .fill(webSocketManager.isConnected ? Color.green : Color.red)
                            .frame(width: 12, height: 12)
                        Text(webSocketManager.isConnected ? "Connected" : "Disconnected")
                    }
                }
                
                Section(header: Text("Actions")) {
                    Button(action: {
                        if webSocketManager.isConnected {
                            webSocketManager.disconnect()
                        } else {
                            serverURL = tempServerURL
                            webSocketManager.connect(to: serverURL)
                        }
                    }) {
                        HStack {
                            Spacer()
                            Text(webSocketManager.isConnected ? "Disconnect" : "Connect")
                            Spacer()
                        }
                    }
                    .foregroundColor(webSocketManager.isConnected ? .red : .blue)
                    
                    if !webSocketManager.messages.isEmpty {
                        Button(action: {
                            webSocketManager.messages.removeAll()
                        }) {
                            HStack {
                                Spacer()
                                Text("Clear Chat History")
                                Spacer()
                            }
                        }
                        .foregroundColor(.red)
                    }
                }
                
                Section(header: Text("About")) {
                    HStack {
                        Text("Server URL")
                        Spacer()
                        Text(serverURL)
                            .foregroundColor(.secondary)
                            .font(.caption)
                    }
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        serverURL = tempServerURL
                        isPresented = false
                    }
                }
            }
        }
    }
}
