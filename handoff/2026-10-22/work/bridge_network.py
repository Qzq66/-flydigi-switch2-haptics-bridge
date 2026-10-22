"""Explicit network settings; defaults preserve the Windows hotspot setup."""
from dataclasses import dataclass
import ipaddress

@dataclass(frozen=True)
class NetworkConfig:
    bind_host: str = '192.168.137.1'
    subnet: str = '192.168.137.0/24'
    port: int = 49724
    def __post_init__(self):
        network=ipaddress.IPv4Network(self.subnet)
        host=ipaddress.IPv4Address(self.bind_host)
        if host not in network or host in (network.network_address,network.broadcast_address):
            raise ValueError('Bind address must be a usable host in subnet')
        if type(self.port) is not int or not 1<=self.port<=65535:raise ValueError('Invalid UDP port')
    @property
    def broadcast(self):return str(ipaddress.IPv4Network(self.subnet).broadcast_address)
    def accepts(self,peer):
        try:
            host=ipaddress.IPv4Address(peer[0]);network=ipaddress.IPv4Network(self.subnet)
            return peer[1]==self.port and host in network and host not in (network.network_address,network.broadcast_address)
        except (ValueError,IndexError,TypeError):return False

DEFAULT_NETWORK=NetworkConfig()
