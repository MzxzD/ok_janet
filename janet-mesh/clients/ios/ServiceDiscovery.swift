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
    
    func getServiceURL(from result: NWBrowser.Result) -> String? {
        switch result.endpoint {
        case .service(let name, let type, let domain, _):
            // Construct WebSocket URL
            // In a real implementation, you'd resolve the endpoint to get the IP
            return "ws://\(name).\(domain):8080/ws"
        default:
            return nil
        }
    }
}
