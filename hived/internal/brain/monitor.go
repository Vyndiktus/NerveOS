//go:build linux

package brain

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"
)

// SystemState is a point-in-time snapshot of the device's resource usage.
// Plugins receive this on every tick and base their decisions on it.
type SystemState struct {
	CPUPercent  float64     // 0–100, system-wide
	RAMTotalMB  uint64
	RAMUsedMB   uint64
	RAMPressure float64     // 0.0 (empty) – 1.0 (full)
	Procs       []ProcInfo
	Battery     BatteryInfo
	Timestamp   time.Time
}

// ProcInfo is the per-process snapshot visible to plugins.
type ProcInfo struct {
	PID     int
	Name    string
	CPUPct  float64 // since last tick
	RSSMB   uint64  // resident set size
	NiceVal int     // current nice value (-20..19)
	OOMAdj  int     // current oom_score_adj
}

// BatteryInfo holds power supply state from sysfs.
type BatteryInfo struct {
	Present  bool
	Percent  int
	Charging bool
}

// Monitor reads /proc at each tick and maintains the current SystemState.
type Monitor struct {
	mu       sync.RWMutex
	state    SystemState
	lastCPU  cpuStat
	lastProc map[int]procTick // per-pid CPU accounting
}

type procTick struct{ utime, stime, sysTotal uint64 }

func newMonitor() *Monitor {
	m := &Monitor{lastProc: make(map[int]procTick)}
	m.lastCPU, _ = readCPUStat()
	return m
}

func (m *Monitor) current() SystemState {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.state
}

func (m *Monitor) sample() SystemState {
	s := SystemState{Timestamp: time.Now()}

	// System-wide CPU
	cur, _ := readCPUStat()
	s.CPUPercent = cpuDelta(m.lastCPU, cur)
	m.lastCPU = cur

	// RAM
	s.RAMTotalMB, s.RAMUsedMB = readRAM()
	if s.RAMTotalMB > 0 {
		s.RAMPressure = float64(s.RAMUsedMB) / float64(s.RAMTotalMB)
	}

	// Per-process stats
	s.Procs = m.readProcs(cur.total())

	// Battery
	s.Battery = readBattery()

	m.mu.Lock()
	m.state = s
	m.mu.Unlock()
	return s
}

// ── CPU ──────────────────────────────────────────────────────────────────────

type cpuStat struct {
	user, nice, sys, idle, iowait, irq, softirq, steal uint64
}

func (c cpuStat) total() uint64 {
	return c.user + c.nice + c.sys + c.idle + c.iowait + c.irq + c.softirq + c.steal
}
func (c cpuStat) busy() uint64 {
	return c.user + c.nice + c.sys + c.irq + c.softirq + c.steal
}

func readCPUStat() (cpuStat, error) {
	f, err := os.Open("/proc/stat")
	if err != nil {
		return cpuStat{}, err
	}
	defer f.Close()

	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := sc.Text()
		if !strings.HasPrefix(line, "cpu ") {
			continue
		}
		flds := strings.Fields(line)
		p := func(i int) uint64 {
			if i >= len(flds) {
				return 0
			}
			v, _ := strconv.ParseUint(flds[i], 10, 64)
			return v
		}
		return cpuStat{p(1), p(2), p(3), p(4), p(5), p(6), p(7), p(8)}, nil
	}
	return cpuStat{}, fmt.Errorf("no aggregate cpu line in /proc/stat")
}

func cpuDelta(prev, cur cpuStat) float64 {
	dt := cur.total() - prev.total()
	db := cur.busy() - prev.busy()
	if dt == 0 {
		return 0
	}
	return float64(db) / float64(dt) * 100.0
}

// ── RAM ──────────────────────────────────────────────────────────────────────

