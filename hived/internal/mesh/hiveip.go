package mesh

import (
	"encoding/hex"
	"fmt"
	"net"
)

// HiveSubnet is the private address space for the hive mesh.
const HiveSubnet = "10.42.0.0/16"

// DeriveHiveIP returns a deterministic /32 IP in 10.42.0.0/16
// based on the node ID. Uses bytes 0-1 of the raw node ID as
// the third and fourth octets, giving 65536 possible addresses.
// Collision probability is ~0.15% at 10 nodes — acceptable until
// we implement a coordinator.
func DeriveHiveIP(nodeID string) (net.IP, error) {
	if len(nodeID) < 4 {
		return nil, fmt.Errorf("hiveip: node ID too short: %q", nodeID)
	}
	b, err := hex.DecodeString(nodeID[:4])
	if err != nil {
		return nil, fmt.Errorf("hiveip: decode node ID: %w", err)
	}
	// Reserve 10.42.0.0 and 10.42.0.1 (gateway/self-excluded)
	third := b[0]
	fourth := b[1]
	if third == 0 && fourth < 2 {
		fourth = 2
	}
	ip := net.IPv4(10, 42, third, fourth)
	return ip, nil
}

// HiveIPNet returns the /32 net.IPNet for a given hive IP.
func HiveIPNet(ip net.IP) net.IPNet {
	return net.IPNet{
		IP:   ip,
		Mask: net.CIDRMask(32, 32),
	}
}
