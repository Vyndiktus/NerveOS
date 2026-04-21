package main

import (
	"flag"
	"log"
	"os"
	"os/signal"
	"syscall"

	"NerveOS/hived/internal/discovery"
	"NerveOS/hived/internal/mesh"
	"NerveOS/hived/internal/resources"
)

func main() {
	configPath := flag.String("config", "/etc/hive/hived.conf", "Path to hived config file")
	flag.Parse()

	cfg, err := loadConfig(*configPath)
	if err != nil {
		log.Fatalf("hived: config: %v", err)
	}

	if err := cfg.ensureIdentity(*configPath); err != nil {
		log.Fatalf("hived: identity: %v", err)
	}

	// Inject cross-section fields (NodeID, PrivKeyPath) into subsystem configs
	cfg.wireInternals()

	log.Printf("hived starting — node=%s name=%s", cfg.Node.ID[:8], cfg.Node.Name)

	meshMgr, err := mesh.New(cfg.Mesh)
	if err != nil {
		log.Fatalf("hived: mesh init: %v", err)
	}

	resMgr, err := resources.New(cfg.Resources)
	if err != nil {
		log.Fatalf("hived: resources init: %v", err)
	}

	discMgr, err := discovery.New(cfg.Mesh, meshMgr)
	if err != nil {
		log.Fatalf("hived: discovery init: %v", err)
	}

	// Start in order: mesh first (creates WG interface + loads keys),
	// then resources, then discovery (needs mesh public key to be ready).
	if err := meshMgr.Start(); err != nil {
		log.Fatalf("hived: mesh start: %v", err)
	}
	if err := resMgr.Start(); err != nil {
		log.Fatalf("hived: resources start: %v", err)
	}
	if err := discMgr.Start(); err != nil {
		log.Fatalf("hived: discovery start: %v", err)
	}

	log.Printf("hived running — wg-port=%d hive-ip=%s discovery=%s",
		cfg.Mesh.ListenPort, meshMgr.HiveIP(), cfg.Mesh.Discovery)

	// Drain resource advertisements (future: broadcast to peers via hive protocol)
	go func() {
		for range resMgr.Advertisements() {
		}
	}()

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	<-sig

	log.Println("hived shutting down...")
	discMgr.Stop()
	resMgr.Stop()
	meshMgr.Stop()
}
