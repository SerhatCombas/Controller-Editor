# System Modeling — Library Gelistirme Yol Haritasi

> Bu dosya System Modeling tarafinin (Layer 2, sol kanat) library altyapisini
> MSL'den ogrendigimiz pattern'lerle nasil gelistirecegimizi takip eder.
> Her task basladiginda `[ ]` → `[x]` olarak guncellenir.
>
> **Kaynak oncelik sirasi:** MSL analizi > mevcut calisankod > requirement dokumanlar
>
> **Temel prensip:** Mevcut calisan pipeline (quarter-car, single-mass) BOZULMAYACAK.
> Yeni altyapi yanina eklenir, eski yollar korunur, sonra tek tek gecis yapilir.

---

## Mimari Baglamn

```
Layer 1: Controller Editor App
Layer 2: System Modeling          |  Control & Analysis
Layer 3: Model Library | Workspace | Control Panel | Result Panel
```

**Veri akisi:**
```
Library Panel → Workspace (topoloji) → SystemModel (state-space/TF) → Control & Analysis
```

**System Model Contract** = `StateSpaceModel` dataclass (zaten mevcut).
Generic reducer elektrik tarafini da ayni ciktiya donustururse, Control & Analysis
hangi domain'den geldigini bilmek zorunda kalmaz.

---

## Faz 0: Cekirek Altyapi Guncellemesi

> Mevcut base/ katmanini MSL pattern'leriyle zenginlestir.
> Hicbir mevcut bilesen bozulmaz — tum degisiklikler backward-compatible.

### T0.1 — DomainSpec Registry ✅
- [x] `app/core/base/domain.py` icerisine `DomainSpec` dataclass ekle
  - `name`, `across_var`, `through_var`, `across_unit`, `through_unit`
  - `color` (connection rengi), `flange_kinds` (yon turleri)
- [x] `DOMAIN_SPECS: dict[str, DomainSpec]` registry dict'i olustur
  - `electrical`, `translational`, `rotational`, `thermal`
- [x] Mevcut `Domain` ve `MECHANICAL_TRANSLATIONAL_DOMAIN` korunur
  - `DomainSpec` icinden `to_domain() -> Domain` helper ile uyum saglenir
- [x] Birim testi: her DomainSpec'in across x through = power dogrulamasi
  - `tests/test_domain_spec.py` — 15 test, hepsi gecti
- [x] **DÜZELTME:** effort_var/flow_var/effort_unit/flow_unit/power_order eklendi
  - across/through = Modelica connector degiskenleri (s, f)
  - effort/flow = power-conjugate cift (f, v): effort × flow = W her zaman
  - power_order=0: effort≡across (elektrik), power_order=1: flow=der(across) (mekanik)
- [x] `SIGN_CONVENTION.md` yazildi — tum domain'ler icin tek referans
- [x] Helper sign convention düzeltildi:
  - Elektrik: v_diff = v_p - v_n, through = i_p (MSL OnePort)
  - Mekanik: v_diff = v_b - v_a, through = i_b (MSL PartialCompliant)

**MSL referansi:** 4 analiz dokumaninin 6.3 bolumu — domain tablosu
**Catisma notu:** Component Library Requirements "Supported Domains" ile uyumlu.
Requirement sadece "mechanical translational" ve "electrical" diyor;
DomainSpec registry gelecekteki domain'leri de kapsar (rotational, thermal, hydraulic).

### T0.2 — Port Zenginlestirmesi ✅
- [x] `Port` dataclass'ina `direction_hint: str | None = None` ekle
  - Elektrik: `'positive'` / `'negative'`
  - Mekanik: `'a'` / `'b'`
  - Varsayilan: `None` (backward compat)
- [x] `Port` dataclass'ina `visual_anchor: tuple[float, float] | None = None` ekle
  - SVG uzerindeki normalize konum (0.0-1.0)
  - Component Visual Symbol Guidelines Section 6 ile uyumlu
- [x] `is_positive` / `is_negative` property helper'lar eklendi
- [x] Mevcut Port kullanimlarini dogrula — hicbiri bozulmadi (548 test passed)
  - `tests/test_port_enrichment.py` — 12 test, hepsi gecti

