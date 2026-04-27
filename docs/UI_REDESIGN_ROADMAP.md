# UI Redesign Roadmap

## Hedef Mimari (new_ui.xml'den)

```
SystemDesignerShell (QMainWindow)
├── QSplitter (Horizontal)
│   ├── [LEFT] System Modelling (QFrame + SystemModelingView)
│   │   ├── Module Title: "System Modelling"
│   │   └── SystemModelingView
│   │       ├── CollapsibleSidebar("Library", ModelLibraryPanel, side=left)
│   │       └── [CENTER] BlockDiagramWorkspace
│   │           ├── Toolbar (component count, clear button)
│   │           ├── Canvas (grid background, drag-drop)
│   │           └── ComponentInspectorPanel (bottom, property editor)
│   │
│   └── [RIGHT] System Controlling (QFrame + SystemControllingView)
│       ├── Module Title: "System Controlling"
│       └── SystemControllingView
│           ├── CollapsibleSidebar("Configuration", ControllerTuningPanel, side=left)
│           ├── [CENTER] SimulationResultsPanel
│           │   ├── Header: "Results and Analysis"
│           │   ├── 2×2 Grid: Time Response | Step Response | Bode | Pole-Zero
│           │   └── "Run Simulation" button (bottom)
│           └── CollapsibleSidebar("Model Equations", ModelEquationsPanel, side=right)
```

## Mevcut Durum vs Hedef — Karşılaştırma

