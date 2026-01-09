"""
Service Advertiser - Advertises Janet mesh services via Bonjour/mDNS
"""
import socket
import platform
import psutil
from typing import Dict, Any, Optional
import json

try:
    from zeroconf import ServiceInfo, Zeroconf
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False
    print("Warning: zeroconf not installed. Install with: pip install zeroconf")


class ServiceAdvertiser:
    """Advertises Janet mesh services on the local network"""
    
    def __init__(self, service_name: str = "janet-brain",
                 service_type: str = "_janetmesh._tcp",
                 port: int = 8765):
        self.service_name = service_name
        self.service_type = service_type
        self.port = port
        self.zeroconf: Optional[Zeroconf] = None
        self.service_info: Optional[ServiceInfo] = None
    
    def get_local_ip(self) -> str:
        """Get local IP address"""
        try:
            # Connect to a remote address to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except:
            return "127.0.0.1"
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Auto-detect device capabilities"""
        caps = []
        
        # Check for GPU
        try:
            import torch
            if torch.cuda.is_available():
                caps.append("cuda")
                caps.append("gpu")
        except:
            pass
        
        # Check for Metal (macOS)
        if platform.system() == "Darwin":
            caps.append("metal")
            caps.append("coreml")
        
        # Check RAM
        ram_gb = psutil.virtual_memory().total / (1024**3)
        if ram_gb > 8:
            caps.append("large_models")
        if ram_gb > 16:
            caps.append("multiple_models")
        
        # Check CPU cores
        cpu_count = psutil.cpu_count()
        if cpu_count >= 8:
            caps.append("high_performance")
        
        return {
            "capabilities": caps,
            "ram_gb": ram_gb,
            "cpu_cores": cpu_count,
            "platform": platform.system(),
            "load": 0  # Will be updated dynamically
        }
    
    def advertise(self):
        """Start advertising the service"""
        if not ZEROCONF_AVAILABLE:
            print("Cannot advertise: zeroconf not installed")
            return
        
        try:
            self.zeroconf = Zeroconf()
            local_ip = self.get_local_ip()
            capabilities = self.get_capabilities()
            
            # Create service info
            self.service_info = ServiceInfo(
                f"{self.service_type}.local.",
                f"{self.service_name}.{self.service_type}.local.",
                addresses=[socket.inet_aton(local_ip)],
                port=self.port,
                properties={
                    "capabilities": json.dumps(capabilities["capabilities"]),
                    "ram_gb": str(capabilities["ram_gb"]),
                    "cpu_cores": str(capabilities["cpu_cores"]),
                    "platform": capabilities["platform"],
                    "load": "0"
                },
                server=f"{socket.gethostname()}.local."
            )
            
            self.zeroconf.register_service(self.service_info)
            print(f"📢 Advertising as: {self.service_name} on {local_ip}:{self.port}")
            print(f"   Capabilities: {', '.join(capabilities['capabilities'])}")
        
        except Exception as e:
            print(f"Error advertising service: {e}")
    
    def update_load(self, load: float):
        """Update service load information"""
        if self.service_info and self.zeroconf:
            try:
                properties = self.service_info.properties.copy()
                properties["load"] = str(load)
                self.service_info.properties = properties
                self.zeroconf.update_service(self.service_info)
            except Exception as e:
                print(f"Error updating load: {e}")
    
    def stop(self):
        """Stop advertising the service"""
        if not self.zeroconf or not self.service_info:
            return
        
        # During shutdown, just clear references to avoid async cleanup issues
        # The service will timeout naturally on the network
        try:
            import warnings
            
            # Suppress RuntimeWarnings about coroutines during shutdown
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                
                # Try sync methods first (works for older versions)
                try:
                    if hasattr(self.zeroconf, 'unregister_service'):
                        self.zeroconf.unregister_service(self.service_info)
                    if hasattr(self.zeroconf, 'close') and not hasattr(self.zeroconf, 'async_close'):
                        # Only call sync close if async_close doesn't exist
                        self.zeroconf.close()
                except (TypeError, AttributeError):
                    # Sync methods don't work, but that's okay - service will timeout
                    pass
                
                # Clear references to prevent garbage collection issues
                self.zeroconf = None
                self.service_info = None
                
                print("Service advertisement stopped")
        except Exception:
            # Silently ignore all errors during shutdown
            # Clear references anyway to prevent warnings
            self.zeroconf = None
            self.service_info = None


if __name__ == "__main__":
    advertiser = ServiceAdvertiser()
    advertiser.advertise()
    
    try:
        import time
        time.sleep(60)  # Advertise for 60 seconds
    except KeyboardInterrupt:
        pass
    finally:
        advertiser.stop()
