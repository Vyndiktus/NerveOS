//go:build !linux

package brain

import "fmt"

// Stubs for non-Linux platforms (dev builds on macOS/Windows).

type Actuator struct{}

func newActuator() *Actuator              { return &Actuator{} }
func (a *Actuator) Apply(act Action) error { return act.Apply() }

type NiceAction struct {
	PID     int
	NewNice int
}

func (a NiceAction) String() string { return fmt.Sprintf("nice pid=%d new=%d", a.PID, a.NewNice) }
func (a NiceAction) Apply() error   { return nil }

type OOMAction struct {
	PID   int
	Score int
}

func (a OOMAction) String() string { return fmt.Sprintf("oom pid=%d score=%d", a.PID, a.Score) }
func (a OOMAction) Apply() error   { return nil }

type SwappinessAction struct{ Value int }

func (a SwappinessAction) String() string { return fmt.Sprintf("swappiness val=%d", a.Value) }
func (a SwappinessAction) Apply() error   { return nil }
