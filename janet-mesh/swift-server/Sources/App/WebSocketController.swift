import Vapor
import WebSocketKit
import Foundation
import NIOCore

/// WebSocket controller that relays messages between clients and Python service
final class WebSocketController: RouteCollection {
    private let clientManager = ClientManager()
    private let pythonServiceURL = "ws://localhost:8765"
    
    func boot(routes: RoutesBuilder) throws {
        routes.webSocket("ws", onUpgrade: handleWebSocket)
        routes.get("status") { req -> [String: Any] in
            return [
                "connected_clients": self.clientManager.count(),
                "status": "running"
            ]
        }
    }
    
    private func handleWebSocket(req: Request, ws: WebSocket) {
        // Generate or extract client ID
        let clientId = UUID().uuidString
        clientManager.add(clientId: clientId, websocket: ws)
        
        req.logger.info("Client connected: \(clientId)")
        
        // Connect to Python service
        let pythonURL = URL(string: pythonServiceURL)!
        let pythonHost = pythonURL.host ?? "localhost"
        let pythonPort = pythonURL.port ?? 8765
        
        WebSocket.connect(
            host: pythonHost,
            port: pythonPort,
            on: req.eventLoop
        ) { pythonWS in
            // Send welcome message to client
            let welcomeMessage = """
            {
                "type": "connected",
                "client_id": "\(clientId)",
                "status": "ready"
            }
            """
            ws.send(welcomeMessage)
            
            // Forward messages from client to Python service
            ws.onText { ws, text in
                req.logger.debug("Client -> Python: \(text)")
                pythonWS.send(text)
            }
            
            ws.onBinary { ws, buffer in
                // Convert binary to base64 for JSON transport
                let data = Data(buffer: buffer)
                let base64 = data.base64EncodedString()
                let message = """
                {
                    "type": "audio_chunk",
                    "client_id": "\(clientId)",
                    "audio": "\(base64)"
                }
                """
                pythonWS.send(message)
            }
            
            // Forward messages from Python service to client
            pythonWS.onText { ws, text in
                req.logger.debug("Python -> Client: \(text)")
                ws.send(text)
            }
            
            // Handle client disconnect
            ws.onClose.whenComplete { _ in
                req.logger.info("Client disconnected: \(clientId)")
                self.clientManager.remove(clientId: clientId)
                pythonWS.close()
            }
            
            // Handle Python service disconnect
            pythonWS.onClose.whenComplete { _ in
                req.logger.warning("Python service disconnected")
                let errorMessage = """
                {
                    "type": "error",
                    "message": "Python service disconnected"
                }
                """
                ws.send(errorMessage)
                ws.close()
            }
        }.whenFailure { error in
            req.logger.error("Failed to connect to Python service: \(error)")
            let errorMessage = """
            {
                "type": "error",
                "message": "Failed to connect to Python service"
            }
            """
            ws.send(errorMessage)
            ws.close()
        }
    }
}
