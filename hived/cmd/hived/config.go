package main

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"os"

	"github.com/BurntSushi/toml"
	"NerveOS/hived/internal/mesh"
	"NerveOS/hived/internal/resources"
)

type Config struct {
	Node      NodeConfig       `toml:"node"`
	Mesh      mesh.Config      `toml:"mesh"`
	Resources resources.Config `toml:"resources"`
	Security  SecurityConfig   `toml:"security"`
}

type NodeConfig struct {
	ID   string `toml:"id"`
	Name string `toml:"name"`
}

type SecurityConfig struct {
	WGPrivateKeyPath string `toml:"wg_private_key_path"`
	CACertPath       string `toml:"ca_cert_path"`
}

func loadConfig(path string) (*Config, error) {
	var cfg Config
	if _, err := toml.DecodeFile(path, &cfg); err != nil {
		return nil, fmt.Errorf("decode %s: %w", path, err)
	}

	// Defaults
	if cfg.Security.WGPrivateKeyPath == "" {
		cfg.Security.WGPrivateKeyPath = "/etc/hive/wg-private.key"
	}
	if cfg.Mesh.ListenPort == 0 {
		cfg.Mesh.ListenPort = 51820
	}
	if cfg.Mesh.Discovery == "" {
		cfg.Mesh.Discovery = "both"
	}

	return &cfg, nil
}

// wireInternals injects fields that span config sections into the mesh config.
// Called after ensureIdentity so NodeID is always populated.
func (cfg *Config) wireInternals() {
	cfg.Mesh.NodeID     = cfg.Node.ID
	cfg.Mesh.PrivKeyPath = cfg.Security.WGPrivateKeyPath
	// Thread storage path into resources config
	if cfg.Resources.HiveStorePath == "" {
		cfg.Resources.HiveStorePath = "/var/hive/store"
	}
}

// ensureIdentity generates a stable node ID on first boot and persists it.
func (cfg *Config) ensureIdentity(cfgPath string) error {
	if cfg.Node.ID != "" {
		return nil
	}

	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		return err
	}
	cfg.Node.ID = hex.EncodeToString(b)
	fmt.Printf("hived: generated node ID: %s\n", cfg.Node.ID)

	// Append the id to the config file so it survives reboots.
	f, err := os.OpenFile(cfgPath, os.O_APPEND|os.O_WRONLY, 0o640)
	if err != nil {
		// Config may be read-only in early boot; just warn.
		fmt.Printf("hived: warning: could not persist node ID: %v\n", err)
		return nil
	}
	defer f.Close()
	_, _ = fmt.Fprintf(f, "\n# written by hived on first boot\n[node]\nid = %q\n", cfg.Node.ID)
	return nil
}
