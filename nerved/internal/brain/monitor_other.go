//go:build !linux

package brain

import "time"

// Stubs for non-Linux platforms.

type SystemState struct {
	CPUPercent  float64
	RAMTotalMB  uint64
	RAMUsedMB   uint64
	RAMPressure float64
	Procs       []ProcInfo
	Battery     BatteryInfo
	Timestamp   time.Time
}

type ProcInfo struct {
	PID     int
	Name    string
	CPUPct  float64
	RSSMB   uint64
	NiceVal int
	OOMAdj  int
}

type BatteryInfo struct {
	Present  bool
	Percent  int
	Charging bool
}

type Monitor struct{}

func newMonitor() *Monitor { return &Monitor{} }

func (m *Monitor) current() SystemState { return SystemState{Timestamp: time.Now()} }
func (m *Monitor) sample() SystemState  { return m.current() }
