package brain

import (
	"bufio"
	"encoding/json"
	"fmt"
	"log"
	"net"
	"os"
	"sort"
	"strings"
)

// Socket exposes a UNIX domain socket at cfg.SocketPath.
//
// Protocol: line-oriented text. Send a command, receive a JSON response.
// This is the integration point for the future voice command pipeline:
//   whisper.cpp → transcript → write to socket → brain acts.
//
// Commands:
//
//	ping             → "pong"
//	status           → JSON object with system-wide resource summary
//	procs            → JSON array of top processes (cpu>0.1% or rss>10MB)
type Socket struct {
	ln  net.Listener
	mgr *Manager
}

func newSocket(path string, mgr *Manager) (*Socket, error) {
	_ = os.Remove(path)
	ln, err := net.Listen("unix", path)
	if err != nil {
		return nil, err
	}
	if err := os.Chmod(path, 0o660); err != nil {
		ln.Close()
		return nil, err
	}
	s := &Socket{ln: ln, mgr: mgr}
	go s.serve()
	return s, nil
}

func (s *Socket) Close() { _ = s.ln.Close() }

func (s *Socket) serve() {
	for {
		conn, err := s.ln.Accept()
		if err != nil {
			return
		}
		go s.handle(conn)
	}
}

func (s *Socket) handle(conn net.Conn) {
	defer conn.Close()
	sc := bufio.NewScanner(conn)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" {
			continue
		}
		resp := s.dispatch(line)
		fmt.Fprintln(conn, resp)
	}
}

func (s *Socket) dispatch(cmd string) string {
	parts := strings.Fields(cmd)
	if len(parts) == 0 {
		return `{"error":"empty command"}`
	}

	switch parts[0] {

	case "ping":
		return `"pong"`

	case "status":
		st := s.mgr.State()
		b, _ := json.Marshal(map[string]any{
			"cpu_pct":      st.CPUPercent,
			"ram_total_mb": st.RAMTotalMB,
			"ram_used_mb":  st.RAMUsedMB,
			"ram_pressure": st.RAMPressure,
			"battery_pct":  st.Battery.Percent,
			"charging":     st.Battery.Charging,
			"proc_count":   len(st.Procs),
			"ts":           st.Timestamp.Unix(),
		})
		return string(b)

	case "procs":
		st := s.mgr.State()
		type pout struct {
			PID  int     `json:"pid"`
			Name string  `json:"name"`
			CPU  float64 `json:"cpu_pct"`
			RSS  uint64  `json:"rss_mb"`
			Nice int     `json:"nice"`
		}
		var out []pout
		for _, p := range st.Procs {
			if p.CPUPct > 0.1 || p.RSSMB > 10 {
				out = append(out, pout{p.PID, p.Name, p.CPUPct, p.RSSMB, p.NiceVal})
			}
		}
		sort.Slice(out, func(i, j int) bool { return out[i].CPU > out[j].CPU })
		if len(out) > 20 {
			out = out[:20]
		}
		b, _ := json.Marshal(out)
		return string(b)

	default:
		log.Printf("brain: unknown socket command %q", parts[0])
		return fmt.Sprintf(`{"error":"unknown command %q"}`, parts[0])
	}
}
