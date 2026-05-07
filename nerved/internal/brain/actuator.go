//go:build linux

package brain

import (
	"fmt"
	"os"
	"syscall"
)

// Actuator applies Actions and logs failures. It is intentionally thin —
// all decision logic lives in plugins.
type Actuator struct{}

func newActuator() *Actuator { return &Actuator{} }

func (a *Actuator) Apply(action Action) error {
	return action.Apply()
}

// ── NiceAction ───────────────────────────────────────────────────────────────

// NiceAction adjusts a process's CPU scheduling priority.
// NewNice: -20 (highest priority) … 19 (lowest priority).
type NiceAction struct {
	PID     int
	NewNice int
}

func (a NiceAction) String() string {
	return fmt.Sprintf("nice pid=%d new=%d", a.PID, a.NewNice)
}
func (a NiceAction) Apply() error {
	return syscall.Setpriority(syscall.PRIO_PROCESS, a.PID, a.NewNice)
}

// ── OOMAction ────────────────────────────────────────────────────────────────

// OOMAction adjusts a process's OOM kill score.
// Score: -1000 (never kill) … 1000 (kill first under memory pressure).
type OOMAction struct {
	PID   int
	Score int
}

func (a OOMAction) String() string {
	return fmt.Sprintf("oom pid=%d score=%d", a.PID, a.Score)
}
func (a OOMAction) Apply() error {
	return os.WriteFile(
		fmt.Sprintf("/proc/%d/oom_score_adj", a.PID),
		[]byte(fmt.Sprintf("%d\n", a.Score)),
		0o644,
	)
}

// ── SwappinessAction ─────────────────────────────────────────────────────────

// SwappinessAction adjusts kernel swap aggressiveness globally.
// Value: 0 (avoid swap) … 100 (swap aggressively).
type SwappinessAction struct {
	Value int
}

func (a SwappinessAction) String() string {
	return fmt.Sprintf("swappiness val=%d", a.Value)
}
func (a SwappinessAction) Apply() error {
	return os.WriteFile(
		"/proc/sys/vm/swappiness",
		[]byte(fmt.Sprintf("%d\n", a.Value)),
		0o644,
	)
}