func readRAM() (totalMB, usedMB uint64) {
	f, err := os.Open("/proc/meminfo")
	if err != nil {
		return
	}
	defer f.Close()

	var totalKB, availKB uint64
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := sc.Text()
		flds := strings.Fields(line)
		if len(flds) < 2 {
			continue
		}
		v, _ := strconv.ParseUint(flds[1], 10, 64)
		switch {
		case strings.HasPrefix(line, "MemTotal:"):
			totalKB = v
		case strings.HasPrefix(line, "MemAvailable:"):
			availKB = v
		}
		if totalKB > 0 && availKB > 0 {
			break
		}
	}
	totalMB = totalKB / 1024
	usedMB = (totalKB - availKB) / 1024
	return
}

// ── Processes ────────────────────────────────────────────────────────────────

func (m *Monitor) readProcs(sysTotalNow uint64) []ProcInfo {
	entries, err := os.ReadDir("/proc")
	if err != nil {
		return nil
	}

	next := make(map[int]procTick, len(m.lastProc))
	var procs []ProcInfo

	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		pid, err := strconv.Atoi(e.Name())
		if err != nil {
			continue
		}

		name, utime, stime, rssPages, nice, err := readOneProcStat(pid)
		if err != nil {
			continue
		}
		oom := readOOMAdj(pid)

		var cpuPct float64
		if prev, ok := m.lastProc[pid]; ok {
			dt := sysTotalNow - prev.sysTotal
			db := (utime + stime) - (prev.utime + prev.stime)
			if dt > 0 {
				cpuPct = float64(db) / float64(dt) * 100.0
			}
		}
		next[pid] = procTick{utime, stime, sysTotalNow}

		procs = append(procs, ProcInfo{
			PID:     pid,
			Name:    name,
			CPUPct:  cpuPct,
			RSSMB:   rssPages * 4 / 1024, // pages→KB→MB
			NiceVal: nice,
			OOMAdj:  oom,
		})
	}

	m.lastProc = next
	return procs
}

func readOneProcStat(pid int) (name string, utime, stime, rssPages uint64, nice int, err error) {
	data, err := os.ReadFile(fmt.Sprintf("/proc/%d/stat", pid))
	if err != nil {
		return
	}
	s := string(data)

	// comm is wrapped in parens and may contain spaces/parens itself —
	// find the outermost pair.
	open := strings.Index(s, "(")
	close := strings.LastIndex(s, ")")
	if open < 0 || close < 0 || close <= open {
		err = fmt.Errorf("malformed stat")
		return
	}
	name = s[open+1 : close]

	// Fields after ')' are space-separated; index from 0 = state (field 3).
	rest := strings.Fields(s[close+2:])
	p := func(i int) uint64 {
		if i >= len(rest) {
			return 0
		}
		v, _ := strconv.ParseUint(rest[i], 10, 64)
		return v
	}
	pi := func(i int) int {
		if i >= len(rest) {
			return 0
		}
		v, _ := strconv.ParseInt(rest[i], 10, 64)
		return int(v)
	}
	// Offsets relative to rest[0]=state:
	// rest[11]=utime, rest[12]=stime, rest[16]=nice, rest[21]=rss (pages)
	utime    = p(11)
	stime    = p(12)
	nice     = pi(16)
	rssPages = p(21)
	return
}

func readOOMAdj(pid int) int {
	d, err := os.ReadFile(fmt.Sprintf("/proc/%d/oom_score_adj", pid))
	if err != nil {
		return 0
	}
	v, _ := strconv.Atoi(strings.TrimSpace(string(d)))
	return v
}

// ── Battery ──────────────────────────────────────────────────────────────────

var batteryPaths = []string{
	"/sys/class/power_supply/battery",
	"/sys/class/power_supply/Battery",
	"/sys/class/power_supply/BAT0",
	"/sys/class/power_supply/BAT1",
}

func readBattery() BatteryInfo {
	for _, base := range batteryPaths {
		raw, err := os.ReadFile(base + "/capacity")
		if err != nil {
			continue
		}
		pct, err := strconv.Atoi(strings.TrimSpace(string(raw)))
		if err != nil {
			continue
		}
		status, _ := os.ReadFile(base + "/status")
		st := strings.ToLower(strings.TrimSpace(string(status)))
		charging := st == "charging" || st == "full"
		return BatteryInfo{Present: true, Percent: pct, Charging: charging}
	}
	return BatteryInfo{}
}
