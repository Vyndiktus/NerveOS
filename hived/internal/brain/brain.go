// Package brain is NerveOS's lightweight resource intelligence layer.
// It samples system state every second, runs registered plugins to decide
// what actions to take, and applies them. New capabilities (voice commands,
// hive-level scheduling, etc.) are added by implementing the Plugin interface.
package brain

import (
	"log"
	"time"
)

// Plugin is the extension point. Implement this to add new brain capabilities.
type Plugin interface {
	Name() string
	// Tick is called every second with a fresh system snapshot.
	// Return zero or more Actions to apply this tick.
	Tick(state SystemState) []Action
}

// Config controls the brain manager. All fields have sane defaults.
type Config struct {
	// How often to sample and act (milliseconds). Default: 1000.
	TickMs int `toml:"tick_ms"`
	// UNIX socket path for external commands. Default: /var/run/brain.sock.
	SocketPath string `toml:"socket_path"`
	// Process names that must never be throttled or OOM-killed.
	Protected []string `toml:"protected_procs"`
}

// Manager runs the brain: sample → plugins → actuate, every tick.
type Manager struct {
	cfg     Config
	plugins []Plugin
	mon     *Monitor
	act     *Actuator
	sock    *Socket
	stop    chan struct{}
}

func New(cfg Config) (*Manager, error) {
	if cfg.TickMs <= 0 {
		cfg.TickMs = 1000
	}
	if cfg.SocketPath == "" {
		cfg.SocketPath = "/var/run/brain.sock"
	}
	if len(cfg.Protected) == 0 {
		cfg.Protected = []string{
			"hived", "init", "bluetoothd", "dbus-daemon", "sshd",
		}
	}

	mon := newMonitor()
	act := newActuator()

	m := &Manager{
		cfg:  cfg,
		mon:  mon,
		act:  act,
		stop: make(chan struct{}),
	}

	// Built-in plugins — registered in priority order.
	m.Register(newResourceGuard(cfg.Protected))
	m.Register(newIdleThrottler(cfg.Protected))
	m.Register(newMemoryPressure())
	m.Register(newPowerSaver(cfg.Protected))

	return m, nil
}

// Register adds a plugin. Call before Start.
func (m *Manager) Register(p Plugin) {
	m.plugins = append(m.plugins, p)
}

func (m *Manager) Start() error {
	// Prime the monitor so the first tick has a baseline for CPU deltas.
	m.mon.sample()

	sock, err := newSocket(m.cfg.SocketPath, m)
	if err != nil {
		log.Printf("brain: socket unavailable (%v) — continuing without it", err)
	} else {
		m.sock = sock
	}

	go m.run()
	log.Printf("brain: started — plugins=%d tick=%dms socket=%s",
		len(m.plugins), m.cfg.TickMs, m.cfg.SocketPath)
	return nil
}

func (m *Manager) Stop() {
	close(m.stop)
	if m.sock != nil {
		m.sock.Close()
	}
	log.Println("brain: stopped")
}

// State returns the most recent system snapshot (non-blocking).
func (m *Manager) State() SystemState {
	return m.mon.current()
}

func (m *Manager) run() {
	ticker := time.NewTicker(time.Duration(m.cfg.TickMs) * time.Millisecond)
	defer ticker.Stop()
	for {
		select {
		case <-m.stop:
			return
		case <-ticker.C:
			m.tick()
		}
	}
}

func (m *Manager) tick() {
	state := m.mon.sample()

	var actions []Action
	for _, p := range m.plugins {
		actions = append(actions, p.Tick(state)...)
	}
	for _, a := range actions {
		if err := m.act.Apply(a); err != nil {
			log.Printf("brain: %s: %v", a, err)
		}
	}
}
