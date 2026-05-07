// Package discovery handles peer discovery via mDNS (WiFi/batman-adv) and
// Reticulum announce/path (LoRa, RNS overlays, long-range transports).
package discovery

import (
	"context"
	"fmt"
	"log"
	"net"
	"strconv"
	"strings"
	"time"

	"github.com/grandcat/zeroconf"
	"NerveOS/nerved/internal/mesh"
	"NerveOS/nerved/internal/transport"
)

const (
	mdnsService      = "_NerveOS._udp"
	mdnsDomain       = "local."
	announceInterval = 30 * time.Second
	browseDuration   = 10 * time.Second
)

// Manager handles peer discovery across all available transports.
type Manager struct {
	cfg        mesh.Config
	meshMgr    *mesh.Manager
	detector   *transport.Detector
	mdnsSrv    *zeroconf.Server
	rnsAnn     *transport.RNSAnnouncer
	stop       chan struct{}
}

func New(cfg mesh.Config, meshMgr *mesh.Manager) (*Manager, error) {
	return &Manager{
		cfg:      cfg,
		meshMgr:  meshMgr,
		detector: transport.NewDetector(),
		stop:     make(chan struct{}),
	}, nil
}

func (d *Manager) Start() error {
	transports := d.detector.Available()
	if len(transports) == 0 {
		log.Println("discovery: WARNING — no usable network transports detected")
	} else {
		for _, t := range transports {
			log.Printf("discovery: transport available: %s (%s) discovery=%s multi-hop=%v",
				t.Iface, t.Type, t.Discovery, t.MultiHop)
		}
	}

	// mDNS — runs over WiFi, Ethernet, and BATMAN-adv (bat0 looks like LAN)
	mdnsIfaces := d.detector.MDNSIfaces()
	if len(mdnsIfaces) > 0 {
		if err := d.startMDNS(mdnsIfaces); err != nil {
			// Non-fatal: log and continue — RNS may still work
			log.Printf("discovery: mDNS start: %v", err)
		} else {
			go d.browseMDNS()
		}
	}

	// Reticulum — starts when rnsd is available (LoRa, long-range transports)
	if d.detector.HasReticulum() || d.cfg.Discovery == "both" || d.cfg.Discovery == "dht" {
		d.rnsAnn = transport.NewRNSAnnouncer(
			d.cfg.NodeID,
			d.meshMgr.PublicKey(),
			d.meshMgr.NerveIP().String(),
		)
		d.rnsAnn.Start()
	}

	// Static peer bootstrap (direct WireGuard peers from config)
	if len(d.cfg.Peers) > 0 {
		go d.runRendezvous()
	}

	log.Printf("discovery: started (mode=%s mDNS-ifaces=%v rns=%v)",
		d.cfg.Discovery, mdnsIfaces, d.rnsAnn != nil)
	return nil
}

func (d *Manager) Stop() {
	close(d.stop)
	if d.mdnsSrv != nil {
		d.mdnsSrv.Shutdown()
	}
	if d.rnsAnn != nil {
		d.rnsAnn.Stop()
	}
	log.Println("discovery: stopped")
}

// ── mDNS ─────────────────────────────────────────────────────────────────────

// startMDNS registers this node as a _NerveOS._udp mDNS service on the
// given interfaces. Works transparently over bat0 — mDNS multicasts
// propagate across the entire BATMAN-adv mesh as if on a single LAN.
func (d *Manager) startMDNS(ifaceNames []string) error {
	// Resolve interface objects for zeroconf
	var ifaces []net.Interface
	for _, name := range ifaceNames {
		if iface, err := net.InterfaceByName(name); err == nil {
			ifaces = append(ifaces, *iface)
		}
	}
	if len(ifaces) == 0 {
		ifaces = nil // fall back to all interfaces
	}
	return d.startMDNSOnIfaces(ifaces)
}

func (d *Manager) startMDNSOnIfaces(ifaces []net.Interface) error {
	nodeID := d.cfg.NodeID
	pubKey := d.meshMgr.PublicKey()
	hiveIP := d.meshMgr.NerveIP()
	port   := d.cfg.ListenPort

	if pubKey == "" {
		return fmt.Errorf("mDNS: public key not yet available (mesh not started?)")
	}

	txt := []string{
		"id=" + nodeID,
		"pk=" + pubKey,
		"hip=" + hiveIP.String(),
		"wgp=" + strconv.Itoa(port),
		"v=1", // protocol version
	}

	instanceName := "NerveOS-" + nodeID[:8]
	srv, err := zeroconf.Register(instanceName, mdnsService, mdnsDomain, port, txt, ifaces)
	if err != nil {
		return fmt.Errorf("mDNS register: %w", err)
	}
	d.mdnsSrv = srv
	log.Printf("discovery: mDNS announced as %s (hive-ip=%s)", instanceName, hiveIP)
	return nil
}

// browseMDNS continuously browses for other _NerveOS._udp peers on the LAN.
func (d *Manager) browseMDNS() {
	// Initial browse immediately, then on interval
	d.scanOnce()

	ticker := time.NewTicker(announceInterval)
	defer ticker.Stop()

	for {
		select {
		case <-d.stop:
			return
		case <-ticker.C:
			d.scanOnce()
		}
	}
}

