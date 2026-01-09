import Vapor

/// Configures the Vapor application
public func configure(_ app: Application) throws {
    // Configure server
    app.http.server.configuration.hostname = "0.0.0.0"
    app.http.server.configuration.port = 8080
    
    // Register routes
    try routes(app)
}

func routes(_ app: Application) throws {
    let wsController = WebSocketController()
    try app.register(collection: wsController)
}
