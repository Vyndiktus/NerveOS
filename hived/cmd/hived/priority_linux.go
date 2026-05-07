//go:build linux

package main

import (
	"log"
	"os"
	"syscall"
)

func init() {
	// Raise our own scheduling priority before anything else starts.
	// nice=-10 puts hived above all normal user processes (which start at 0)
	// while leaving room for true real-time tasks like audio and the kernel.
	if err := syscall.Setpriority(syscall.PRIO_PROCESS, 0, -10); err != nil {
		log.Printf("hived: could not set nice=-10: %v", err)
	}
	// Protect ourselves from OOM kills — hived must survive memory pressure.
	if err := os.WriteFile("/proc/self/oom_score_adj", []byte("-900\n"), 0o644); err != nil {
		log.Printf("hived: could not set oom_score_adj: %v", err)
	}
}
