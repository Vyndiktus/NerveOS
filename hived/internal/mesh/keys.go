package mesh

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// LoadOrGenerateKeys returns the WireGuard private and public keys,
// generating and persisting a new keypair if none exists at privKeyPath.
func LoadOrGenerateKeys(privKeyPath string) (privKey, pubKey string, err error) {
	if data, readErr := os.ReadFile(privKeyPath); readErr == nil {
		privKey = strings.TrimSpace(string(data))
		if pk, e := derivePublicKey(privKey); e == nil {
			return privKey, pk, nil
		}
	}

	raw, err := exec.Command("wg", "genkey").Output()
	if err != nil {
		return "", "", fmt.Errorf("keys: wg genkey: %w", err)
	}
	privKey = strings.TrimSpace(string(raw))

	if err := os.MkdirAll(filepath.Dir(privKeyPath), 0o700); err != nil {
		return "", "", fmt.Errorf("keys: mkdir: %w", err)
	}
	if err := os.WriteFile(privKeyPath, []byte(privKey+"\n"), 0o600); err != nil {
		return "", "", fmt.Errorf("keys: save privkey: %w", err)
	}

	pubKey, err = derivePublicKey(privKey)
	if err != nil {
		return "", "", err
	}

	return privKey, pubKey, nil
}

func derivePublicKey(privKey string) (string, error) {
	cmd := exec.Command("wg", "pubkey")
	cmd.Stdin = strings.NewReader(privKey + "\n")
	out, err := cmd.Output()
	if err != nil {
		return "", fmt.Errorf("keys: wg pubkey: %w", err)
	}
	return strings.TrimSpace(string(out)), nil
}
