import SwiftUI

struct ContentView: View {
    @StateObject private var serviceDiscovery = ServiceDiscovery()
    @StateObject private var webSocketManager = WebSocketManager()
    @StateObject private var audioCapture = AudioCapture()
    @State private var serverURL = "ws://localhost:8080/ws"
    @State private var isConnected = false
    @State private var inputText = ""
    @State private var responseText = ""
    
    var body: some View {
        VStack(spacing: 20) {
            Text("Janet Mesh Client")
                .font(.largeTitle)
                .padding()
            
            // Connection status
            HStack {
                Circle()
                    .fill(isConnected ? Color.green : Color.red)
                    .frame(width: 12, height: 12)
                Text(isConnected ? "Connected" : "Disconnected")
            }
            
            // Server URL input
            TextField("Server URL", text: $serverURL)
                .textFieldStyle(RoundedBorderTextFieldStyle())
                .padding(.horizontal)
            
            // Connect button
            Button(action: {
                if isConnected {
                    webSocketManager.disconnect()
                    isConnected = false
                } else {
                    webSocketManager.connect(to: serverURL)
                    isConnected = true
                }
            }) {
                Text(isConnected ? "Disconnect" : "Connect")
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(isConnected ? Color.red : Color.blue)
                    .foregroundColor(.white)
                    .cornerRadius(8)
            }
            .padding(.horizontal)
            
            // Text input
            VStack(alignment: .leading) {
                Text("Text Input")
                    .font(.headline)
                TextField("Type your message...", text: $inputText)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                
                Button("Send") {
                    webSocketManager.sendText(inputText)
                    inputText = ""
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color.green)
                .foregroundColor(.white)
                .cornerRadius(8)
            }
            .padding(.horizontal)
            
            // Audio recording
            VStack {
                Text("Audio Input")
                    .font(.headline)
                
                HStack {
                    Button(action: {
                        if audioCapture.isRecording {
                            audioCapture.stopRecording()
                        } else {
                            try? audioCapture.startRecording()
                        }
                    }) {
                        Image(systemName: audioCapture.isRecording ? "stop.circle.fill" : "mic.circle.fill")
                            .font(.system(size: 50))
                            .foregroundColor(audioCapture.isRecording ? .red : .blue)
                    }
                    
                    if audioCapture.isRecording {
                        ProgressView(value: audioCapture.audioLevel)
                            .frame(width: 100)
                    }
                }
            }
            .padding()
            
            // Response
            VStack(alignment: .leading) {
                Text("Response")
                    .font(.headline)
                ScrollView {
                    Text(responseText.isEmpty ? "No response yet" : responseText)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding()
                }
                .frame(height: 200)
                .background(Color.gray.opacity(0.1))
                .cornerRadius(8)
            }
            .padding(.horizontal)
            
            Spacer()
        }
        .onChange(of: webSocketManager.lastMessage) { message in
            // Parse response
            if let data = message.data(using: .utf8),
               let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let type = json["type"] as? String,
               type == "response",
               let text = json["text"] as? String {
                responseText = text
            }
        }
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}
