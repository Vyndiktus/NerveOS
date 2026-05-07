//go:build !linux

// Stub for non-Linux platforms.
package resources

import "log"

type Config struct {
	AdvertiseCPU      bool   `toml:"advertise_cpu"`
	AdvertiseRAM      bool   `toml:"advertise_ram"`
	AdvertiseStorage  bool   `toml:"advertise_storage"`
	ReserveRAMMB      int    `toml:"reserve_ram_mb"`
	ReserveStorageGB  int    `toml:"reserve_storage_gb"`
	ReserveCPUPercent int    `toml:"reserve_cpu_percent"`
	HiveStorePath     string `toml:"hive_store_path"`
}

type Advertisement struct {
	NodeID         string
	CPUCores       int
	CPUAvailPct    float64
	RAMTotalMB     uint64
	RAMAvailMB     uint64
	StorageTotalGB uint64
	StorageAvailGB uint64
}

type Manager struct{ adv chan Advertisement }

func New(_ Config) (*Manager, error) {
	return &Manager{adv: make(chan Advertisement, 1)}, nil
}

func (m *Manager) Start() error {
	log.Println("resources: stub (non-Linux)")
	return nil
}
func (m *Manager) Stop()                              { log.Println("resources: stopped") }
func (m *Manager) Advertisements() <-chan Advertisement { return m.adv }
