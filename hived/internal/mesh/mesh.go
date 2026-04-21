// Package mesh manages WireGuard tunnel creation and peer lifecycle.
package mesh

import (
	"fmt"
	"log"
	"net"
	"os/exec"
	"strings"
	"sync"
)

const wgInterface = "hive0"

type Config struct {
	NodeID      string   `toml:"-"`           // injected from NodeConfig at startup
	ListenPort  int      `toml:"listen_port"`
	Discovery   string   `toml:"discovery"`
	Peers       []string `toml:"peers"`
	PrivKeyPath string   `toml:"-"`           // injected from SecurityConfig at startup
}

type Peer struct {
	ID        string
	PublicKey string
	Endpoint  string    // host:port of the WireGuard endpoint
	HiveIP    net.IP    // peer's IP in the hive subnet
	AllowedIP net.IPNet // /32 of HiveIP
}

type Manager struct {
	cfg     Config
	mu      sync.RWMutex
	peers   map[string]*Peer // keyed by public key
	pubKey  string
	hiveIP  net.IP
	stop    chan struct{}
}

func New(cfg Config) (*Manager, error) {
	if cfg.ListenPort == 0 {
		cfg.ListenPort = 51820
	}
	return &Manager{
		cfg:   cfg,
		peers: make(map[string]*Peer),
		stop:  make(chan struct{}),
	}, nil
}

func (m *Manager) Start() error {
	// Load or generate WireGuard keypair
	privKey, pubKey, err := LoadOrGenerateKeys(m.cfg.PrivKeyPath)
	if err != nil {
		return fmt.Errorf("mesh: keys: %w", err)
	}
	m.pubKey = pubKey

	// Derive deterministic hive IP from node ID
	hiveIP, err := DeriveHiveIP(m.cfg.NodeID)
	if err != nil {
		return fmt.Errorf("mesh: hive IP: %w", err)
	}
	m.hiveIP = hiveIP

	if err := m.ensureInterface(privKey); err != nil {
		return fmt.Errorf("mesh: interface: %w", err)
	}

	// Assign hive IP to the interface
	cidr := fmt.Sprintf("%s/16", hiveIP)
	_ = exec.Command("ip", "addr", "add", cidr, "dev", wgInterface).Run()

	log.Printf("mesh: up — interface=%s port=%d hive-ip=%s pubkey=%s…",
		wgInterface, m.cfg.ListenPort, hiveIP, pubKey[:8])
	return nil
}

func (m *Manager) Stop() {
	close(m.stop)
	_ = exec.Command("ip", "link", "del", wgInterface).Run()
	log.Println("mesh: stopped")
}

// PublicKey returns this node's WireGuard public key (base64).
func (m *Manager) PublicKey() string { return m.pubKey }

// HiveIP returns this node's IP in the hive subnet.
func (m *Manager) HiveIP() net.IP { return m.hiveIP }

// Cfg exposes the mesh config to other packages that need it.
func (m *Manager) Cfg() Config { return m.cfg }

// AddPeer adds or updates a peer in the WireGuard interface.
func (m *Manager) AddPeer(p *Peer) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	// Skip ourselves
	if p.PublicKey == m.pubKey {
		return nil
	}
	// Skip already-known peers with same endpoint (no change)
	if existing, ok := m.peers[p.PublicKey]; ok && existing.Endpoint == p.Endpoint {
		return nil
	}

	ipNet := HiveIPNet(p.HiveIP)
	p.AllowedIP = ipNet

	args := []string{
		"set", wgInterface,
		"peer", p.PublicKey,
		"allowed-ips", ipNet.String(),
	}
	if p.Endpoint != "" {
		args = append(args, "endpoint", p.Endpoint)
		args = append(args, "persistent-keepalive", "25")
	}

	if err := exec.Command("wg", args...).Run(); err != nil {
		return fmt.Errorf("mesh: wg set peer %s: %w", p.ID, err)
	}

	// Add route for peer's hive IP
	_ = exec.Command("ip", "route", "add", ipNet.String(), "dev", wgInterface).Run()

	m.peers[p.PublicKey] = p
	log.Printf("mesh: peer added id=%s endpoint=%s hive-ip=%s", p.ID, p.Endpoint, p.HiveIP)
	return nil
}

// RemovePeer removes a peer from the WireGuard interface.
func (m *Manager) RemovePeer(pubKey string) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	if err := exec.Command("wg", "set", wgInterface, "peer", pubKey, "remove").Run(); err != nil {
		return fmt.Errorf("mesh: remove peer: %w", err)
	}
	delete(m.peers, pubKey)
	return nil
}

// Peers returns a snapshot of all known peers.
func (m *Manager) Peers() []*Peer {
	m.mu.RLock()
	defer m.mu.RUnlock()
	out := make([]*Peer, 0, len(m.peers))
	for _, p := range m.peers {
		out = append(out, p)
	}
	return out
}

func (m *Manager) ensureInterface(privKey string) error {
	if _, err := net.InterfaceByName(wgInterface); err == nil {
		return nil // already exists
	}

	cmds := [][]string{
		{"ip", "link", "add", wgInterface, "type", "wireguard"},
		{"ip", "link", "set", wgInterface, "up"},
	}
	for _, c := range cmds {
		if out, err := exec.Command(c[0], c[1:]...).CombinedOutput(); err != nil {
			return fmt.Errorf("%v: %s: %w", c, strings.TrimSpace(string(out)), err)
		}
	}

	// Set private key and port via wg
	wgArgs := []string{
		"set", wgInterface,
		"listen-port", fmt.Sprintf("%d", m.cfg.ListenPort),
		"private-key", m.cfg.PrivKeyPath,
	}
	if out, err := exec.Command("wg", wgArgs...).CombinedOutput(); err != nil {
		return fmt.Errorf("wg set privkey: %s: %w", strings.TrimSpace(string(out)), err)
	}

	return nil
}
