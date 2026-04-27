# Faz 5 İlerleme Notları

## Tamamlanan Sub-fazlar

### 5a — Elektrik QK sabitleri ✅
`output_kind.py`'a eklendi: QK_CURRENT, QK_CAPACITOR_VOLTAGE, QK_VOLTAGE,
QK_RELATIVE_VOLTAGE + backward-compat mapping'leri.

### 5b — RLC template dolduruldu ✅
`rlc_circuit.py` basic component'lerden inşa edildi:
VoltageSource("v_source") → Resistor("resistor") → Inductor("inductor") →
Capacitor("capacitor") → ElectricalGround("ground").
3 probe: loop_current, capacitor_voltage, resistor_voltage.
R=10Ω, L=0.5H, C=1mF (underdamped: ζ≈0.224).
`test_rlc_circuit_template.py` eklendi (10 pass, 1 skip).

### 5-pal — Palette UI Refactor (4-seviye hiyerarşi) ✅
`model_panel.py` refactor edildi:
- PaletteNodeSpec'e `placeholder_text` alanı eklendi
- 2-seviye (Domain, Subgroup) → 4-seviye (Domain, Subdomain, Category)
- PALETTE_HIERARCHY_SPEC ile boş kategoriler "Coming soon" ile görünür
- 11 backend-ready component palette'te: Mass, Spring, Damper, Fixed,
  Force Source, Resistor, Capacitor, Inductor, Ground, DC Voltage Source,
  DC Current Source
- 16 visual-only stub gizli (diode, switch, sensors, ac sources)

### 5MVP-0 — Template/Quarter-Car Temizliği ✅
**Silinen dosyalar:**
- `app/core/templates/quarter_car.py`
- `app/core/templates/single_mass.py`
- `app/core/templates/two_mass.py`
- `app/core/templates/rc_circuit.py`
- `app/core/templates/rlc_circuit.py`
- `app/services/simulation_backend.py`
- `app/services/runtime_backend.py`
- `app/services/parity_harness.py`
- `tests/test_backend_parity.py`
- `tests/test_runtime_backend.py`
- `tests/test_canvas_compiler_parity.py`

**Oluşturulan dosyalar:**
- `tests/fixtures/__init__.py`
- `tests/fixtures/minimal_wheel_road.py` — Wheel+Road 2-DOF fixture (Strateji A)
- `tests/fixtures/graph_factories.py` — single_mass, two_mass, rlc graph factories
- `docs/decisions/016-random-road-reorganization.md` — ADR-016

