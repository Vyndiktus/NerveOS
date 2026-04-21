package transport

// RNS announce/path discovery for Reticulum transports.
// Reticulum handles its own routing and encryption — hived only needs to
// announce its presence and respond to path requests via the RNS Python API
// (invoked via rnstatus/rnpath CLI tools or the shared instance socket).
//
// Full RNS integration (direct socket protocol) is a future milestone.
// This file provides the scaffolding and the CLI-based bridge for now.

import (
	"fmt"
	"log"
	"os/exec"
	"strings"
	"time"
)

const (
	rnsInstanceAddr = "localhost:37428" // rnsd shared instance port (from reticulum.config)
	rnsAnnounceInterval = 60 * time.Second
)

// RNSAnnouncer announces this hive node via Reticulum and discovers peers.
type RNSAnnouncer struct {
	nodeID  string
	pubKey  string
	hiveIP  string
	stop    chan struct{}
}

func NewRNSAnnouncer(nodeID, pubKey, hiveIP string) *RNSAnnouncer {
	return &RNSAnnouncer{
		nodeID: nodeID,
		pubKey: pubKey,
		hiveIP: hiveIP,
		stop:   make(chan struct{}),
	}
}

// Start begins periodic Reticulum announces.
func (r *RNSAnnouncer) Start() {
	go r.run()
	log.Printf("transport/rns: announcer started for node %s", r.nodeID[:8])
}

func (r *RNSAnnouncer) Stop() {
	close(r.stop)
}

func (r *RNSAnnouncer) run() {
	// Check rnsd is reachable before starting
	if !r.rnsdAvailable() {
		log.Println("transport/rns: rnsd not available — RNS discovery disabled")
		return
	}

	r.announce()

	ticker := time.NewTicker(rnsAnnounceInterval)
	defer ticker.Stop()
	for {
		select {
		case <-r.stop:
			return
		case <-ticker.C:
			r.announce()
			r.discover()
		}
	}
}

// announce sends an RNS announce carrying this node's hived identity.
// The app_name "NerveOS" + aspect "node" namespaces our announces from
// other RNS applications sharing the same transport.
func (r *RNSAnnouncer) announce() {
	appData := fmt.Sprintf("id=%s,pk=%s,hip=%s", r.nodeID, r.pubKey, r.hiveIP)

	// Use rnsd's Python API via a one-shot Python invocation.
	// Future: use the shared instance socket directly for efficiency.
	script := fmt.Sprintf(`
import RNS, time
RNS.Reticulum(configdir="/etc/reticulum", loglevel=RNS.LOG_WARNING)
id = RNS.Identity()
dest = RNS.Destination(id, RNS.Destination.IN, RNS.Destination.SINGLE, "NerveOS", "node")
dest.set_proof_strategy(RNS.Destination.PROVE_ALL)
dest.announce(app_data=b"%s")
time.sleep(1)
`, appData)

	cmd := exec.Command("python3", "-c", script)
	if out, err := cmd.CombinedOutput(); err != nil {
		log.Printf("transport/rns: announce error: %v — %s", err, strings.TrimSpace(string(out)))
	} else {
		log.Printf("transport/rns: announced node %s over RNS", r.nodeID[:8])
	}
}

// discover queries RNS for other NerveOS.node destinations.
func (r *RNSAnnouncer) discover() {
	// rnstatus gives us a list of known paths — parse for NerveOS.node entries
	out, err := exec.Command("rnpath", "--all").Output()
	if err != nil {
		return
	}
	for _, line := range strings.Split(string(out), "\n") {
		if strings.Contains(line, "NerveOS.node") {
			log.Printf("transport/rns: discovered peer via RNS: %s", strings.TrimSpace(line))
			// TODO: extract destination hash, request path, fetch app_data (peer info),
			// then call meshMgr.AddPeer() — requires a proper RNS socket client.
		}
	}
}

// rnsdAvailable checks whether the Reticulum daemon is running.
func (r *RNSAnnouncer) rnsdAvailable() bool {
	out, err := exec.Command("rnstatus", "--short").Output()
	if err != nil {
		return false
	}
	return strings.Contains(string(out), "Transport")
}