**MSL referansi:** PositivePin/NegativePin ve Flange_a/Flange_b ayrimi tek Port ile
**Requirement referansi:** Component Library Requirements Section 7 — Port gereksinimleri

### T0.3 — Sympy Tabanli Denklem Altyapisi ✅
- [x] `app/core/base/equation.py` olusturuldu:
  - `SymbolicEquation` frozen dataclass: `lhs`, `rhs`, `provenance`, `residual`, `substitute()`
  - `der()` fonksiyonu: `sympy.Function('der')` wrapper
- [x] `BaseComponent`'e yeni method'lar eklendi:
  - `symbolic_equations() -> list[SymbolicEquation]` (varsayilan: bos liste)
  - `_sym(name) -> sympy.Symbol` — component-scoped, cached symbol helper
- [x] Mevcut string-based `constitutive_equations()` KORUNDU
  - Iki yol paralel: eski bilesenler string, yeni bilesenler sympy
- [x] Test: Ohm (v=R*i) + Capacitor (i=C*der(v)) testleri gecti
  - `tests/test_symbolic_equations.py` — 16 test, hepsi gecti

**MSL referansi:** msl_components_final_blueprint.md Section 3 — constitutive law = tek satir
**Catisma notu:** Mevcut sistem string denklemleri kullaniyor. Requirement dokumanlarinda
sympy zorunlulugu yok. Ancak generic reducer icin sympy gerekli.
Karar: ikisini paralel tut, yenileri sympy ile yaz.

### T0.4 — Helper Method'lar (BaseComponent'e) ✅
- [x] `add_one_port(domain, name, direction_hint)` → tek port + reference denklemi
  - Ground / Fixed icin
- [x] `add_one_port_pair(domain, prefix)` → 2 port + KCL + across_diff
  - Resistor, Spring, Damper, Capacitor, Inductor icin
  - `across_diff = port_b.across - port_a.across`
  - `0 = port_a.through + port_b.through`
  - `through = port_b.through`
- [x] `add_rigid_pair(domain, center_name, length_param)` → 2 port + center + L, KCL YOK
  - Mass icin (Newton denklemi bilesen kendi yazar)
- [x] Her helper DomainSpec registry'den domain bilgisi alir
- [x] Helper'lar sympy denklemleri uretir (T0.3'e bagimli)
- [x] Mevcut bilesenler helper kullanmak ZORUNDA DEGIL (opt-in)
  - `app/core/base/component_helpers.py` — PortSetup + 3 helper
  - `tests/test_component_helpers.py` — 30 test, hepsi gecti

**MSL referansi:** msl_components_final_blueprint.md Section 4 — helper tanimlari
**Kritik not:** Mass icin add_rigid_pair KCL EKLEMEZ. Bu MSL'den ogrenidigimiz
en onemli yapisal fark: Mass m*a = f_a + f_b (Newton), OnePort 0 = f_a + f_b (KCL).

### T0.5 — ComponentDefinition Contract Guncellemesi ✅
- [x] Mevcut `BaseComponent` icerisine yeni field'lar eklendi:
  - `category: ComponentCategory | None = None` (passive, source, sensor, reference — Literal type)
  - `tags: tuple[str, ...] = ()` (arama icin)
  - `icon_path: str | None = None` (SVG dosya yolu)
  - `icon_viewbox: str = "0 0 64 64"` (SVG viewBox)
- [x] setup() pattern: helper method'lar (T0.4) zaten standalone fonksiyonlar —
  yeni bilesenler bunlari `__init__` veya factory icinde cagirabilir.
  Mevcut bilesenler degisiklik gerektirmez.
- [x] Backward compat dogrulandi: 579 test passed, 0 regression

**Requirement referansi:** Component Library Requirements Section 6 — ComponentDefinition
**Catisma notu:** Requirement'da `equation contribution` string olarak gosterilmis.
MSL'den: sympy tabanli olacak. Requirement uyarlanir.

---

## Faz 1: Elektrik Bilesenleri

