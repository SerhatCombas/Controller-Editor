# Faz 5 — Template-as-Data Refactor: Yol Haritası

## TL;DR

Faz 5'in amacı: **Default layout'lar Python sınıfı değil, basic
component'lerden inşa edilmiş `SystemGraph` factory'leri olsun.** Modelica
nasıl `.mo` dosyalarında jenerik komponentlerden örnek modeller tanımlıyorsa,
bizim Python factory fonksiyonlarımız da öyle çalışsın.

İyi haber: Mekanik template'ler (`single_mass`, `two_mass`, `quarter_car`)
**zaten doğru pattern'da**. Asıl sorun iki yerde:

1. **Elektrik template'leri boş** (`rlc_circuit.py`, `rc_circuit.py` —
   placeholder'lar). Bunları **doldurmak gerekiyor**.
2. **MainWindow `quarter_car` template'in `SystemGraph`'ını kullanmıyor** —
   onun yerine paralel yaşayan `QuarterCarModel` + `QuarterCarParameters` +
   `QuarterCarNumericBackend` sınıflarını kullanıyor. Bu **asıl refactor**.

---

## Sub-faz tablosu

| Sub-faz | Açıklama | Risk | Süre tahmini |
|---|---|---|---|
| 5a | Elektrik QK sabitleri ekle (`output_kind.py`) | Düşük | 30 dk |
| 5b | RLC template'i doldur (`rlc_circuit.py`) | Düşük | 1 saat |
| 5c | RLC için end-to-end test (`test_rlc_circuit_e2e.py`) | Düşük | 1-2 saat |
| 5d | MainWindow'da template seçici UI ekle | Orta | 2-3 saat |
| 5e | `GenericNumericBackend` sınıfı yaz | Yüksek | 1 gün |
| 5f | MainWindow refactor: hardcoded QuarterCar bağımlılığı kaldır | Yüksek | 1 gün |
| 5g | RC template'ini doldur (5b pattern'ı) | Düşük | 30 dk |
| 5h | Quarter-car için parity testi (eski vs yeni backend) | Yüksek | 1 gün |
| 5i | Eski `QuarterCarModel`/`QuarterCarNumericBackend` sınıflarını sil | Orta | 2 saat |
| 5j | Faz 5 dokümantasyonu (faz5_summary.md, ADR) | Düşük | 1 saat |

**Faz 5 toplam**: ~5-6 gün. Ama 5a-5d **bir günde bitirilebilir** ve hemen
"iki çalışan default template" hedefine ulaşırsın. 5e-5i daha derin refactor
ve sonra gelir.

---

## 5a — Elektrik QK sabitleri ✅ TAMAMLANDI

`output_kind.py`'a elektrik QK sabitlerini eklendi:
QK_CURRENT, QK_CAPACITOR_VOLTAGE, QK_VOLTAGE, QK_RELATIVE_VOLTAGE.

---

## 5b — RLC template'i doldur ✅ TAMAMLANDI

`app/core/templates/rlc_circuit.py` basic component'lerden inşa edildi:
VoltageSource("v_source") → Resistor("resistor") → Inductor("inductor") →
Capacitor("capacitor") → ElectricalGround("ground").

3 probe: loop_current, capacitor_voltage, resistor_voltage.

---

## 5c — RLC için end-to-end test

### Amaç
RLC template'in gerçekten doğru fizik üretip üretmediğini doğrula.
R=10, L=0.5, C=1e-3:
- ω₀ = 1/√(LC) ≈ 44.72 rad/s
- ζ = R/(2√(L/C)) ≈ 0.224 (underdamped)
- ω_d ≈ 43.59 rad/s

### Not
GenericNumericBackend henüz yoksa skip with reason.

---

## 5d — MainWindow'da template seçici UI

Template combo: Quarter Car, Single Mass, Two-Mass, RLC Series Circuit.
Seçim → switch_template(template_id).

**Risk**: quarter_car bağımlılığı patlayacak — 5e ile birlikte düşünülmeli.

---

## 5e — GenericNumericBackend ⚠️ ASIL REFACTOR

Hedef yapı:
```
template.graph (SystemGraph) → GenericNumericBackend → numerik simülasyon
                             → GenericSymbolicBackend → state-space, transfer
```

Tek backend, herhangi bir SystemGraph'ı simüle edebiliyor.

---

## 5f — MainWindow refactor

Hardcoded QuarterCar bağımlılığını kaldır. Template-bağımsız yapıya geç.
ModelDescriptor concept'i ile template metadata'sını yönet.

---

## 5g — RC template'i doldur

RLC pattern'ından Inductor çıkar. Trivial.

---

## 5h — Quarter-car parity testi

Eski QuarterCarNumericBackend vs GenericNumericBackend(quarter_car) karşılaştır.

---

## 5i — Eski sınıfları sil

5h parity geçtiyse güvenle sil:
- QuarterCarModel
- QuarterCarNumericBackend

---

## 5j — Dokümantasyon

- docs/faz5_summary.md
- docs/decisions/014-template-as-data.md
- architecture.md generic backend bölümü
