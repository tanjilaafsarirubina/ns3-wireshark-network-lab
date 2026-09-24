"""Plot throughput and mean delay against packet size from a sweep CSV.

Measured points come from the CSV written by udp_echo_flowmon.py --csv.
The dashed lines are the analytical values for the default link
(5 Mbps, 2 ms, 1500-byte MTU), so any mismatch shows up immediately.

    python plot_results.py [--csv ../results/packet_size_sweep.csv]
                           [--out ../results/packet_size_sweep.png]
"""

import argparse
import csv
import math
from pathlib import Path

import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
DATA_RATE_BPS = 5e6
PROP_DELAY_S = 2e-3
MTU = 1500
UDP_HDR, IP_HDR, PPP_HDR = 8, 20, 2
THROUGHPUT_WINDOW_S = 18.0


def model_throughput(payload):
    """Lab formula: IP-level bytes of one packet averaged over 18 s."""
    return (payload + UDP_HDR + IP_HDR) * 8 / THROUGHPUT_WINDOW_S


def model_delay(payload):
    """Propagation + serialization of every IP fragment on the wire."""
    ip_payload = payload + UDP_HDR
    fragments = math.ceil(ip_payload / (MTU - IP_HDR))
    wire_bytes = ip_payload + fragments * (IP_HDR + PPP_HDR)
    return PROP_DELAY_S + wire_bytes * 8 / DATA_RATE_BPS


def load(path):
    points = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            size = int(row["packet_size"])
            # Both echo directions carry identical stats; keep the first.
            points.setdefault(size, (float(row["throughput_bps"]),
                                     float(row["mean_delay_s"])))
    return sorted((s, t, d) for s, (t, d) in points.items())


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv", default=HERE.parent / "results" / "packet_size_sweep.csv")
    parser.add_argument("--out", default=HERE.parent / "results" / "packet_size_sweep.png")
    args = parser.parse_args()

    sizes, throughput, delay = zip(*load(args.csv))
    xs = range(64, max(sizes) + 129)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))

    ax1.plot(xs, [model_throughput(x) for x in xs], "--", color="0.6", label="Model: 8·(size+28) / 18 s")
    ax1.plot(sizes, throughput, "o", color="#1f77b4", label="ns-3 FlowMonitor")
    ax1.set(title="Throughput vs packet size", xlabel="UDP payload (bytes)",
            ylabel="Throughput (bps)")

    ax2.plot(xs, [model_delay(x) * 1000 for x in xs], "--", color="0.6",
             label="Model: 2 ms + serialization")
    ax2.plot(sizes, [d * 1000 for d in delay], "o", color="#d62728", label="ns-3 FlowMonitor")
    ax2.axvline(MTU - IP_HDR - UDP_HDR, color="0.85", lw=1)
    ax2.annotate("IP fragmentation\n(payload > 1472 B)", xy=(MTU - IP_HDR - UDP_HDR, 4.2),
                 xytext=(560, 4.6), fontsize=9, arrowprops=dict(arrowstyle="->", color="0.5"))
    ax2.set(title="Mean one-way delay vs packet size", xlabel="UDP payload (bytes)",
            ylabel="Delay (ms)")

    for ax in (ax1, ax2):
        ax.set_xticks(range(0, max(sizes) + 1, 512))
        ax.grid(alpha=0.3)
        ax.legend(frameon=False, fontsize=9)

    fig.tight_layout()
    fig.savefig(args.out, dpi=150)
    print("Saved", args.out)


if __name__ == "__main__":
    main()