> 5 temel elektrik bilaseni — MSL blueprint'teki 3-10 satirlik forma oturacak.
> Her bilesen helper method'lari + sympy denklemleri kullanir.

### T1.1 — `app/core/models/electrical/` Dizin Yapisi ✅
- [x] `__init__.py` olusturuldu
- [x] `ground.py`, `resistor.py`, `capacitor.py`, `inductor.py`, `source.py`

### T1.2 — ElectricalGround ✅
- [x] `add_one_port(domain='electrical', name='p', direction_hint='positive')`
- [x] Denklem: `p.v == 0`
- [x] Kategori: `reference`
- [x] Test: 6 test gecti

### T1.3 — Resistor ✅
- [x] `add_one_port_pair(domain='electrical')`
- [x] Parametre: `R` (Ohm), varsayilan 1.0
- [x] Denklem: `v_diff == R * through` (Ohm)
- [x] Kategori: `passive`
- [x] Sign convention: v_diff = v_p - v_n, through = i_p (MSL uyumlu)
- [x] Test: 11 test (sign convention dahil)

### T1.4 — Capacitor ✅
- [x] `add_one_port_pair(domain='electrical')`
- [x] Parametre: `C` (Farad), varsayilan 1e-6
- [x] Denklem: `through == C * der(v_diff)`
- [x] Kategori: `passive`
- [x] StateContribution: potential energy, dof_count=1
- [x] Test: 8 test (derivative + state)

### T1.5 — Inductor ✅
- [x] `add_one_port_pair(domain='electrical')`
- [x] Parametre: `L` (Henry), varsayilan 1e-3
- [x] Denklem: `v_diff == L * der(through)`
- [x] Kategori: `passive`
- [x] StateContribution: inertial energy, dof_count=1
- [x] Test: 7 test

### T1.6 — IdealSource (VoltageSource + CurrentSource) ✅
- [x] `add_one_port_pair(domain='electrical')`
- [x] source_kind: `prescribed_across` | `prescribed_through` (effort/flow yerine acik isim)
- [x] Denklem: prescribed_across → `v_diff == signal`, prescribed_through → `through == signal`
- [x] Kategori: `source`
- [x] `VoltageSource(...)` ve `CurrentSource(...)` factory fonksiyonlar
- [x] Test: 8 test
- [x] Toplam: `tests/test_electrical_components.py` — 45 test, hepsi gecti

**MSL referansi:** msl_interfaces_analiz.md Section 2.3 — V/I source simetrisi
**Requirement referansi:** Component Library Requirements Section 5 — Elektrik bilesenleri

---

## Faz 2: Generic 1st-Order Reducer

> Mevcut M/D/K reduceryuolunu BOZMADAN yanina yeni bir generic yol ekle.
> Bu yol her domain icin calisir: sympy Jacobian ile A,B,C,D uretir.

### T2.1 — SymbolicFlattener ✅
- [x] `app/core/symbolic/symbolic_flattener.py` olusturuldu
- [x] SystemGraph'taki tum bilesenlerin `symbolic_equations()`'ini toplar
- [x] Node denklemlerini sympy formunda ekler (across equality + through balance)
- [x] Input sembollerini parameter_map'ten cikarir (input ≠ sabit parametre)
- [x] Cikti: `FlatSystem` dataclass — equations + state/algebraic/input/output/parameter

### T2.2 — SmallSignalLinearReducer ✅
- [x] `app/core/symbolic/small_signal_reducer.py` olusturuldu (adi degisti: "Generic" yerine "SmallSignal")
- [x] Adimlar: parameter substitution → der() proxy → sympy.solve → A,B,C,D cikart
- [x] Cikti: `StateSpaceModel` (ayni contract)
- [x] RC devresi: A=[[-1]], B=[[1]], C=[[1]], D=[[0]] ✅ (H(s)=1/(s+1))
- [x] Mevcut `PolymorphicDAEReducer` KORUNDU

