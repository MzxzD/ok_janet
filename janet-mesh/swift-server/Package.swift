// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "JanetMeshServer",
    platforms: [
        .macOS(.v13),
        .iOS(.v16)
    ],
    dependencies: [
        .package(url: "https://github.com/vapor/vapor.git", from: "4.89.0"),
        .package(url: "https://github.com/vapor/websocket-kit.git", from: "2.6.0"),
    ],
    targets: [
        .executableTarget(
            name: "App",
            dependencies: [
                .product(name: "Vapor", package: "vapor"),
                .product(name: "WebSocketKit", package: "websocket-kit"),
            ]
        ),
    ]
)
