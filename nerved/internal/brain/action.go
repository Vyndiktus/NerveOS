package brain

// Action is an operation the brain wants to perform on the system.
// Plugins return slices of Actions from Tick; the Actuator applies them.
type Action interface {
	Apply() error
	String() string
}
