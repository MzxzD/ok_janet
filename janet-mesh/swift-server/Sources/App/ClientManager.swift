import Vapor
import WebSocketKit

/// Manages client WebSocket connections
final class ClientManager {
    private var clients: [String: WebSocket] = [:]
    private let lock = NSLock()
    
    func add(clientId: String, websocket: WebSocket) {
        lock.lock()
        defer { lock.unlock() }
        clients[clientId] = websocket
    }
    
    func remove(clientId: String) {
        lock.lock()
        defer { lock.unlock() }
        clients.removeValue(forKey: clientId)
    }
    
    func get(clientId: String) -> WebSocket? {
        lock.lock()
        defer { lock.unlock() }
        return clients[clientId]
    }
    
    func getAll() -> [String: WebSocket] {
        lock.lock()
        defer { lock.unlock() }
        return clients
    }
    
    func count() -> Int {
        lock.lock()
        defer { lock.unlock() }
        return clients.count
    }
}
