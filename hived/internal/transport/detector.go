package transport

import (
	"log"
	"net"
)

// skip these interfaces — not hive transports
var skipIfaces = map[string]bool{
	"lo":    true,
	"hive0": true, // WireGuard hive tunnel (our own overlay, not a transport)
}

// Detector scans the host's network interfaces and classifies them.
type Detector struct{}

func NewDetector() *Detector { return &Detector{} }

// Available returns all usable transports currently present on the system,
// ordered by preference: batman-adv > halow > wifi > ethernet > reticulum.
func (d *Detector) Available() []*Transport {
	ifaces, err := net.Interfaces()
	if err != nil {
		log.Printf("transport: detector: %v", err)
		return nil
	}

	var transports []*Transport
	for _, iface := range ifaces {
		if skipIfaces[iface.Name] {
			continue
		}
		// Skip interfaces that are down
		if iface.Flags&net.FlagUp == 0 {
			continue
		}
		// Skip loopback
		if iface.Flags&net.FlagLoopback != 0 {
			continue
		}

		t := classifyIface(iface.Name)
		if t == TypeUnknown {
			continue
		}

		addrs := ifaceIPs(iface)
		// Require at least one usable IP (except batman — bat0 may not have one yet)
		if len(addrs) == 0 && t != TypeBatman {
			continue
		}

		transports = append(transports, &Transport{
			Type:         t,
			Iface:        iface.Name,
			Addrs:        addrs,
			Discovery:    discoveryModeFor(t),
			MultiHop:     multiHopFor(t),
			ApproxRangeM: approxRangeFor(t),
		})
	}

	return rank(transports)
}

// Best returns the highest-priority available transport, or nil.
func (d *Detector) Best() *Transport {
	all := d.Available()
	if len(all) == 0 {
		return nil
	}
	return all[0]
}

// MDNSIfaces returns interface names suitable for mDNS binding.
func (d *Detector) MDNSIfaces() []string {
	var names []string
	for _, t := range d.Available() {
		if t.Discovery == DiscoveryMDNS {
			names = append(names, t.Iface)
		}
	}
	return names
}

// HasReticulum reports whether a Reticulum transport is available.
func (d *Detector) HasReticulum() bool {
	for _, t := range d.Available() {
		if t.Type == TypeReticulum {
			return true
		}
	}
	return false
}

// HasBatman reports whether a BATMAN-adv interface is up.
func (d *Detector) HasBatman() bool {
	for _, t := range d.Available() {
		if t.Type == TypeBatman {
			return true
		}
	}
	return false
}

// ifaceIPs returns all unicast IPv4 addresses for an interface.
func ifaceIPs(iface net.Interface) []net.IP {
	addrs, err := iface.Addrs()
	if err != nil {
		return nil
	}
	var ips []net.IP
	for _, a := range addrs {
		var ip net.IP
		switch v := a.(type) {
		case *net.IPNet:
			ip = v.IP
		case *net.IPAddr:
			ip = v.IP
		}
		if ip != nil && ip.To4() != nil && !ip.IsLoopback() {
			ips = append(ips, ip)
		}
	}
	return ips
}

// rank orders transports by preference for hive use.
// Priority: batman (multi-hop mesh) > halow (long range) > wifi > ethernet > reticulum
func rank(ts []*Transport) []*Transport {
	priority := map[Type]int{
		TypeBatman:    0,
		TypeHaLow:     1,
		TypeWiFi:      2,
		TypeEthernet:  3,
		TypeReticulum: 4,
		TypeLoRa:      5,
	}
	// Simple insertion sort — transport count is tiny
	for i := 1; i < len(ts); i++ {
		for j := i; j > 0 && priority[ts[j].Type] < priority[ts[j-1].Type]; j-- {
			ts[j], ts[j-1] = ts[j-1], ts[j]
		}
	}
	return ts
}
