import Foundation
import Combine

/// Manages WebSocket connection to Janet mesh server
class WebSocketManager: ObservableObject {
    @Published var isConnected = false
    @Published var lastMessage: String = ""
    @Published var lastAudioData: Data?
    @Published var messages: [Message] = []
    @Published var isWaitingForResponse = false
    
    private var webSocketTask: URLSessionWebSocketTask?
    private var clientId: String?
    
    func connect(to urlString: String) {
        // Disconnect any existing connection first
        disconnect()
        
        guard let url = URL(string: urlString) else {
            print("❌ Invalid URL: \(urlString)")
            return
        }
        
        print("🔌 Connecting to: \(urlString)")
        
        // Create URLSession with proper configuration
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 10
        config.timeoutIntervalForResource = 30
        
        let session = URLSession(configuration: config)
        webSocketTask = session.webSocketTask(with: url)
        
        // Set up connection state monitoring
        webSocketTask?.resume()
        
        // Start receiving messages (this also helps establish the connection)
        receiveMessage()
        
        // Also set up a ping to keep connection alive and verify it's working
        sendPing()
    }
    
    private func sendPing() {
        webSocketTask?.sendPing { [weak self] error in
            if let error = error {
                print("❌ WebSocket ping failed: \(error)")
                DispatchQueue.main.async {
                    self?.isConnected = false
                }
            } else {
                // Connection is alive, schedule next ping
                DispatchQueue.main.asyncAfter(deadline: .now() + 30) {
                    self?.sendPing()
                }
            }
        }
    }
    
    func disconnect() {
        webSocketTask?.cancel(with: .goingAway, reason: nil)
        webSocketTask = nil
        DispatchQueue.main.async {
            self.isConnected = false
            self.isWaitingForResponse = false
        }
    }
    
    func sendText(_ text: String) {
        guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        
        // Add user message to conversation
        let userMessage = Message(text: text, isFromUser: true)
        DispatchQueue.main.async {
            self.messages.append(userMessage)
            self.isWaitingForResponse = true
        }
        
        // Create JSON message properly
        let messageDict: [String: Any] = [
            "type": "text_input",
            "text": text
        ]
        
        guard let jsonData = try? JSONSerialization.data(withJSONObject: messageDict),
              let messageJSON = String(data: jsonData, encoding: .utf8) else {
            print("Error encoding message to JSON")
            DispatchQueue.main.async {
                self.isWaitingForResponse = false
            }
            return
        }
        
        let wsMessage = URLSessionWebSocketTask.Message.string(messageJSON)
        webSocketTask?.send(wsMessage) { error in
            if let error = error {
                print("Error sending message: \(error)")
                DispatchQueue.main.async {
                    self.isWaitingForResponse = false
                }
            }
        }
    }
    
    func sendAudio(_ audioData: Data) {
        let base64 = audioData.base64EncodedString()
        let messageDict: [String: Any] = [
            "type": "audio_chunk",
            "audio": base64
        ]
        
        guard let jsonData = try? JSONSerialization.data(withJSONObject: messageDict),
              let messageJSON = String(data: jsonData, encoding: .utf8) else {
            print("Error encoding audio message to JSON")
            return
        }
        
        let wsMessage = URLSessionWebSocketTask.Message.string(messageJSON)
        webSocketTask?.send(wsMessage) { error in
            if let error = error {
                print("Error sending audio: \(error)")
            }
        }
    }
    
    private func receiveMessage() {
        webSocketTask?.receive { [weak self] result in
            guard let self = self else { return }
            
            switch result {
            case .success(let message):
                switch message {
                case .string(let text):
                    print("📨 Received message: \(text.prefix(100))")
                    DispatchQueue.main.async {
                        self.lastMessage = text
                        self.handleMessage(text)
                    }
                case .data(let data):
                    print("📨 Received binary data: \(data.count) bytes")
                    DispatchQueue.main.async {
                        self.lastAudioData = data
                    }
                @unknown default:
                    break
                }
                // Continue receiving messages
                self.receiveMessage()
                
            case .failure(let error):
                print("❌ WebSocket receive error: \(error.localizedDescription)")
                DispatchQueue.main.async {
                    self.isConnected = false
                    self.isWaitingForResponse = false
                }
                // Don't try to receive again on failure - connection is likely closed
            }
        }
    }
    
    private func handleMessage(_ text: String) {
        guard let data = text.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = json["type"] as? String else {
            return
        }
        
        switch type {
        case "connected":
            if let clientId = json["client_id"] as? String {
                self.clientId = clientId
            }
            DispatchQueue.main.async {
                self.isConnected = true
            }
        case "response":
            DispatchQueue.main.async {
                self.isWaitingForResponse = false
                
                // Add Janet's response to conversation
                if let responseText = json["text"] as? String, !responseText.isEmpty {
                    let janetMessage = Message(text: responseText, isFromUser: false)
                    self.messages.append(janetMessage)
                }
                
                // Handle audio if present
                if let audioBase64 = json["audio"] as? String,
                   let audioData = Data(base64Encoded: audioBase64) {
                    self.lastAudioData = audioData
                }
            }
        case "error":
            DispatchQueue.main.async {
                self.isWaitingForResponse = false
                if let errorMessage = json["message"] as? String {
                    let errorMsg = Message(text: "Error: \(errorMessage)", isFromUser: false)
                    self.messages.append(errorMsg)
                    print("Error from server: \(errorMessage)")
                }
            }
        default:
            break
        }
    }
}
