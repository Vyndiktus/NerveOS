package brain

import (
	"log"
	"strings"
)

// ── ResourceGuard ─────────────────────────────────────────────────────────────
// Keeps critical processes protected: nice=-5, oom=-900.
// This runs every tick but only emits actions when a value drifts.

type ResourceGuard struct {
	protected map[string]bool
}

func newResourceGuard(names []string) *ResourceGuard {
	m := make(map[string]bool, len(names))
	for _, n := range names {
		m[n] = true
	}
	return &ResourceGuard{m}
}

func (g *ResourceGuard) Name() string { return "resource-guard" }

func (g *ResourceGuard) Tick(s SystemState) (out []Action) {
	for _, p := range s.Procs {
		if !g.isCritical(p.Name) {
			continue
		}
		targetNice := -5
		if p.Name == "hived" {
			targetNice = -10 // hived runs at higher priority than all other protected procs
		}
		if p.OOMAdj != -900 {
			out = append(out, OOMAction{PID: p.PID, Score: -900})
		}
		if p.NiceVal > targetNice {
			out = append(out, NiceAction{PID: p.PID, NewNice: targetNice})
		}
	}
	return
}

func (g *ResourceGuard) isCritical(name string) bool {
	return g.protected[name]
}

// ── IdleThrottler ─────────────────────────────────────────────────────────────
// When the system is busy (>75% CPU), deprioritises non-critical processes
// that are each consuming >15% CPU by raising their nice value to 10.
// When the system cools down, nice values are restored to 0.

type IdleThrottler struct {
	protected  map[string]bool
	throttled  map[int]bool // pids currently throttled by us
	busyThresh float64      // system CPU% to trigger throttling
	procThresh float64      // per-proc CPU% that marks it as a hog
}

func newIdleThrottler(names []string) *IdleThrottler {
	m := make(map[string]bool, len(names))
	for _, n := range names {
		m[n] = true
	}
	return &IdleThrottler{
		protected:  m,
		throttled:  make(map[int]bool),
		busyThresh: 75.0,
		procThresh: 15.0,
	}
}

func (t *IdleThrottler) Name() string { return "idle-throttler" }

func (t *IdleThrottler) Tick(s SystemState) (out []Action) {
	busy := s.CPUPercent > t.busyThresh

	// Build current PID set to detect dead processes.
	alive := make(map[int]bool, len(s.Procs))
	for _, p := range s.Procs {
		alive[p.PID] = true
	}
	for pid := range t.throttled {
		if !alive[pid] {
			delete(t.throttled, pid)
		}
	}

	for _, p := range s.Procs {
		if p.PID <= 1 || t.protected[p.Name] || isKernelThread(p.Name) {
			continue
		}
		if busy && p.CPUPct > t.procThresh && !t.throttled[p.PID] && p.NiceVal < 10 {
			out = append(out, NiceAction{PID: p.PID, NewNice: 10})
			t.throttled[p.PID] = true
			log.Printf("brain: throttle pid=%d (%s) cpu=%.1f%%", p.PID, p.Name, p.CPUPct)
		} else if !busy && t.throttled[p.PID] && p.NiceVal >= 10 {
			out = append(out, NiceAction{PID: p.PID, NewNice: 0})
			delete(t.throttled, p.PID)
			log.Printf("brain: unthrottle pid=%d (%s)", p.PID, p.Name)
		}
	}
	return
}

// ── MemoryPressure ────────────────────────────────────────────────────────────
// Above 80% RAM usage: raises OOM scores for large non-critical processes
// so the kernel kills them first. Also increases swappiness.

type MemoryPressure struct {
	protected map[string]bool
}

func newMemoryPressure() *MemoryPressure {
	return &MemoryPressure{protected: make(map[string]bool)}
}

func (mp *MemoryPressure) Name() string { return "memory-pressure" }

func (mp *MemoryPressure) Tick(s SystemState) (out []Action) {
	if s.RAMPressure < 0.80 {
		// Restore default swappiness when pressure eases.
		out = append(out, SwappinessAction{Value: 60})
		return
	}

	out = append(out, SwappinessAction{Value: 80})

	// Flag large non-critical procs for preferential OOM killing.
	for _, p := range s.Procs {
		if p.PID <= 1 || mp.protected[p.Name] || isKernelThread(p.Name) {
			continue
		}
		if p.RSSMB > 150 && p.OOMAdj < 200 {
			out = append(out, OOMAction{PID: p.PID, Score: 200})
		}
	}
	return
}

// ── PowerSaver ────────────────────────────────────────────────────────────────
// When battery is below 15% and not charging, raises nice values of all
// non-critical processes to 15 to reduce CPU load and extend runtime.

type PowerSaver struct {
	protected map[string]bool
	active    bool
}

func newPowerSaver(names []string) *PowerSaver {
	m := make(map[string]bool, len(names))
	for _, n := range names {
		m[n] = true
	}
	return &PowerSaver{protected: m}
}

func (ps *PowerSaver) Name() string { return "power-saver" }

func (ps *PowerSaver) Tick(s SystemState) (out []Action) {
	low := s.Battery.Present && !s.Battery.Charging && s.Battery.Percent < 15

	if low && !ps.active {
		log.Printf("brain: battery %d%% — entering power-save", s.Battery.Percent)
		ps.active = true
	} else if !low && ps.active {
		log.Printf("brain: battery %d%% — leaving power-save", s.Battery.Percent)
		ps.active = false
	}

	if !ps.active {
		return
	}

	for _, p := range s.Procs {
		if p.PID <= 1 || ps.protected[p.Name] || isKernelThread(p.Name) {
			continue
		}
		if p.NiceVal < 15 {
			out = append(out, NiceAction{PID: p.PID, NewNice: 15})
		}
	}
	return
}

// ── helpers ───────────────────────────────────────────────────────────────────

// isKernelThread returns true for processes whose names start with 'k' and
// contain only lowercase letters — a heuristic for kernel worker threads
// (kworker, kswapd, ksoftirqd …). We skip them because:
//   - nice changes have no effect on kernel threads
//   - they're already protected by the kernel scheduler
func isKernelThread(name string) bool {
	if len(name) < 2 || name[0] != 'k' {
		return false
	}
	return !strings.ContainsAny(name, "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
}
