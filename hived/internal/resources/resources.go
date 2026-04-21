// Package resources advertises and brokers CPU, RAM, and storage to the hive.
package resources

import (
	"bufio"
	"fmt"
	"log"
	"os"
	"runtime"
	"strconv"
	"strings"
	"syscall"
	"time"
)

type Config struct {
	AdvertiseCPU     bool `toml:"advertise_cpu"`
	AdvertiseRAM     bool `toml:"advertise_ram"`
	AdvertiseStorage bool `toml:"advertise_storage"`

	ReserveRAMMB      int    `toml:"reserve_ram_mb"`
	ReserveStorageGB  int    `toml:"reserve_storage_gb"`
	ReserveCPUPercent int    `toml:"reserve_cpu_percent"`
	HiveStorePath     string `toml:"hive_store_path"`
}

// Advertisement is the resource snapshot broadcast to peers.
type Advertisement struct {
	NodeID         string
	CPUCores       int
	CPUAvailPct    float64 // 0–100, net of reserve
	RAMTotalMB     uint64
	RAMAvailMB     uint64  // net of reserve
	StorageTotalGB uint64
	StorageAvailGB uint64  // net of reserve
}

type Manager struct {
	cfg      Config
	stop     chan struct{}
	adv      chan Advertisement
	lastCPU  cpuStat
}

func New(cfg Config) (*Manager, error) {
	if cfg.ReserveRAMMB == 0 {
		cfg.ReserveRAMMB = 512
	}
	if cfg.ReserveCPUPercent == 0 {
		cfg.ReserveCPUPercent = 20
	}
	if cfg.HiveStorePath == "" {
		cfg.HiveStorePath = "/var/hive/store"
	}
	m := &Manager{
		cfg:  cfg,
		stop: make(chan struct{}),
		adv:  make(chan Advertisement, 1),
	}
	// Prime the CPU sampler so the first reading isn't zero
	m.lastCPU, _ = readCPUStat()
	return m, nil
}

func (m *Manager) Start() error {
	go m.run()
	log.Printf("resources: started (CPUs=%d reserve-ram=%dMB reserve-cpu=%d%%)",
		runtime.NumCPU(), m.cfg.ReserveRAMMB, m.cfg.ReserveCPUPercent)
	return nil
}

func (m *Manager) Stop() {
	close(m.stop)
	log.Println("resources: stopped")
}

// Advertisements returns a channel that receives resource snapshots every 10s.
func (m *Manager) Advertisements() <-chan Advertisement {
	return m.adv
}

func (m *Manager) run() {
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-m.stop:
			return
		case <-ticker.C:
			a := m.sample()
			select {
			case m.adv <- a:
			default:
			}
		}
	}
}

func (m *Manager) sample() Advertisement {
	ramTotal, ramAvail := sampleRAM()
	cpuPct := m.sampleCPU()
	stTotal, stAvail := sampleStorage(m.cfg.HiveStorePath)

	// Apply reserves
	reserveRAM := uint64(m.cfg.ReserveRAMMB)
	if ramAvail > reserveRAM {
		ramAvail -= reserveRAM
	} else {
		ramAvail = 0
	}

	cpuAvail := cpuPct - float64(m.cfg.ReserveCPUPercent)
	if cpuAvail < 0 {
		cpuAvail = 0
	}

	reserveSt := uint64(m.cfg.ReserveStorageGB)
	if stAvail > reserveSt {
		stAvail -= reserveSt
	} else {
		stAvail = 0
	}

	a := Advertisement{
		CPUCores:       runtime.NumCPU(),
		CPUAvailPct:    cpuAvail,
		RAMTotalMB:     ramTotal,
		RAMAvailMB:     ramAvail,
		StorageTotalGB: stTotal,
		StorageAvailGB: stAvail,
	}

	log.Printf("resources: cpu=%.1f%% ram=%dMB/%dMB storage=%dGB/%dGB",
		cpuAvail, ramAvail, ramTotal, stAvail, stTotal)

	return a
}

// ── RAM — /proc/meminfo ───────────────────────────────────────────────────────

func sampleRAM() (totalMB, availMB uint64) {
	f, err := os.Open("/proc/meminfo")
	if err != nil {
		return 0, 0
	}
	defer f.Close()

	var totalKB, availKB uint64
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		switch {
		case strings.HasPrefix(line, "MemTotal:"):
			totalKB = parseMemField(line)
		case strings.HasPrefix(line, "MemAvailable:"):
			availKB = parseMemField(line)
		}
		if totalKB > 0 && availKB > 0 {
			break
		}
	}
	return totalKB / 1024, availKB / 1024
}

func parseMemField(line string) uint64 {
	// "MemTotal:       8059932 kB"
	fields := strings.Fields(line)
	if len(fields) < 2 {
		return 0
	}
	v, _ := strconv.ParseUint(fields[1], 10, 64)
	return v
}

// ── CPU — /proc/stat ─────────────────────────────────────────────────────────

type cpuStat struct {
	user, nice, system, idle, iowait, irq, softirq, steal uint64
}

func (c cpuStat) total() uint64 {
	return c.user + c.nice + c.system + c.idle + c.iowait + c.irq + c.softirq + c.steal
}

func (c cpuStat) busy() uint64 {
	return c.user + c.nice + c.system + c.irq + c.softirq + c.steal
}

func readCPUStat() (cpuStat, error) {
	f, err := os.Open("/proc/stat")
	if err != nil {
		return cpuStat{}, err
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		if !strings.HasPrefix(line, "cpu ") {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) < 9 {
			break
		}
		parse := func(i int) uint64 {
			v, _ := strconv.ParseUint(fields[i], 10, 64)
			return v
		}
		return cpuStat{
			user: parse(1), nice: parse(2), system: parse(3), idle: parse(4),
			iowait: parse(5), irq: parse(6), softirq: parse(7), steal: parse(8),
		}, nil
	}
	return cpuStat{}, fmt.Errorf("cpu stat: no aggregate cpu line found")
}

// sampleCPU returns the CPU usage percentage since the last call.
func (m *Manager) sampleCPU() float64 {
	cur, err := readCPUStat()
	if err != nil {
		return 0
	}
	prev := m.lastCPU
	m.lastCPU = cur

	totalDelta := cur.total() - prev.total()
	busyDelta  := cur.busy() - prev.busy()
	if totalDelta == 0 {
		return 0
	}
	return float64(busyDelta) / float64(totalDelta) * 100.0
}

// ── Storage — syscall.Statfs ──────────────────────────────────────────────────

func sampleStorage(path string) (totalGB, availGB uint64) {
	if path == "" {
		path = "/"
	}
	var stat syscall.Statfs_t
	if err := syscall.Statfs(path, &stat); err != nil {
		return 0, 0
	}
	bsize := uint64(stat.Bsize)
	total := stat.Blocks * bsize / 1024 / 1024 / 1024
	avail := stat.Bavail * bsize / 1024 / 1024 / 1024
	return total, avail
}