### T2.3 — Reducer Secim Mantigi (ERTELENDI)
> **Karar:** Deferred until second reducer exists. Su an SmallSignalLinearReducer
> hem elektrik hem mekanik icin calisir. Otomatik secim mantigi ikinci reducer
> (ornegin nonlinear/numeric DAE solver) eklendiginde anlamli olur.
> Erken soyutlama riski nedeniyle bilinçli olarak ertelendi.
- [ ] SystemGraph'taki domain'lere gore otomatik secim
  - Sadece mekanik → `PolymorphicDAEReducer` (hizli M/D/K yolu)
  - Elektrik veya karisik → `SmallSignalLinearReducer`
  - Manuel override: `reducer='symbolic'` | `reducer='mdk'`
- [ ] Her iki yol ayni `StateSpaceModel` uretir
- [x] `tests/test_rc_circuit_e2e.py` — 16 test, hepsi gecti

**Catisma notu:** Implementation Plan Phase 4 "Model Builder" olarak tanimliyor.
Mevcut EquationBuilder + DAEReducer zaten bu rolu oynuyor.
Generic reducer ek bir yol — mevcut Phase 4'un genisletilmesi.

---

## Faz 3: Entegrasyon ve Dogrulama

> Yeni altyapinin hem elektrik hem mekanik tarafta dogru calistigini dogrula.

### T3.1 — RC Devresi End-to-End Testi ✅
- [x] `VoltageSource(1V step) + Resistor(1 Ohm) + Capacitor(1 F) + Ground`
- [x] SystemGraph olustur, connect() ile bagla
- [x] SmallSignalLinearReducer ile state-space uret
- [x] Beklenen: `H(s) = 1/(s+1)`, A=[-1], B=[1], C=[1], D=[0]
- [x] 16 test, hepsi gecti (`tests/test_rc_circuit_e2e.py`)

### T3.2 — RLC Devresi Testi ✅
- [x] `VoltageSource + Resistor + Inductor + Capacitor + Ground`
- [x] Beklenen: 2. mertebe sistem, `H(s) = 1/(LCs^2 + RCs + 1)`
- [x] 2 state (v_C, i_L), A matrisi 2x2, eigenvalue stability, DC gain=1
- [x] 12 test, hepsi gecti (`tests/test_rlc_circuit_e2e.py`)

### T3.3 — Mevcut Pipeline Backward Compat ✅
- [x] 39 pre-existing hata HEAD commit'inde de mevcut (bizden kaynaklanmiyor)
- [x] Mekanik bilesenler (Spring, Damper, Mass, Ground) degisiklik görmedi
- [x] Yeni BaseComponent alanlari (category, tags, _sym_cache) opt-in default
- [x] Port enrichment (direction_hint, visual_anchor) None default ile uyumlu
- [x] 31 test, hepsi gecti (`tests/test_backward_compat.py`)

### T3.4 — Cross-Domain Dogrulama ✅
- [x] Domain izolasyonu: elektrik↔mekanik baglanti hatasi dogrulandi
- [x] DomainSpec registry: 4 domain, effort/flow, power_order
- [x] Bagimsiz pipeline calismasi: symbolic (elektrik) + string (mekanik)
- [x] Multi-domain SystemGraph: farkli domain bilesenleri bir arada
- [x] 18 test, hepsi gecti (`tests/test_cross_domain.py`)
- [x] Bond-graph analojisi testi — **covered by T4.5:** `TestBondGraphAnalogy` in `tests/test_mass_spring_damper_e2e.py` (MSD vs RLC eigenvalue parity)

---

## Faz 4: Mevcut Mekanik Bilesenleri Yeni Helper'larla Yeniden Yazma

> Mevcut Mass/Spring/Damper calismaya devam ederken,
> yeni versiyonlarini helper method'larla yaz. Parity test ile dogrula.

### T4.1 — TranslationalSpring ✅
- [x] `add_one_port_pair(domain='translational')` ile yeniden yazildi
- [x] Denklem: `through = k * v_diff` (v_diff = s_b - s_a, MSL sign convention)
- [x] 10 birim test gecti (`tests/test_translational_components.py`)

