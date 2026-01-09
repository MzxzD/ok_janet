import Foundation
import Combine

/// Manages WebSocket connection to Janet mesh server
class WebSocketManager: ObservableObject {
    @Published var isConnected = false
    @Published var lastMessage: String = ""
    @Published var lastAudioData: Data?
    
    private var webSocketTask: URLSessionWebSocketTask?
    private var clientId: String?
    
    func connect(to urlString: String) {
        guard let url = URL(string: urlString) else {
            print("Invalid URL: \(urlString)")
            return
        }
        
        let session = URLSession(configuration: .default)
        webSocketTask = session.webSocketTask(with: url)
        webSocketTask?.resume()
        
        receiveMessage()
        isConnected = true
    }
    
    func disconnect() {
        webSocketTask?.cancel(with: .goingAway, reason: nil)
        webSocketTask = nil
        isConnected = false
    }
    
    func sendText(_ text: String) {
        let message = """
        {
            "type": "text_input",
            "text": "\(text)"
        }
        """
        
        guard let data = message.data(using: .utf8) else { return }
        let message = URLSessionWebSocketTask.Message.string(message)
        webSocketTask?.send(message) { error in
            if let error = error {
                print("Error sending message: \(error)")
            }
        }
    }
    
    func sendAudio(_ audioData: Data) {
        let base64 = audioData.base64EncodedString()
        let message = """
        {
            "type": "audio_chunk",
            "audio": "\(base64)"
        }
        """
        
        let wsMessage = URLSessionWebSocketTask.Message.string(message)
        webSocketTask?.send(wsMessage) { error in
            if let error = error {
                print("Error sending audio: \(error)")
            }
        }
    }
    
    private func receiveMessage() {
        webSocketTask?.receive { [weak self] result in
            switch result {
            case .success(let message):
                switch message {
                case .string(let text):
                    DispatchQueue.main.async {
                        self?.lastMessage = text
                        self?.handleMessage(text)
                    }
                case .data(let data):
                    DispatchQueue.main.async {
                        self?.lastAudioData = data
                    }
                @unknown default:
                    break
                }
                self?.receiveMessage() // Continue receiving
            case .failure(let error):
                print("WebSocket receive error: \(error)")
                DispatchQueue.main.async {
                    self?.isConnected = false
                }
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
        case "response":
            if let audioBase64 = json["audio"] as? String,
               let audioData = Data(base64Encoded: audioBase64) {
                self.lastAudioData = audioData
            }
        case "error":
            if let message = json["message"] as? String {
                print("Error from server: \(message)")
            }
        default:
            break
        }
    }
}