| Özellik | Mevcut (MainWindowV2) | Hedef (SystemDesignerShell) |
|---------|----------------------|---------------------------|
| Ana layout | 3-sütun splitter | 2-modül splitter |
| Palette/Library | ModelPanel içinde sabit | CollapsibleSidebar (sol) |
| Canvas | ModelPanel içinde | BlockDiagramWorkspace (ayrı) |
| Property Editor | Yok | ComponentInspectorPanel (canvas altı) |
| Controller | controller_panel.py (legacy) | ControllerTuningPanel (PID/LQR/Zustandsregler/MPR) |
| I/O Selection | model_canvas.py sağ-tık | Dedicated tab (ControllerTuningPanel) |
| Sim Settings | Yok | Dedicated tab (Duration, Solver, Backend, Tolerances) |
| Equations | EquationPanel (sabit sütun) | CollapsibleSidebar (sağ, varsayılan kapalı) |
| Results | AnalysisPanel (sabit sütun) | SimulationResultsPanel (merkez) |
| Simulation Button | "Compile & Analyze" (toolbar) | "Run Simulation" (results panel altı) |
| Theme | Açık/karışık | Tam dark theme (#222426) |
| Collapsible panels | Yok | CollapsibleSidebar (shared widget) |

## Implementasyon Fazları

---

### Faz UI-1 — CollapsibleSidebar Widget (shared component)

**Dosya:** `app/ui/widgets/collapsible_sidebar.py`

**Açıklama:** Hedef tasarımda 3 yerde kullanılan ortak widget: Library (sol), Configuration (sol), Model Equations (sağ). Expand/collapse animasyonu, pin/unpin, hover-reveal.

**Alt görevler:**
- UI-1a: `CollapsibleSidebar(title, content_widget, side="left"|"right", expanded=True)` sınıfı
- UI-1b: Expanded state: header (title + toggle button) + content area
- UI-1c: Collapsed state: dar rail (ikon/etiket) → hover ile drawer açılır
- UI-1d: Pin button: drawer'ı kalıcı expand eder
- UI-1e: Unit test (expand/collapse state toggle, pin logic)

**Referans:** `src/shared/components/collapsible_sidebar.py` (new_ui.xml'deki implementasyon)

**Tahmini efor:** 1 oturum

---

### Faz UI-2 — System Modeling View

**Dosyalar:**
- `app/ui/views/system_modeling_view.py` (YENİ)
- `app/ui/panels/model_library_panel.py` (YENİ — mevcut ModelPanel'den extract)
- `app/ui/panels/component_inspector_panel.py` (YENİ)

**Açıklama:** Sol modülü oluşturur. Mevcut `ModelPanel`'i parçalar: library tree ayrı bir panel olur (CollapsibleSidebar içinde), canvas BlockDiagramWorkspace olarak ortada kalır, altta ComponentInspectorPanel eklenir.

**Alt görevler:**
- UI-2a: `ModelLibraryPanel` — mevcut ModelPanel'deki palette tree'yi extract et
  - Search box
  - 4-seviye hiyerarşi (zaten var: Domain > Subdomain > Category > Component)
  - Drag-and-drop desteği (zaten var)
- UI-2b: `ComponentInspectorPanel` — seçili component'in properties'ini gösterir
  - Component adı, type, parameter değerleri
  - Düzenlenebilir parametreler (QDoubleSpinBox)
  - Canvas'taki seçim sinyaline bağlanır
- UI-2c: `SystemModelingView` — composition widget
  - CollapsibleSidebar("Library", ModelLibraryPanel, side="left", expanded=True)
  - Center: mevcut canvas (model_canvas.py) + ComponentInspectorPanel (alt)
- UI-2d: Workspace toolbar (component sayısı, clear button)
- UI-2e: Testler (panel oluşturma, signal bağlantıları)

**Bağımlılık:** UI-1 (CollapsibleSidebar)

**Mevcut koddan yeniden kullanılacaklar:**
- `model_canvas.py` (1954 satır) — olduğu gibi kalır
- `ModelPanel`'deki palette ağacı → `ModelLibraryPanel`'e taşınır
- I/O role atama (sağ-tık menü) — canvas'ta kalır

**Tahmini efor:** 1-2 oturum

---

### Faz UI-3 — Controller Tuning Panel

**Dosya:** `app/ui/panels/controller_tuning_panel.py` (YENİ)

**Açıklama:** Mevcut `controller_panel.py`'ı tamamen yeniden yazar. QTabWidget ile 3 sekme: Controller, I/O Selection, Simulation Settings.

**Alt görevler:**
- UI-3a: Controller tab
  - QComboBox: PID | LQR | Zustandsregler | MPR
  - QStackedWidget: her controller tipi için parametre formu
  - PID: Enable, Kp, Ki, Kd, Output limit
  - LQR: State weights q1/q2, Control weight r, Integral action
  - Zustandsregler: K1, K2, K3, Observer gains L1, L2
  - MPR: Prediction/Control horizon, Tracking/Effort weights, Input constraint
- UI-3b: I/O Selection tab
  - Input source: ComboBox (workspace'ten dinamik)
  - Input profile: Step | Sine | Ramp | Impulse | Custom
  - Output checkboxes: position, velocity, acceleration, control effort, error signal
- UI-3c: Simulation Settings tab
  - Duration, Sample time (QDoubleSpinBox)
  - Solver: RK45 | RK23 | DOP853 | BDF | Radau
  - Backend: Numeric | State space | Transfer function
  - Tolerances: rtol, atol
- UI-3d: Signal wiring — AppStateV2 ile entegrasyon
  - Controller parametreleri → ControllerConfigV2'ye yansıtılır
  - I/O seçimi → AnalysisConfig'e yansıtılır
- UI-3e: Testler

**Referans:** `src/features/ControllerDesignModule/panels/ControllerTuningPanel/controller_tuning_panel.py`

**Tahmini efor:** 1-2 oturum

---

### Faz UI-4 — System Controlling View

**Dosyalar:**
- `app/ui/views/system_controlling_view.py` (YENİ)
- `app/ui/panels/simulation_results_panel.py` (YENİ — mevcut AnalysisPanel'den evolve)
- `app/ui/panels/model_equations_panel.py` (YENİ — mevcut EquationPanel'den evolve)

**Açıklama:** Sağ modülü oluşturur. 3 collapsible sidebar ile merkezi results paneli.

**Alt görevler:**
- UI-4a: `SimulationResultsPanel` — mevcut AnalysisPanel'i refactor et
  - Header: "Results and Analysis"
  - 2×2 matplotlib grid (zaten var, taşınacak)
  - "Run Simulation" button (altta)
  - Button → CompileAnalyzeService.compile_and_analyze() tetikler
- UI-4b: `ModelEquationsPanel` — mevcut EquationPanel'den evolve
  - QPlainTextEdit (read-only)
  - State-space, TF, governing equations gösterimi
- UI-4c: `SystemControllingView` — composition widget
  - CollapsibleSidebar("Configuration", ControllerTuningPanel, side="left", expanded=True)
  - Center: SimulationResultsPanel
  - CollapsibleSidebar("Model Equations", ModelEquationsPanel, side="right", expanded=False)
- UI-4d: Signal flow: Run Simulation → compile → analyze → update plots + equations
- UI-4e: Testler

**Bağımlılık:** UI-1 (CollapsibleSidebar), UI-3 (ControllerTuningPanel)

**Tahmini efor:** 1-2 oturum

---

### Faz UI-5 — SystemDesignerShell + Dark Theme

**Dosyalar:**
- `app/ui/main_window_v3.py` (YENİ) veya mevcut `main_window_v2.py`'ı refactor
- `app/main.py` (entry point güncelle)

**Açıklama:** Ana pencere. 2-modül frame (System Modelling | System Controlling) + full dark theme.

**Alt görevler:**
- UI-5a: `SystemDesignerShell(QMainWindow)`
  - QSplitter(Horizontal): SystemModelingView | SystemControllingView
  - build_module_frame() helper: başlık + content'i frame'e sarar
  - Boyut: 1800×980, splitter oranları: 38% / 62%
- UI-5b: Dark theme stylesheet
  - App background: #222426
  - Panel background: #2f3133 / #343638
  - Text: #f5f7f8
  - Borders: #5a5d60
  - Accent: #2f6fb3 (buttons)
  - Full QSS (new_ui.xml'deki APP_STYLESHEET'ten)
- UI-5c: Entry point switch: `app/main.py` → SystemDesignerShell
- UI-5d: Smoke test: pencere açılır, modüller görünür, compile çalışır
- UI-5e: Testler

**Bağımlılık:** UI-2, UI-4

**Tahmini efor:** 1 oturum

---

### Faz UI-6 — Legacy Cleanup

**Silinecek dosyalar:**
- `app/ui/main_window_v2.py` (eski shell)
- `app/ui/panels/controller_panel.py` (legacy, try/except stubs)
- `app/ui/panels/output_panel.py` (kullanılmıyor)

**Güncellenecek dosyalar:**
- `app/ui/panels/__init__.py` — export'ları güncelle
- İlgili import'lar temizle

**Tahmini efor:** 0.5 oturum

---

## Dosya Haritası (Mevcut → Hedef)

```
MEVCUT                              HEDEF
─────────────────────────           ─────────────────────────
app/ui/main_window_v2.py       →   SİLİNİR (UI-6)
app/ui/panels/model_panel.py   →   PARÇALANIR:
                                      → app/ui/panels/model_library_panel.py (UI-2a)
                                      → canvas model_canvas.py'da kalır
app/ui/panels/equation_panel.py →   EVOLVE → app/ui/panels/model_equations_panel.py (UI-4b)
app/ui/panels/analysis_panel.py →   EVOLVE → app/ui/panels/simulation_results_panel.py (UI-4a)
app/ui/panels/controller_panel.py → YENİDEN YAZILIR → controller_tuning_panel.py (UI-3)
app/ui/panels/output_panel.py  →   SİLİNİR (UI-6)

YENİ DOSYALAR:
app/ui/widgets/collapsible_sidebar.py        (UI-1)
app/ui/views/system_modeling_view.py         (UI-2)
app/ui/views/system_controlling_view.py      (UI-4)
app/ui/panels/model_library_panel.py         (UI-2a)
app/ui/panels/component_inspector_panel.py   (UI-2b)
app/ui/panels/controller_tuning_panel.py     (UI-3)
app/ui/panels/simulation_results_panel.py    (UI-4a)
app/ui/panels/model_equations_panel.py       (UI-4b)
app/ui/main_window_v3.py                     (UI-5)
```

## Kritik Tasarım Kararları

1. **model_canvas.py dokunulmaz** — 1954 satırlık QPainter canvas olduğu gibi kalır. Sadece parent widget değişir (ModelPanel → BlockDiagramWorkspace bölgesi).

2. **Backend pipeline korunur** — CompileAnalyzeService, GenericStaticBackend, AppStateV2 değişmez. Sadece UI katmanı yeniden yapılandırılır.

3. **Incremental migration** — Her faz bağımsız test edilebilir. Faz UI-5'e kadar MainWindowV2 çalışmaya devam eder.

4. **CollapsibleSidebar = key widget** — 3 farklı yerde kullanılacak, önce bunu yazmak gerekir.

5. **Dark theme son fazda** — QSS stylesheet tek noktada uygulanır, erken fazlarda varsayılan tema kullanılır.

## Bağımlılık Grafiği

```
UI-1 (CollapsibleSidebar)
 ├── UI-2 (System Modeling View)
 │    └── UI-5 (Shell + Theme)
 └── UI-3 (Controller Tuning)
      └── UI-4 (System Controlling View)
           └── UI-5 (Shell + Theme)
                └── UI-6 (Legacy Cleanup)
```

## Toplam Tahmini Efor

| Faz | Efor |
|-----|------|
| UI-1 | 1 oturum |
| UI-2 | 1-2 oturum |
| UI-3 | 1-2 oturum |
| UI-4 | 1-2 oturum |
| UI-5 | 1 oturum |
| UI-6 | 0.5 oturum |
| **Toplam** | **5.5-8.5 oturum** |