### T4.2 — TranslationalDamper ✅
- [x] `add_one_port_pair(domain='translational')` ile yeniden yazildi
- [x] Denklem: `through = d * der(v_diff)` (viskoz sönüm)
- [x] 5 birim test gecti

### T4.3 — TranslationalMass ✅
- [x] `add_rigid_pair(domain='translational')` ile yeniden yazildi
- [x] Denklem: `der(s) = v`, `m * der(v) = f_a + f_b` (Newton, 2 state)
- [x] 8 birim test gecti (KCL yok, rigid coupling dogrulandi)

### T4.4 — TranslationalFixed + ForceSource/PositionSource ✅
- [x] `add_one_port(domain='translational')` ile TranslationalFixed yazildi
- [x] ForceSource (prescribed_through) ve PositionSource (prescribed_across)
- [x] 8 birim test gecti

### T4.5 — Mass-Spring-Damper E2E + Bond-Graph Analoji ✅
- [x] MSD sistemi: ForceSource → Mass → Spring||Damper → Fixed
- [x] m=1, k=1, d=1: A=[[0,1],[-1,-1]], B=[[0],[1]], C=[[1,0]], D=[[0]]
- [x] Eigenvalue stability, underdamped response, DC gain = 1/k = 1.0
- [x] **Bond-graph analoji kaniti:** MSD(m=1,k=1,d=1) eigenvalues = RLC(R=1,L=1,C=1) eigenvalues
- [x] SmallSignalLinearReducer'a index-2 DAE destegi eklendi (constrained state demotion + differentiated constraint injection)
- [x] 15 test gecti (`tests/test_mass_spring_damper_e2e.py`)
- [~] Gecis karari: eski bilesenleri deprecated isaretle
  > **Strateji (kabul edildi):** Eski bilesenleri hemen kaldirMA.
  > 1. Legacy bilesenler calisir kalir (backward compat korunur)
  > 2. Registry'de `status: "legacy"` metadata ile isaretlenecek (ileride)
  > 3. Yeni model olustururken yeni symbolic bilesenler onerilir
  > 4. Eski kayitli modeller sessizce desteklenir
  > 5. Migration araci/testi hazir olmadan kaldirma yapilmaz

---

## Faz 5: Gorsel Sistem + Component Registry

> Component Visual Symbol Guidelines'a uygun SVG altyapisi.
> Model Library Panel'in ihtiyac duydugu component registry.

### T5.1 — SVG Symbol Altyapisi ✅
- [x] `app/core/symbols/` dizini olustur
- [x] `electrical/` ve `translational/` alt dizinleri
- [x] Her bilesen icin minimal SVG dosyasi (viewBox="0 0 64 64")
  - 6 electrical: `resistor.svg`, `capacitor.svg`, `inductor.svg`, `ground.svg`, `voltage_source.svg`, `current_source.svg`
  - 6 translational: `spring.svg`, `damper.svg`, `mass.svg`, `fixed.svg`, `force_source.svg`, `position_source.svg`
- [x] Port anchor'lari SVG icinde degil, bilesen metadata'sinda

### T5.2 — ComponentRegistry ✅
- [x] `app/core/registry.py` olustur
- [x] `ComponentRegistry` sinifi:
  - `register(entry)`, `get(name)`, `all()`
  - `get_by_domain(domain) -> list`
  - `get_by_category(category) -> list`
  - `search(query) -> list` (free-text across name/domain/category/tags/description)
- [x] 12 bilesen (6 elektrik + 6 translational) kayit edilir
- [x] `ComponentEntry` frozen dataclass: factory `create()`, `icon_abs_path`
- [x] 44 test (`tests/test_registry.py`) — all passing

**Requirement referansi:** Model Library Panel Requirements Section 4 — Organization
**Component Library Requirements Section 10 — Categories

### T5.3 — %name / %R Placeholder Sistemi ✅
- [x] SVG template'lerinde `{{name}}`, `{{R}}` gibi placeholder'lar (11 SVG guncellendi + 1 yeni position_source.svg)
- [x] `app/core/symbols/renderer.py`: `render_svg()`, `load_and_render()`, `render_entry_svg()`, `extract_placeholders()`
- [x] MSL'in `Text(textString="%name")` pattern'inin Python karsiligi
- [x] 81 test (`tests/test_svg_renderer.py`) — all passing

