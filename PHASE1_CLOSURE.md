# Phase 1 Closure Note

> Tarih: 2026-04-26
> Kapsam: SYSTEM_MODELING_ROADMAP.md Faz 0–5

---

## Tamamlanan Isler

### Faz 0 — Cekirek Altyapi (T0.1–T0.5)
- DomainSpec registry (4 domain: electrical, mechanical_translational, rotational, hydraulic)
- Port zenginlestirmesi: direction_hint, visual_anchor
- Sympy tabanli denklem altyapisi: SymbolicEquation, _der_func
- Helper method'lar: add_one_port, add_one_port_pair, add_rigid_pair
- ComponentDefinition contract guncellendi

### Faz 1 — Elektrik Bilesenleri (T1.1–T1.6)
- 6 bilesen: ElectricalGround, Resistor, Capacitor, Inductor, VoltageSource, CurrentSource
- Hepsi symbolic helper'lar uzerinden, MSL sign convention'a uygun

### Faz 2 — Generic 1st-Order Reducer (T2.1–T2.2)
- SymbolicFlattener: graph → flat symbolic system
- SmallSignalLinearReducer: symbolic equations → state-space (A, B, C, D)
- RC devresi golden test: H(s) = 1/(s+1) dogrulandi

### Faz 3 — Entegrasyon ve Dogrulama (T3.1–T3.4)
- RC E2E (16 test), RLC E2E (12 test)
- Backward compatibility (31 test): eski bilesenler kirilmadi
- Cross-domain izolasyon (18 test): domain sinirlari korunuyor
- Bond-graph analojisi: MSD ↔ RLC eigenvalue parity (T4.5 icerisinde)

### Faz 4 — Mekanik Bilesenleri Yeniden Yazma (T4.1–T4.5)
- 6 bilesen: TranslationalFixed, TranslationalSpring, TranslationalDamper,
  TranslationalMass, ForceSource, PositionSource
- Mass-spring-damper E2E (15 test): A=[[0,1],[-1,-1]], B=[[0],[1]]
- SmallSignalLinearReducer'a index-2 DAE destegi eklendi
  (constrained state demotion + differentiated constraint injection)

### Faz 5 — Gorsel Sistem + Component Registry (T5.1–T5.3)
- 12 SVG dosyasi (6 electrical + 6 translational), viewBox="0 0 64 64"
- ComponentRegistry: 12 bilesen, domain/category/search/factory
- SVG placeholder sistemi: {{name}}, {{R}}, {{k}} vb.
- XML escape (injection onleme)
- Port anchor metadata (component port isimleriyle birebir eslesme)

---

## Sayisal Ozet

| Metrik | Deger |
|--------|-------|
| Toplam test | 952 passed, 310 skipped, 2 failed (pre-existing scipy) |
| Yeni test dosyalari | 8 (rc_e2e, rlc_e2e, backward_compat, cross_domain, translational_components, msd_e2e, registry, svg_renderer) |
| Yeni kaynak dosyalar | ~25 (models, symbolic, symbols, registry) |
| SVG dosyalari | 12 |
| Kayitli bilesenler | 12 (6 electrical + 6 translational) |
| Domain sayisi | 2 aktif (electrical, translational) |
| Tasarim dokumanlari | 3 (SIGN_CONVENTION.md, VISUAL_DESIGN_DECISIONS.md, PHASE1_CLOSURE.md) |

---

## Alinan Kararlar

1. **Sign convention**: MSL uyumlu. across=v_b-v_a (power_order=1), through=i_b, KCL: i_a+i_b=0.
2. **SVG sadece gorsel**: Port anchor bilgisi registry'de explicit, SVG'den parse edilmez.
3. **Registry sorumluluk siniri**: Kayit + kesif katmani. Fizik, UI ve simulasyon tasimaz.
4. **Rotate/flip gorseldir**: Fiziksel port semantigi degismez.
5. **Legacy bilesenleri kaldirma**: Migration araci hazir olmadan yapilmaz.

---

## Kabul Edilen Riskler

1. **Tek reducer**: SmallSignalLinearReducer hem elektrik hem mekanik icin calisiyor.
   Nonlinear veya yuksek index DAE'ler desteklenmiyor. Kabul edilebilir cunku
   MVP kapsami lineer LTI sistemler.

2. **Asset loading dosya yolu tabanli**: `Path(__file__).parent / "symbols"`.
   Dagitim (PyInstaller, wheel) asamasinda `importlib.resources`'a gecis gerekecek.

3. **Escape sadece text icin**: SVG attribute degerlerinin dinamiklesme durumunda
   numeric constraint gibi ek validasyon gerekir.

4. **Pre-existing 2 test failure**: `scipy` modulu eksik ortamda `test_linearization_warnings`
   icindeki 2 test basarisiz. Bizim degisikliklerimizle ilgisi yok.

---

## Ertelenen Isler

| Madde | Neden | Ne Zaman |
|-------|-------|----------|
| T2.3 Reducer secim mantigi | Tek reducer var, erken soyutlama riski | Ikinci reducer eklendiginde |
| T4.5 Legacy deprecation | Migration araci yok, kullanici kirilma riski | Migration testi hazir olunca |
| Numeric constraint (SVG attr) | Su an sadece text placeholder var | SVG attribute'leri dinamiklesince |
| importlib.resources gecisi | Gelistirme ortaminda sorun yok | Dagitim oncesi |

---

## Sonraki Adimlar Icin Oneriler

Phase 1 tamamlandi. Bundan sonra mumkun yonler:

- **Phase 2: Canvas/UI katmani** — registry + port anchors + SVG render'i birlestiren
  gorsel canvas. Drag-drop, connection line, snapping.
- **Transfer function cikisi** — StateSpaceModel'den H(s) Bode plot, step response.
- **Rotational domain** — 3. domain: Inertia, TorsionalSpring, TorsionalDamper.
- **Save/load** — Model serialization (JSON/YAML), canvas state, topology.
- **Nonlinear/numeric reducer** — Jacobian linearization, numeric DAE solver.

Hangisine gecilecegi proje oncelikleriyle belirlenmeli.
