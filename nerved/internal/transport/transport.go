// Package transport detects and classifies network transports available
// to the hive, enabling nerved to adapt its behaviour across WiFi, BATMAN-adv
// mesh, Reticulum overlays, HaLow, and future radio types.
package transport

import (
	"net"
	"strings"
)

// Type identifies the physical or logical transport medium.
type Type int

const (
	TypeUnknown    Type = iota
	TypeEthernet        // wired Ethernet (eth0, en*)
	TypeWiFi            // standard WiFi (wlan*, mlan*)
	TypeBatman          // BATMAN-adv virtual interface (bat0) — L2 mesh
	TypeHaLow           // WiFi HaLow 802.11ah (halow*, wlan* on sub-1GHz)
	TypeReticulum       // Reticulum tunnel interface (rns*)
	TypeLoRa            // LoRa via Reticulum RNode
)

func (t Type) String() string {
	switch t {
	case TypeEthernet:
		return "ethernet"
	case TypeWiFi:
		return "wifi"
	case TypeBatman:
		return "batman-adv"
	case TypeHaLow:
		return "halow"
	case TypeReticulum:
		return "reticulum"
	case TypeLoRa:
		return "lora"
	default:
		return "unknown"
	}
}

// DiscoveryMode describes how peers should be discovered over this transport.
type DiscoveryMode int

const (
	// DiscoveryMDNS — standard mDNS multicast (works on WiFi, batman-adv, ethernet)
	DiscoveryMDNS DiscoveryMode = iota
	// DiscoveryRNS — Reticulum announce/path system (used for RNS and LoRa transports)
	DiscoveryRNS
)

// Transport represents a single network transport available to the hive.
type Transport struct {
	Type          Type
	Iface         string        // Linux interface name (e.g. "bat0", "wlan0")
	Addrs         []net.IP      // IP addresses bound to this interface
	Discovery     DiscoveryMode // how to discover peers on this transport
	MultiHop      bool          // true if the transport handles multi-hop routing itself
	ApproxRangeM  int           // approximate physical range in metres (0 = unknown)
}

// Capability returns a human-readable description of this transport.
func (t *Transport) Capability() string {
	switch t.Type {
	case TypeBatman:
		return "L2 mesh (BATMAN-adv) — multi-hop, auto-healing"
	case TypeHaLow:
		return "WiFi HaLow 802.11ah — km-range, ~15 Mbps"
	case TypeReticulum:
		return "Reticulum overlay — encrypted, works over any carrier"
	case TypeLoRa:
		return "LoRa — ultra-long range, ~1 kbps"
	case TypeWiFi:
		return "WiFi — LAN, ~100m"
	case TypeEthernet:
		return "Ethernet — LAN, wired"
	default:
		return "unknown"
	}
}

// classifyIface maps an interface name to its transport type.
func classifyIface(name string) Type {
	switch {
	case name == "bat0" || strings.HasPrefix(name, "bat"):
		return TypeBatman
	case strings.HasPrefix(name, "rns"):
		return TypeReticulum
	case strings.HasPrefix(name, "halow") || strings.HasPrefix(name, "ah"):
		return TypeHaLow
	case strings.HasPrefix(name, "wlan") || strings.HasPrefix(name, "mlan") ||
		strings.HasPrefix(name, "wlp"):
		return TypeWiFi
	case strings.HasPrefix(name, "eth") || strings.HasPrefix(name, "en") ||
		strings.HasPrefix(name, "eno") || strings.HasPrefix(name, "enp"):
		return TypeEthernet
	default:
		return TypeUnknown
	}
}

// discoveryModeFor returns the appropriate discovery mode for a transport type.
func discoveryModeFor(t Type) DiscoveryMode {
	switch t {
	case TypeReticulum, TypeLoRa:
		return DiscoveryRNS
	default:
		return DiscoveryMDNS
	}
}

// multiHopFor returns whether a transport handles multi-hop routing itself.
func multiHopFor(t Type) bool {
	return t == TypeBatman || t == TypeReticulum || t == TypeLoRa
}

// approxRangeFor returns the approximate range in metres for a transport type.
func approxRangeFor(t Type) int {
	switch t {
	case TypeLoRa:
		return 15000
	case TypeHaLow:
		return 5000
	case TypeBatman:
		return 0 // depends on underlying interfaces
	case TypeWiFi:
		return 100
	case TypeEthernet:
		return 100
	default:
		return 0
	}
}
