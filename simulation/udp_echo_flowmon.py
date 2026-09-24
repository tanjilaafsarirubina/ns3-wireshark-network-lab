"""UDP echo over a point-to-point link, measured with ns-3's FlowMonitor.

    n0 (10.1.1.1) ------ 5 Mbps, 2 ms ------ n1 (10.1.1.2)
    UdpEchoClient                            UdpEchoServer :9

The client sends echo requests of --packet-size bytes to the server, which
echoes them back. FlowMonitor then reports, per flow: bytes, packets, losses,
mean one-way delay and throughput.

Adapted from ns-3's examples/tutorial/first.py. Run it from an ns-3 (3.40+)
source tree built with Python bindings:

    ./ns3 shell
    python3 path/to/udp_echo_flowmon.py --packet-size 512
"""

import argparse
import csv
import os

from ns import ns

SERVER_PORT = 9
SERVER_START, CLIENT_START = 1.0, 2.0  # seconds
APP_STOP, SIM_STOP = 10.0, 20.0  # seconds

# Throughput is averaged over the window from client start to simulation end
# (18 s), the same formula used in the lab report.
THROUGHPUT_WINDOW = SIM_STOP - CLIENT_START

CSV_FIELDS = ["packet_size", "flow_id", "protocol", "source", "destination",
              "tx_bytes", "rx_bytes", "tx_packets", "rx_packets",
              "lost_packets", "mean_delay_s", "throughput_bps"]


def parse_args():
    parser = argparse.ArgumentParser(
        description="ns-3 UDP echo simulation with FlowMonitor statistics.")
    parser.add_argument("--packet-size", type=int, default=2048,
                        help="UDP payload size in bytes (default: 2048)")
    parser.add_argument("--packets", type=int, default=1,
                        help="number of echo requests to send (default: 1)")
    parser.add_argument("--interval", type=float, default=1.0,
                        help="seconds between requests (default: 1.0)")
    parser.add_argument("--data-rate", default="5Mbps",
                        help="link data rate (default: 5Mbps)")
    parser.add_argument("--delay", default="2ms",
                        help="link propagation delay (default: 2ms)")
    parser.add_argument("--csv", metavar="PATH",
                        help="append per-flow results to this CSV file")
    return parser.parse_args()


def flow_row(packet_size, flow_id, flow, st):
    proto = {6: "TCP", 17: "UDP"}.get(flow.protocol, str(flow.protocol))
    mean_delay = st.delaySum.GetSeconds() / st.rxPackets if st.rxPackets else 0.0
    return {
        "packet_size": packet_size,
        "flow_id": flow_id,
        "protocol": proto,
        "source": "%s:%s" % (flow.sourceAddress, flow.sourcePort),
        "destination": "%s:%s" % (flow.destinationAddress, flow.destinationPort),
        "tx_bytes": st.txBytes,
        "rx_bytes": st.rxBytes,
        "tx_packets": st.txPackets,
        "rx_packets": st.rxPackets,
        "lost_packets": st.lostPackets,
        "mean_delay_s": mean_delay,
        "throughput_bps": st.rxBytes * 8 / THROUGHPUT_WINDOW,
    }


def print_row(row):
    print("FlowID: %i (%s %s --> %s)" % (row["flow_id"], row["protocol"],
                                         row["source"], row["destination"]))
    print("  Tx Bytes:     ", row["tx_bytes"])
    print("  Rx Bytes:     ", row["rx_bytes"])
    print("  Tx Packets:   ", row["tx_packets"])
    print("  Rx Packets:   ", row["rx_packets"])
    print("  Lost Packets: ", row["lost_packets"])
    if row["rx_packets"] > 0:
        print("  Mean Delay:    %.4f ms" % (row["mean_delay_s"] * 1000))
        print("  Throughput:    %.2f bps" % row["throughput_bps"])


def append_csv(path, rows):
    new_file = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerows(rows)


def main():
    args = parse_args()

    ns.core.LogComponentEnable("UdpEchoClientApplication", ns.core.LOG_LEVEL_INFO)
    ns.core.LogComponentEnable("UdpEchoServerApplication", ns.core.LOG_LEVEL_INFO)

    # Topology: two nodes joined by a point-to-point link.
    nodes = ns.network.NodeContainer()
    nodes.Create(2)

    point_to_point = ns.point_to_point.PointToPointHelper()
    point_to_point.SetDeviceAttribute("DataRate", ns.core.StringValue(args.data_rate))
    point_to_point.SetChannelAttribute("Delay", ns.core.StringValue(args.delay))
    devices = point_to_point.Install(nodes)

    stack = ns.internet.InternetStackHelper()
    stack.Install(nodes)

    address = ns.internet.Ipv4AddressHelper()
    address.SetBase(ns.network.Ipv4Address("10.1.1.0"),
                    ns.network.Ipv4Mask("255.255.255.0"))
    interfaces = address.Assign(devices)

    # Applications: echo server on n1, echo client on n0.
    echo_server = ns.applications.UdpEchoServerHelper(SERVER_PORT)
    server_apps = echo_server.Install(nodes.Get(1))
    server_apps.Start(ns.core.Seconds(SERVER_START))
    server_apps.Stop(ns.core.Seconds(APP_STOP))

    server_address = interfaces.GetAddress(1).ConvertTo()
    echo_client = ns.applications.UdpEchoClientHelper(server_address, SERVER_PORT)
    echo_client.SetAttribute("MaxPackets", ns.core.UintegerValue(args.packets))
    echo_client.SetAttribute("Interval", ns.core.TimeValue(ns.core.Seconds(args.interval)))
    echo_client.SetAttribute("PacketSize", ns.core.UintegerValue(args.packet_size))
    client_apps = echo_client.Install(nodes.Get(0))
    client_apps.Start(ns.core.Seconds(CLIENT_START))
    client_apps.Stop(ns.core.Seconds(APP_STOP))

    # The helper must stay alive until the stats are read: its destructor
    # disposes of the monitor.
    flowmon_helper = ns.flow_monitor.FlowMonitorHelper()
    monitor = flowmon_helper.InstallAll()

    ns.core.Simulator.Stop(ns.core.Seconds(SIM_STOP))
    ns.core.Simulator.Run()

    monitor.CheckForLostPackets()
    classifier = flowmon_helper.GetClassifier()
    rows = []
    for flow_id, flow_stats in monitor.GetFlowStats():
        flow = classifier.FindFlow(flow_id)
        row = flow_row(args.packet_size, flow_id, flow, flow_stats)
        print_row(row)
        rows.append(row)

    if args.csv:
        append_csv(args.csv, rows)

    ns.core.Simulator.Destroy()


if __name__ == "__main__":
    main()
