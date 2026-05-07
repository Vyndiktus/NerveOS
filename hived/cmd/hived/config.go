package main

import (
	"bytes"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"os"

	"github.com/BurntSushi/toml"
	"NerveOS/hived/internal/brain"
	"NerveOS/hived/internal/mesh"
	"NerveOS/hived/internal/resources"
)

type Config struct {
	Node      NodeConfig       `toml:"node"`
	Mesh      mesh.Config      `toml:"mesh"`
	Resources resources.Config `toml:"resources"`
	Brain     brain.Config     `toml:"brain"`
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

	// Rewrite the config file so the generated ID persists across reboots.
	var buf bytes.Buffer
	if err := toml.NewEncoder(&buf).Encode(cfg); err != nil {
		fmt.Printf("hived: warning: could not encode config: %v\n", err)
		return nil
	}
	if err := os.WriteFile(cfgPath, buf.Bytes(), 0o640); err != nil {
		fmt.Printf("hived: warning: could not persist node ID: %v\n", err)
	}
	return nil
}