---

## Oncelik ve Bagimlilk Tablosu

```
T0.1 (DomainSpec)  ─────────────────────────┐
T0.2 (Port)  ───────────────────────────────┤
T0.3 (Sympy equation)  ────────────────────┤
                                            ▼
                                   T0.4 (Helpers) ──────────┐
                                   T0.5 (Contract)          │
                                            │               │
                              ┌─────────────┤               │
                              ▼             ▼               ▼
                        T1.1-T1.6      T4.1-T4.5      T2.1-T2.3
                      (Elektrik)     (Mek. yeniden)   (Generic reducer)
                              │             │               │
                              └──────┬──────┘               │
                                     ▼                      │
                              T3.1-T3.4  ◄──────────────────┘
                           (Dogrulama)
                                     │
                                     ▼
                              T5.1-T5.3
                           (Gorsel + Registry)
                                     │
                                     ▼
                              T6.1-T6.7
                    (Canvas Entegrasyonu + Save/Load)
```

---

## Faz 6: Mevcut Canvas Entegrasyonu + Save/Load

> Mevcut ModelCanvas (QPainter, 1954 satir) ve palette sistemini
> Phase 1 altyapisina (ComponentRegistry, symbolic pipeline, port anchors)
> baglama. Yeni canvas yazmak degil, mevcut sistemi yeni altyapiya gecirme.
>
> Mimari ilke: Canvas gorsel, registry bilir, component fizik uretir, compiler baglar.
> QGraphicsScene migration Phase 8/9 olarak ertelenmistir.

### T6.1 — ComponentVisualSpec + Registry Eslesmesi
- [ ] `ComponentVisualSpec`'e `registry_name: str | None` alani ekle
- [ ] `core_factory` lambda'larini registry'deki `ComponentEntry.create()` ile degistir
- [ ] `port_mapping: dict[str, str]` alanini ekle (canvas port adi → core port adi)
  - Mevcut `_CANVAS_TO_CORE_PORT` tablosunu spec icerisine tasi
- [ ] `palette_domain: str` ve `palette_category: str` alanlari ekle
  - Mevcut `PALETTE_GROUP_ASSIGNMENTS` dict'ini spec metadata'sina tasi
- [ ] Mevcut COMPONENT_CATALOG girdilerini registry ile eslestir
- [ ] Yeni Phase 1 bilesenleri (6 electrical + 6 translational) icin catalog girdileri olustur

**Gap notu:** Mevcut catalog 31+ bilesen (quarter-car, wheel, tire vb.) iceriyor.
Bunlarin hepsi hemen registry'ye tasinmak zorunda degil. Onceki mevcut kalsın,
yeniler registry uzerinden gelsin. Gecis kademeli.

### T6.2 — CanvasCompiler Registry Entegrasyonu
- [ ] `_create_core_component()` icerisinde once registry'ye bak, yoksa eski catalog'a fall back
- [ ] `_resolve_port_id()` icerisinde spec'teki `port_mapping` kullan
- [ ] Domain uyumluluk kontrolu ekle: elektrik↔mekanik wire olusturulamaz
- [ ] Yeni symbolic pipeline yolu: registry bileseni ise `flatten()` + `SmallSignalLinearReducer` kullan
- [ ] Eski bilesenler icin mevcut `EquationBuilder` / `QuarterCarNumericBackend` yolu korunsun

**Karar noktasi:** Compiler hangi path'i sectigini `ComponentEntry.domain` veya
`type_key` prefix'ine gore belirleyebilir. Detay T6.2 icinde netlestirilecek.

### T6.3 — Palette Builder'i Registry'den Besle
- [ ] `build_palette_tree()` fonksiyonunu registry sorgusuyla degistir
- [ ] `registry.get_by_domain()` + `registry.get_by_category()` ile gruplama
- [ ] Mevcut bilesenlerin palette gorunumu korunsun (backward compat)
- [ ] Yeni bilesenler (Capacitor, Inductor, VoltageSource vb.) palette'te gorunsun
- [ ] Arama: `registry.search(query)` ile palette filtreleme