func (d *Manager) scanOnce() {
	resolver, err := zeroconf.NewResolver(nil)
	if err != nil {
		log.Printf("discovery: mDNS resolver: %v", err)
		return
	}

	entries := make(chan *zeroconf.ServiceEntry, 16)
	ctx, cancel := context.WithTimeout(context.Background(), browseDuration)
	defer cancel()

	if err := resolver.Browse(ctx, mdnsService, mdnsDomain, entries); err != nil {
		log.Printf("discovery: mDNS browse: %v", err)
		return
	}

	for {
		select {
		case entry, ok := <-entries:
			if !ok {
				return
			}
			d.handleMDNSEntry(entry)
		case <-ctx.Done():
			return
		case <-d.stop:
			return
		}
	}
}

func (d *Manager) handleMDNSEntry(entry *zeroconf.ServiceEntry) {
	txt := parseTXT(entry.Text)

	peerID  := txt["id"]
	peerPK  := txt["pk"]
	hipStr  := txt["hip"]
	wgpStr  := txt["wgp"]

	// Validate required fields
	if peerID == "" || peerPK == "" || hipStr == "" {
		log.Printf("discovery: mDNS incomplete entry from %s, skipping", entry.HostName)
		return
	}
	// Skip ourselves
	if peerID == d.cfg.NodeID {
		return
	}

	hiveIP := net.ParseIP(hipStr)
	if hiveIP == nil {
		log.Printf("discovery: mDNS bad hive IP %q from %s", hipStr, peerID[:8])
		return
	}

	// Prefer IPv4 LAN address for the WireGuard endpoint
	var lanIP net.IP
	if len(entry.AddrIPv4) > 0 {
		lanIP = entry.AddrIPv4[0]
	} else if len(entry.AddrIPv6) > 0 {
		lanIP = entry.AddrIPv6[0]
	} else {
		log.Printf("discovery: mDNS no address for peer %s", peerID[:8])
		return
	}

	wgPort := d.cfg.ListenPort
	if p, err := strconv.Atoi(wgpStr); err == nil && p > 0 {
		wgPort = p
	}

	endpoint := net.JoinHostPort(lanIP.String(), strconv.Itoa(wgPort))

	peer := &mesh.Peer{
		ID:        peerID,
		PublicKey: peerPK,
		Endpoint:  endpoint,
		NerveIP:    hiveIP,
	}

	if err := d.meshMgr.AddPeer(peer); err != nil {
		log.Printf("discovery: mDNS add peer %s: %v", peerID[:8], err)
	} else {
		log.Printf("discovery: mDNS found peer id=%s endpoint=%s hive-ip=%s",
			peerID[:8], endpoint, hiveIP)
	}
}

// parseTXT converts zeroconf TXT records (["key=value", ...]) into a map.
func parseTXT(records []string) map[string]string {
	m := make(map[string]string, len(records))
	for _, r := range records {
		if k, v, ok := strings.Cut(r, "="); ok {
			m[k] = v
		}
	}
	return m
}

// ── Rendezvous (internet-wide) ────────────────────────────────────────────────
// A lightweight UDP rendezvous protocol for peers that aren't on the same LAN.
// A node announces itself to a known bootstrap server; the server echoes back
// other peer announcements. This is NOT a full DHT — it's a simple signaling
// relay. A true DHT implementation is planned for a future milestone.

type rendezvousMsg struct {
	NodeID    string
	PublicKey string
	NerveIP    string
	Endpoint  string
}

func (d *Manager) runRendezvous() {
	if len(d.cfg.Peers) == 0 {
		log.Println("discovery: rendezvous: no bootstrap peers configured, skipping")
		return
	}

	log.Printf("discovery: rendezvous starting (bootstrap peers: %v)", d.cfg.Peers)

	ticker := time.NewTicker(announceInterval)
	defer ticker.Stop()

	d.announceRendezvous()

	for {
		select {
		case <-d.stop:
			return
		case <-ticker.C:
			d.announceRendezvous()
		}
	}
}

func (d *Manager) announceRendezvous() {
	// For now: dial each configured static peer directly as a WireGuard peer.
	// A full rendezvous server will replace this in a future milestone.
	// The Peers config field contains "pubkey@host:port" entries.
	for _, entry := range d.cfg.Peers {
		if err := d.addStaticPeer(entry); err != nil {
			log.Printf("discovery: static peer %q: %v", entry, err)
		}
	}
}

// addStaticPeer parses "pubkey@host:port" and adds it as a WireGuard peer.
// The hive IP is derived from a hash of the public key as a fallback until
// the peer announces its real hive IP via mDNS or rendezvous.
func (d *Manager) addStaticPeer(entry string) error {
	// format: <base64-pubkey>@<host>:<port>
	at := strings.LastIndex(entry, "@")
	if at < 0 {
		return fmt.Errorf("invalid format (expected pubkey@host:port)")
	}
	pubKey   := entry[:at]
	endpoint := entry[at+1:]

	if pubKey == "" || endpoint == "" {
		return fmt.Errorf("empty pubkey or endpoint")
	}

	// Derive a provisional hive IP from first 4 chars of a hash of pubkey
	// (will be corrected when peer announces its real hive IP)
	provisionalIP := provisionalNerveIP(pubKey)

	peer := &mesh.Peer{
		ID:        pubKey[:8],
		PublicKey: pubKey,
		Endpoint:  endpoint,
		NerveIP:    provisionalIP,
	}
	return d.meshMgr.AddPeer(peer)
}

// provisionalNerveIP derives a hive IP from a WireGuard public key string
// for use before the peer has announced its canonical hive IP.
func provisionalNerveIP(pubKey string) net.IP {
	sum := 0
	for _, b := range []byte(pubKey) {
		sum += int(b)
	}
	return net.IPv4(10, 42, byte((sum>>8)&0xff), byte(sum&0xff))
}
