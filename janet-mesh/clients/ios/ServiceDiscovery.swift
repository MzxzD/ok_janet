import Foundation
import Network

/// Service discovery using Bonjour/mDNS
@available(iOS 14.0, *)
class ServiceDiscovery: ObservableObject {
    @Published var discoveredServices: [NWBrowser.Result] = []
    @Published var isSearching = false
    
    private var browser: NWBrowser?
    private let bonjourType = "_janetmesh._tcp"
    
    func startDiscovery() {
        guard !isSearching else { return }
        
        isSearching = true
        let parameters = NWParameters()
        parameters.includePeerToPeer = true
        
        browser = NWBrowser(for: .bonjour(type: bonjourType, domain: nil), using: parameters)
        
        browser?.stateUpdateHandler = { [weak self] newState in
            DispatchQueue.main.async {
                switch newState {
                case .ready:
                    print("Service discovery ready")
                case .failed(let error):
                    print("Service discovery failed: \(error)")
                    self?.isSearching = false
                default:
                    break
                }
            }
        }
        
        browser?.browseResultsChangedHandler = { [weak self] results, changes in
            DispatchQueue.main.async {
                self?.discoveredServices = Array(results)
                print("Found \(results.count) Janet mesh services")
            }
        }
        
        browser?.start(queue: .main)
    }
    
    func stopDiscovery() {
        browser?.cancel()
        browser = nil
        isSearching = false
        discoveredServices = []
    }
    
    func getServiceURL(from result: NWBrowser.Result, completion: @escaping (String?) -> Void) {
        // First, try to get IP from service metadata if available
        // The server advertises IP in service properties
        print("🔍 Getting service URL from: \(result)")
        
        switch result.endpoint {
        case .hostPort(let host, let port):
            // Direct IP:port endpoint - use immediately
            let url = "ws://\(host):\(port)"
            print("✅ Direct endpoint found: \(url)")
            completion(url)
            
        case .service(let name, let type, let domain, _):
            // Bonjour service - resolve hostname directly to get IP
            // The service is advertised as janet-brain._janetmesh._tcp.local.
            // We'll resolve the hostname to get the IP address
            let hostname = "\(name).\(domain)"
            print("🔍 Resolving Bonjour hostname: \(hostname)")
            
            // Use NWConnection to resolve hostname to IP
            let resolveConnection = NWConnection(
                host: NWEndpoint.Host(hostname),
                port: NWEndpoint.Port(integerLiteral: 8765),
                using: .tcp
            )
            
            var resolved = false
            var timeoutWorkItem: DispatchWorkItem?
            
            // Set 3 second timeout
            timeoutWorkItem = DispatchWorkItem {
                if !resolved {
                    resolved = true
                    resolveConnection.cancel()
                    print("⏱️ Hostname resolution timeout")
                    print("⚠️ Could not resolve service automatically")
                    print("💡 Please enter server IP manually in Settings (e.g., ws://192.168.0.52:8765)")
                    completion(nil)
                }
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 3.0, execute: timeoutWorkItem!)
            
            resolveConnection.stateUpdateHandler = { state in
                switch state {
                case .ready:
                    if !resolved {
                        resolved = true
                        timeoutWorkItem?.cancel()
                        
                        // Get resolved IP from connection path
                        if let path = resolveConnection.currentPath,
                           case .hostPort(let host, let port) = path.remoteEndpoint {
                            let url = "ws://\(host):\(port)"
                            print("✅ Resolved service to: \(url)")
                            resolveConnection.cancel()
                            completion(url)
                        } else {
                            print("⚠️ Could not extract IP from connection")
                            resolveConnection.cancel()
                            completion(nil)
                        }
                    }
                    
                case .failed(let error):
                    if !resolved {
                        resolved = true
                        timeoutWorkItem?.cancel()
                        print("❌ Hostname resolution failed: \(error)")
                        resolveConnection.cancel()
                        completion(nil)
                    }
                    
                case .waiting(let error):
                    print("⏳ Resolution in progress: \(error)")
                    
                default:
                    break
                }
            }
            
            resolveConnection.start(queue: .main)
            
        default:
            completion(nil)
        }
    }
    
    // Convenience method that returns synchronously (for backward compatibility)
    func getServiceURL(from result: NWBrowser.Result) -> String? {
        // This is a fallback - prefer using the async version
        switch result.endpoint {
        case .hostPort(let host, let port):
            return "ws://\(host):\(port)"
        default:
            return nil
        }
    }
}