### T6.4 — SVG Renderer Entegrasyonu
- [ ] `ComponentRenderer._draw_svg_symbol()` icinde yeni `render_entry_svg()` kullan
- [ ] Registry'deki `icon_path` → `app/core/symbols/` ile cozumle
- [ ] Mevcut `app/SVG/` dizinindeki asset'lar korunsun (eski bilesenler icin)
- [ ] Placeholder substitution: canvas component instance name + params → SVG text

### T6.5 — PropertyEditor + Parametre Entegrasyonu
- [ ] Registry'deki `default_params` uzerinden parametre listesini goster
- [ ] Kullanici parametre degistirdiginde canvas component'e yansit
- [ ] Parametre degisikligi save/load'da saklansin
- [ ] Ileride: parametre tipi, sinir, birim bilgisi (Phase 1 henuz yok, placeholder)

### T6.6 — Save/Load JSON Schema v2
- [ ] JSON schema'ya `"version": 2` alani ekle
- [ ] Component icerisinde fizik ve gorsel ayrilsin:
  ```json
  {
    "id": "r1",
    "type": "electrical.resistor",
    "registry_name": "Resistor",
    "position": {"x": 120, "y": 80},
    "rotation": 0,
    "flip": false,
    "parameters": {"R": 1000}
  }
  ```
- [ ] Connection'da gercek port adlari saklansin:
  ```json
  {
    "from": {"component": "r1", "port": "port_a"},
    "to": {"component": "c1", "port": "port_b"}
  }
  ```
- [ ] v1 → v2 migration fonksiyonu: eski layout'lari yeni formata cevir
- [ ] v1 layout'lar acilabilir kalmali (backward compat)

### T6.7 — Entegrasyon Testleri
- [ ] Registry bilesen → canvas drop → compile → SystemGraph → flatten → state-space
- [ ] Yeni elektrik bilesenleri ile RC devresi canvas uzerinden kurulur
- [ ] Save → load → compile → ayni sonuc
- [ ] Eski layout'lar (quarter-car, single_mass) hala acilir ve calisir
- [ ] Domain izolasyonu: canvas uzerinde elektrik-mekanik wire hatasi
- [ ] Parametre degisikligi → yeniden compile → farkli A matrisi

---

**Degismeyecek seyler (Phase 6'da dokunulmayacak):**
- ComponentRenderer cizim mantigi (pure painting)
- Union-find topoloji algoritmasi
- Probe attachment mantigi
- ModelCanvas mouse/keyboard event handling
- SceneAnimationMapper

 (Requirement vs MSL)

| Konu | Requirement Dokumanlar | MSL Analizi | Karar |
|------|------------------------|-------------|-------|
| Denklem formati | String-based (implicit) | Sympy-based symbolic | **MSL: sympy** — generic reducer icin gerekli |
| Port tipi | role + direction/causality | direction_hint (tek field) | **MSL: direction_hint** — daha sade |
| Bilesen hiyerarsisi | ComponentDefinition flat | Helper method pattern | **MSL: helper pattern** — boilerplate azalir |
| Domain tanimlari | Sadece isim | DomainSpec (unit, renk, across/through) | **MSL: DomainSpec** — daha zengin |
| Source soyutlamasi | Ayri VoltageSource/CurrentSource | Generic IdealSource(drive=e/f) | **MSL: generic** — Python'da tek sinif |
| Reducer | M/D/K (2. mertebe mekanik) | Generic 1st-order (her domain) | **Ikisi birlikte** — eski korunur, yeni eklenir |
| SVG physics | "physics must never be inferred from SVG" | Icon annotation = gorsel, equation = fizik | **Uyumlu** — catisma yok |

---

## Durum Takibi

- **Son guncelleme:** 2026-04-26
- **Aktif faz:** Faz 0 (baslangic)
- **Tamamlanan task sayisi:** 0 / 28
- **Sonraki adim:** T0.1 — DomainSpec Registry