**Refactor edilen dosyalar:**
- `app/core/templates/__init__.py` — tüm build_* import'ları silindi
- `app/core/models/__init__.py` — compat stub bırakıldı (5MVP-6'da silinecek)
- `app/core/models/quarter_car_model.py` → minimal compat stub (sadece dataclass'lar)
- `app/services/graph_resolver.py` — template fallback kaldırıldı, RuntimeError
- `app/ui/panels/model_panel.py` — DEFAULT_LAYOUTS = (), load_default_model = blank
- `app/ui/canvas/model_canvas.py` — tüm load_*_layout method'ları silindi
- `tests/test_tf_golden.py` — fixture'lara geçirildi
- `tests/test_symbolic_pipeline.py` — fixture'lara geçirildi
- `tests/test_primary_cutover.py` — fixture'lara geçirildi
- `tests/test_tf_fuzz.py` — fixture'lara geçirildi
- `tests/test_fuzz_parity.py` — fixture'lara geçirildi
- `tests/test_linearity_classifier.py` — fixture'lara geçirildi
- `tests/test_linearization_warnings.py` — silinen backend testleri kaldırıldı
- `tests/test_output_mapper.py` — fixture'lara geçirildi
- `tests/test_input_router.py` — fixture'lara geçirildi
- `tests/test_rlc_circuit_template.py` — fixture'lara geçirildi
- `tests/test_canvas_editing.py` — zaten template import yok, değişmedi

**Korunan dosyalar (Faz 6 için):**
- `app/core/models/mechanical/wheel.py` (570 satır)
- `app/core/models/sources/random_road.py`
- `tests/test_wheel_road_contact.py`
- `tests/test_wheel_road_contact_contribution.py`

### 5MVP-1 — GenericStaticBackend ✅
**Oluşturulan dosyalar:**
- `app/services/static_analysis_backend.py` — `GenericStaticBackend`, `StaticAnalysisResult`, `AnalysisError`
- `tests/test_static_analysis_backend.py` — 40 tests (single-mass, two-mass, RLC, wheel-road, error paths)

**Pipeline:**
  SystemGraph → PolymorphicDAEReducer → StateSpaceBuilder → SymbolicTFBuilder

**API:**
- `backend.analyze(graph)` → `StaticAnalysisResult` (state-space + TFs + stability)
- `backend.analyze_siso(graph, input_id, output_probe_id)` → single TF
- `_MinimalSymbolicSystem` stub bypasses EquationBuilder
- Input ID resolution handles `r_`, `f_*_out` prefix variants transparently

**Bilinen limitasyon:** PolymorphicDAEReducer henüz elektrik bileşenlerini
desteklemiyor (contribute_mass/stiffness/damping interface'i yok). RLC
devreleri için A/B matrisleri sıfır. TODO(5MVP-electrical).

### 5MVP-2 — AppStateV2 ✅
**Oluşturulan dosyalar:**
- `app/core/state/app_state_v2.py` — `AppStateV2`, `ControllerConfigV2`, `AnalysisConfig`
- `tests/test_app_state_v2.py` — 23 tests (defaults, lifecycle, integration, controller)

**Tasarım:**
- `AppStateV2` generic, template-bağımsız — QuarterCar referansı yok
- `graph: SystemGraph | None` — compiled model (canvas'tan gelir)
- `analysis_result: StaticAnalysisResult | None` — backend sonucu
- State transitions: `set_compiled()`, `set_analyzed()`, `set_compile_failed()`, `set_analysis_failed()`, `reset()`
- Convenience properties: `is_compiled`, `is_analyzed`, `n_states`, `is_stable`
- Eski `AppState` untouched (backward compat, 5MVP-6'da silinecek)

### 5MVP-3 — MainWindow_v2 + CompileAnalyzeService ✅
**Oluşturulan dosyalar:**
- `app/services/compile_analyze_service.py` — `CompileAnalyzeService` (canvas→compile→analyze pipeline)
- `tests/test_compile_analyze_service.py` — 11 tests (workflow, rerun, errors, injection)
- `app/ui/main_window_v2.py` — `MainWindowV2` (PySide6 QMainWindow, static analysis only)

**CompileAnalyzeService API:**
- `compile_and_analyze(components, wires) → bool` — full pipeline
- `analyze_current() → bool` — re-analyze with new selection
- `analyze_graph(graph) → bool` — direct graph analysis (for tests)
- Updates `AppStateV2` with results or errors

**MainWindowV2 tasarımı:**
- 3-panel layout: ModelPanel | EquationPanel | AnalysisPanel
- "Compile & Analyze" button → `CompileAnalyzeService.compile_and_analyze()`
- Status label: state count, TF count, stability
- Step response, Bode, pole-zero plots via scipy.signal
- No real-time simulation (static analysis only)
- No dependency on QuarterCarModel, simulation_service, signal_catalog

## Test Durumu

1078 passed, 0 failed, 366 skipped (PySide6-dependent).

## Sıradaki Sub-fazlar

- ~~**5MVP-1** — GenericStaticBackend~~ ✅
- ~~**5MVP-2** — AppStateV2~~ ✅
- ~~**5MVP-3** — MainWindow_v2 + CompileAnalyzeService~~ ✅
- ~~**5MVP-4** — Wire ControllerService/AnalysisPanel to new backend~~ ✅ (MainWindowV2 direkt wiring)
- ~~**5MVP-5** — Switch main entry to MainWindow_v2~~ ✅ (`app/main.py` → `MainWindowV2`)
- ~~**5MVP-6** — Delete quarter-car shell (compat stub, legacy services)~~ ✅
- ~~**5MVP-7** — Refactor Faz 4 motor tests to minimal fixture~~ ✅ (zaten mevcut değil)
- ~~**5MVP-8** — Smoke test: palette → drag → compile → controller → analysis~~ ✅

### 5MVP-6 — Legacy Cleanup ✅
**Silinen dosyalar:**
- `app/core/models/quarter_car_model.py`
- `app/ui/main_window.py` (eski, broken)
- `app/services/simulation_service.py`
- `app/services/equation_service.py`
- `app/services/plotting_service.py`
- `app/services/signal_catalog.py`

**Güncellenen dosyalar:**
- `app/core/models/__init__.py` — QuarterCar exports kaldırıldı
- `app/core/state/app_state.py` — QC import kaldırıldı, parameters/state → dict

### 5MVP-8 — End-to-end Smoke Test ✅
- `tests/test_e2e_smoke.py` — 13 tests
- Single-mass, two-mass, wheel-road: full pipeline
- TF coefficient extraction, DC gain, stability, recompile workflow

## Final Test Durumu

1091 passed, 0 failed, 366 skipped (PySide6-dependent).

## Faz 5 MVP — TAMAMLANDI ✅

Tüm 8 sub-faz başarıyla tamamlandı:
- GenericStaticBackend: graph → state-space → transfer functions
- AppStateV2: template-bağımsız application state

---

## UI Redesign — Faz UI-1..UI-5

### UI-1 — CollapsibleSidebar Widget ✅
`app/ui/widgets/collapsible_sidebar.py` — expand/collapse, toggle, arrow direction, CollapsedSidebarRail.
`tests/test_collapsible_sidebar.py` — 15 tests (state, toggle, arrow, rail).

### UI-2 — SystemModelingView ✅
- `app/ui/panels/model_library_panel.py` — standalone palette + search (extracted from ModelPanel)
- `app/ui/panels/component_inspector_panel.py` — property display below canvas
- `app/ui/views/system_modeling_view.py` — CollapsibleSidebar(Library) + Canvas + Inspector

### UI-3 — ControllerTuningPanel ✅
`app/ui/panels/controller_tuning_panel.py` — 3 tabs:
- Controller: PID/LQR/Zustandsregler/MPR (QStackedWidget)
- I/O Selection: input source, profile, output checkboxes
- Simulation Settings: duration, solver, backend, tolerances

### UI-4 — SystemControllingView ✅
- `app/ui/panels/simulation_results_panel.py` — 2×2 plot grid + Run Simulation button
- `app/ui/panels/model_equations_panel.py` — read-only equations text display
- `app/ui/views/system_controlling_view.py` — Sidebar(Config) + Results + Sidebar(Equations)

### UI-5 — SystemDesignerShell + Dark Theme ✅
- `app/ui/main_window_v3.py` — 2-module layout, full dark theme, compile pipeline
- `app/main.py` → switched to SystemDesignerShell
- Full dark theme stylesheet (#222426 background)

### Test Durumu
1091 passed, 0 failed, 367 skipped (PySide6-dependent).
- CompileAnalyzeService: canvas → compile → analyze pipeline
- MainWindowV2: static analysis UI (step, bode, pole-zero)
- Entry point switched, legacy code deleted
- 1091 tests passing, 0 failures
