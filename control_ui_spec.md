# Control System Builder UI Specification (PyQt First, Web-Ready)

Build a desktop engineering application inspired by MATLAB/Simscape where the user creates electrical and mechanical systems by placing and connecting reusable components.

## Main Goals
- First implementation: Python + PySide6 / PyQt6
- Future target: FastAPI backend + React/Vue frontend
- UI and simulation engine must remain completely separate

## Main Capabilities
- Drag-and-drop component library
- Mechanical and electrical component connections
- Dynamic simulation
- Controller selection (PID, State Space, LQR)
- Analysis plots (step, bode, root locus, nyquist, pole-zero)
- Future save/load and web compatibility

## Component Categories
### Mechanical
- Mass
- Translational Spring
- Translational Damper
- Gear Box
- Slider-Crank
- Wheel
- Suspension Link
- Ground

### Electrical
- Resistor
- Capacitor
- Inductor
- Diode
- DC Voltage Source
- AC Voltage Source
- Voltage Sensor
- Current Sensor

### Control
- PID
- State Space Controller
- LQR
- Gain
- Sum
- Saturation
- Disturbance Input

## UI Layout
### Left Side
- Component library
- Draggable model canvas
- Selected component properties

### Right Side
- Differential equation panel
- Transfer function panel
- Time response plot
- Controller configuration
- Pole-zero map
- Root locus
- Bode diagram
- Nyquist diagram

## Canvas Requirements
- Drag and drop components
- Zoom and pan
- Rotate components
- Highlight selected component
- Visible ports and wires
- Only compatible ports can connect

## Component Data Structure
```python
class Component:
    id: str
    type: str
    domain: str
    position: tuple
    rotation: int
    parameters: dict
    ports: list
```

## Architecture
```text
PyQt UI
   -> AppState
   -> Simulation Service
   -> Physics / Control Engine
```

The core engine returns plain arrays and dictionaries so that later the same backend can power a web frontend.

Example:
```python
{
    'time': [...],
    'displacement': [...],
    'velocity': [...]
}
```

## Quarter-Car Suspension Requirement
Include an example model for a quarter-car suspension:
- body mass
- wheel mass
- suspension spring
- suspension damper
- tire stiffness
- random road profile input

The road input should be configurable:
- amplitude
- roughness
- frequency content
- seed
- duration

Outputs:
- body displacement
- wheel displacement
- suspension travel
- body acceleration

## Recommended Libraries
- PySide6
- NumPy
- SciPy
- python-control
- matplotlib
- networkx
- sympy

## Responsive / Dynamic Resizing Requirement
The PyQt user interface must resize gracefully when the user changes the window size.

Requirements:
- All major panels must expand and shrink proportionally
- No overlapping widgets
- No broken layouts
- No clipped controls or charts
- The canvas should scale with available space
- Plot areas should resize automatically with their parent containers
- Side panels should preserve usability at smaller sizes
- Text, buttons, inputs, and plot widgets must remain aligned
- The interface must stay visually stable and professional during resize events

Implementation expectations:
- Use layout managers, not fixed absolute positioning
- Prefer nested `QHBoxLayout`, `QVBoxLayout`, `QGridLayout`, and splitters where appropriate
- Use size policies correctly (`Expanding`, `Preferred`, `Minimum`)
- Define sensible minimum sizes for critical panels
- The canvas and charts should receive most of the extra space when the window grows
- The UI should keep its structure intact across common desktop resolutions

The goal is that when the main window is resized, the full interface reorganizes cleanly without visual distortion.

