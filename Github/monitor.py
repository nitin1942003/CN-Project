from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from math import ceil
from ryu.lib import hub
from ryu import cfg
import subprocess

# Define the configuration option without registering it as a CLI option
CONF = cfg.CONF
# Default topology type
TOPO_TYPE = 'datacenter'

class NetworkMonitor(app_manager.RyuApp):
    """
    A Ryu application for monitoring network traffic and applying rate limiting.
    """

    def __init__(self, *args, **kwargs):
        super(NetworkMonitor, self).__init__(*args, **kwargs)
        # Bandwith threshold in Kbit/s
        self.bw_threshold = 5000
        self.bw_min = 100
        self.datapaths = {}
        self.query_interval = 2
        self.flow_byte_counts = {}
        self.monitor_thread = hub.spawn(self._monitor)
        self.rate_limited_switches = []
        self.simple_switch_interfaces = ["s1-eth3", "s2-eth1"]
        self.complex_switch_interfaces = ["s1-eth3", "s2-eth3", "s3-eth1", "s3-eth2", "s3-eth3", "s4-eth1", "s4-eth2",
                                          "s5-eth1", "s5-eth2", "s5-eth3", "s6-eth3", "s7-eth3"]
        self.simple_dpids = {0x1: "s1", 0x2: "s2"}
        self.complex_dpids = {0x1: "s1", 0x2: "s2", 0x3: "s3", 0x4: "s4", 0x5: "s5", 0x6: "s6", 0x7: "s7"}
        print("Topology: ", TOPO_TYPE)

    # Applies ingress restriction to a high bw switch/port
    def apply_rate_limiting(self, switch, in_port, out_port, eth_dst, rate):
        """
        Applies ingress rate limiting to a switch port.
        
        Args:
            switch (str): The switch name.
            in_port (int): The input port number.
            out_port (int): The output port number.
            eth_dst (str): The destination Ethernet address.
            rate (float): The current bitrate.
        """
        c_rate = int(ceil(rate))
        switch_id = switch + "-eth" + str(in_port) + str(out_port) + str(eth_dst)
        ingressPolicingBurst, ingressPolicingRate = "ingress_policing_burst=10", "ingress_policing_rate=5000"
        if not switch_id in self.rate_limited_switches:
            self.rate_limited_switches.append(switch_id)
            print("\n\n------------------- \n", "rate limiting ", switch_id, "\n-------------------")
            subprocess.call(["sudo", "ovs-vsctl", "set", "interface", switch + "-eth" + str(in_port), ingressPolicingBurst])
            subprocess.call(["sudo", "ovs-vsctl", "set", "interface", switch + "-eth" + str(in_port), ingressPolicingRate])

    # Removes ingress restriction to a high bw switch/port
    def revoke_rate_limiting(self, switch, in_port, out_port, eth_dst, rate):
        """
        Removes ingress rate limiting from a switch port.
        
        Args:
            switch (str): The switch name.
            in_port (int): The input port number.
            out_port (int): The output port number.
            eth_dst (str): The destination Ethernet address.
            rate (float): The current bitrate.
        """
        switch_id = switch + "-eth" + str(in_port) + str(out_port) + str(eth_dst)
        ingressPolicingBurst, ingressPolicingRate = "ingress_policing_burst=0", "ingress_policing_rate=0"
        if switch_id in self.rate_limited_switches:
            self.rate_limited_switches.remove(switch_id)
            print("\n\n------------------- \n", "undo rate limiting ", switch_id, "\n-------------------")
            subprocess.call(["sudo", "ovs-vsctl", "set", "interface", switch + "-eth" + str(in_port), ingressPolicingBurst])
            subprocess.call(["sudo", "ovs-vsctl", "set", "interface", switch + "-eth" + str(in_port), ingressPolicingRate])

    # Handler for receipt of flow statistics
    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        """
        Handler for flow statistics replies.
        """
        body = ev.msg.body
        dpid = int(ev.msg.datapath.id)
        if TOPO_TYPE == 'simple':
            switch = self.simple_dpids[dpid]
            switch_interfaces = self.simple_switch_interfaces
        elif TOPO_TYPE == 'datacenter':
            switch = self.complex_dpids[dpid]
            switch_interfaces = self.complex_switch_interfaces
        print("-------------- Flow stats for switch", switch, "---------------")

        # Iterate through all statistics reported for the flow
        for stat in sorted([flow for flow in body if flow.priority == 1], key=lambda flow: (flow.match['in_port'], flow.match['eth_dst'])):
            in_port = stat.match['in_port']
            out_port = stat.instructions[0].actions[0].port
            eth_dst = stat.match['eth_dst']

            # Check if we have a previous byte count reading for this flow
            # and calculate bandwith usage over the last polling interval
            key = (dpid, in_port, eth_dst, out_port)
            rate = 0
            if key in self.flow_byte_counts:
                cnt = self.flow_byte_counts[key]
                rate = self.bitrate(stat.byte_count - cnt)

            self.flow_byte_counts[key] = stat.byte_count
            
            # Only print if rate is non-zero
            if rate > 0:
                print("In Port %8x Eth Dst %17s Out Port %8x Bitrate %f" % (in_port, eth_dst, out_port, rate))

            switch_id = switch + "-eth" + str(in_port)
            if rate > self.bw_threshold:
                if not switch_id in switch_interfaces:
                    self.apply_rate_limiting(switch, in_port, out_port, eth_dst, rate)
            elif rate < self.bw_min:
                if not switch_id in switch_interfaces:
                    self.revoke_rate_limiting(switch, in_port, out_port, eth_dst, rate)

    @set_ev_cls(ofp_event.EventOFPStateChange,[MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        """
        Handles changes in the state of OpenFlow switches.
        
        This method adds or removes switches from the monitored datapaths
        based on their connection status.
        
        Args:
            ev (ryu.controller.ofp_event.EventOFPStateChange): The event object containing the state change information.
        """
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if not datapath.id in self.datapaths:
                self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                del self.datapaths[datapath.id]

    def _request_stats(self, datapath):
        """
        Sends requests for flow and port statistics to a datapath.
        
        Args:
            datapath (ryu.controller.controller.Datapath): The datapath to request statistics from.
        """
        print('send stats request: %016x' % datapath.id)
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

    # Convert from byte count delta to bitrate
    def bitrate(self, bytes):
        return bytes * 8.0 / (self.query_interval * 1024)

    def _monitor(self):
        """
        Main monitoring loop.
        
        This method runs in a separate green thread and periodically
        requests statistics from all active datapaths.
        """
        while True:
            for dp in self.datapaths.values():
                 self._request_stats(dp)
            hub.sleep(self.query_interval)
