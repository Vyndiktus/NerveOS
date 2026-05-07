package main

import (
	"flag"
	"log"
	"os"
	"os/signal"
	"syscall"

	"NerveOS/nerved/internal/brain"
	"NerveOS/nerved/internal/discovery"
	"NerveOS/nerved/internal/mesh"
	"NerveOS/nerved/internal/resources"
)


func main() {
	configPath := flag.String("config", "/etc/nerve/nerved.conf", "Path to nerved config file")
	flag.Parse()

	cfg, err := loadConfig(*configPath)
	if err != nil {
		log.Fatalf("nerved: config: %v", err)
	}

	if err := cfg.ensureIdentity(*configPath); err != nil {
		log.Fatalf("nerved: identity: %v", err)
	}

	// Inject cross-section fields (NodeID, PrivKeyPath) into subsystem configs
	cfg.wireInternals()

	log.Printf("nerved starting — node=%s name=%s", cfg.Node.ID[:8], cfg.Node.Name)

	meshMgr, err := mesh.New(cfg.Mesh)
	if err != nil {
		log.Fatalf("nerved: mesh init: %v", err)
	}

	resMgr, err := resources.New(cfg.Resources)
	if err != nil {
		log.Fatalf("nerved: resources init: %v", err)
	}

	discMgr, err := discovery.New(cfg.Mesh, meshMgr)
	if err != nil {
		log.Fatalf("nerved: discovery init: %v", err)
	}

	brainMgr, err := brain.New(cfg.Brain)
	if err != nil {
		log.Fatalf("nerved: brain init: %v", err)
	}

	// Start in order: mesh first (creates WG interface + loads keys),
	// then resources, then discovery (needs mesh public key to be ready),
	// then brain (no dependencies, but start last so system is stable).
	if err := meshMgr.Start(); err != nil {
		log.Fatalf("nerved: mesh start: %v", err)
	}
	if err := resMgr.Start(); err != nil {
		log.Fatalf("nerved: resources start: %v", err)
	}
	if err := discMgr.Start(); err != nil {
		log.Fatalf("nerved: discovery start: %v", err)
	}
	if err := brainMgr.Start(); err != nil {
		log.Fatalf("nerved: brain start: %v", err)
	}

	log.Printf("nerved running — wg-port=%d hive-ip=%s discovery=%s",
		cfg.Mesh.ListenPort, meshMgr.NerveIP(), cfg.Mesh.Discovery)

	// Drain resource advertisements (future: broadcast to peers via hive protocol)
	go func() {
		for range resMgr.Advertisements() {
		}
	}()

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	<-sig

	log.Println("nerved shutting down...")
	brainMgr.Stop()
	discMgr.Stop()
	resMgr.Stop()
	meshMgr.Stop()
}
