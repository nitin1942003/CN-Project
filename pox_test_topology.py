#!/usr/bin/env python3

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info

def createTopology():
    "Create a simple topology with 2 hosts and 2 switches"
    
    # Create network with custom switch
    net = Mininet(switch=OVSSwitch, controller=None)
    
    info('*** Adding controller\n')
    # Add controller with specific IP and port
    c0 = net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6633)
    
    info('*** Adding hosts\n')
    h1 = net.addHost('h1', ip='10.0.0.1/24')
    h2 = net.addHost('h2', ip='10.0.0.2/24')
    
    info('*** Adding switches\n')
    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2')
    
    info('*** Creating links\n')
    net.addLink(h1, s1)
    net.addLink(s1, s2)
    net.addLink(s2, h2)
    
    info('*** Starting network\n')
    net.start()
    
    # Connect switches to controller
    for switch in net.switches:
        switch.start([c0])
    
    info('*** Running CLI\n')
    CLI(net)
    
    info('*** Stopping network\n')
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    createTopology() 