from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel

class TreeTopo(Topo):
    def build(self):
        # Add switches (OpenFlow 1.3)
        # Edge Layer
        s1 = self.addSwitch('s1', protocols='OpenFlow13')
        s2 = self.addSwitch('s2', protocols='OpenFlow13')
        s6 = self.addSwitch('s6', protocols='OpenFlow13')
        s7 = self.addSwitch('s7', protocols='OpenFlow13')
        
        # Aggregation Layer
        s3 = self.addSwitch('s3', protocols='OpenFlow13')
        s5 = self.addSwitch('s5', protocols='OpenFlow13')
        
        # Core Layer
        s4 = self.addSwitch('s4', protocols='OpenFlow13')
        
        # Add hosts
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        h3 = self.addHost('h3')
        h4 = self.addHost('h4')
        h5 = self.addHost('h5')
        h6 = self.addHost('h6')
        h7 = self.addHost('h7')
        h8 = self.addHost('h8')
        
        # Add links between hosts and edge switches (10 Mbps, queue size 1000)
        edge_config = dict(bw=10, max_queue_size=1000, use_htb=True, r2q=1250)
        
        # Connect hosts to s1
        self.addLink(h1, s1, **edge_config)
        self.addLink(h2, s1, **edge_config)
        
        # Connect hosts to s2
        self.addLink(h3, s2, **edge_config)
        self.addLink(h4, s2, **edge_config)
        
        # Connect hosts to s6
        self.addLink(h5, s6, **edge_config)
        self.addLink(h6, s6, **edge_config)
        
        # Connect hosts to s7
        self.addLink(h7, s7, **edge_config)
        self.addLink(h8, s7, **edge_config)
        
        # Add links between edge and aggregation switches (20 Mbps)
        agg_config = dict(bw=20, use_htb=True, r2q=2500)
        
        # Connect edge to aggregation layer
        self.addLink(s1, s3, **agg_config)
        self.addLink(s2, s3, **agg_config)
        self.addLink(s6, s5, **agg_config)
        self.addLink(s7, s5, **agg_config)
        
        # Add links between aggregation and core switches (40 Mbps)
        core_config = dict(bw=40, use_htb=True, r2q=5000)
        
        # Connect aggregation to core layer
        self.addLink(s3, s4, **core_config)
        self.addLink(s5, s4, **core_config)

def create_network():
    # Set log level
    setLogLevel('info')
    
    # Create topology
    topo = TreeTopo()
    
    # Create network with RemoteController and OVS switches
    net = Mininet(
        topo=topo,
        controller=RemoteController,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True
    )
    
    # Add controller
    net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6633)
    
    # Start network
    net.start()
    
    # Drop into CLI
    CLI(net)
    
    # Clean up when done
    net.stop()

if __name__ == '__main__':
    create_network()