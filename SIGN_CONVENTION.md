# Sign Convention Specification

> Bu dosya tüm domain'ler için tek referans noktasıdır.
> Tüm bileşenler, helper'lar, reducer ve testler bu kurallara uymalıdır.
> Bir çelişki varsa BU DOSYA kazanır.

---

## 1. Terminoloji

| Terim | Anlamı | Kaynak |
|-------|--------|--------|
| **across** | Modelica connector'daki potansiyel/konum değişkeni | MSL |
| **through** | Modelica connector'daki akış/kuvvet değişkeni | MSL |
| **effort** | Power-conjugate çiftinin "itici" tarafı (effort × flow = power) | Bond-graph |
| **flow** | Power-conjugate çiftinin "akan" tarafı | Bond-graph |

**Kritik:** Elektrikte across≡effort, through≡flow. Mekanikte BÖYLE DEĞİL:

| Domain | across | through | effort | flow | power_order |
|--------|--------|---------|--------|------|-------------|
| Electrical | v (voltage) | i (current) | v | i | 0 |
| Translational | s (position) | f (force) | f | v=ds/dt | 1 |
| Rotational | phi (angle) | tau (torque) | tau | omega=dphi/dt | 1 |

`power_order=0`: effort=across, flow=through, power=across×through
`power_order=1`: effort=through, flow=der(across), power=through×der(across)

---

## 2. Port Yön Konvansiyonu

### 2.1 Elektrik

- **positive (p)**: Akımın BİLEŞENE GİRDİĞİ port
- **negative (n)**: Akımın BİLEŞENDEN ÇIKTIĞI port
- `v_diff = v_p - v_n` (positive - negative, MSL ile aynı)
- `through = i_p = -i_n` (bileşene giren akım pozitif)
- Passive sign convention: `P = v_diff × through ≥ 0` (bileşen güç tüketir)

### 2.2 Translational

- **port_a (flange_a)**: Sol/üst/referans tarafı port
- **port_b (flange_b)**: Sağ/alt/hareket tarafı port
- `s_rel = s_b - s_a` (relative position, MSL PartialCompliant ile aynı)
- `v_rel = der(s_rel) = v_b - v_a` (relative velocity)
- `0 = f_a + f_b` (KCL: OnePort bileşenleri için kuvvet dengesi)
- `through = f_b` (port_b'ye giren kuvvet pozitif)
- Passive: Spring `f = k × s_rel`, Damper `f = d × v_rel`

### 2.3 Rotational

- **port_a / port_b**: flange_a / flange_b ile aynı konvansiyon
- `phi_rel = phi_b - phi_a`
- `omega_rel = der(phi_rel)`
- `0 = tau_a + tau_b` (KCL)
- `through = tau_b`

---

## 3. Bileşen Kalıpları ve İşaret Kuralları

### 3.1 OnePort Pair (add_one_port_pair) — Resistor, Spring, Damper, C, L

```
   port_a ──┤ Component ├── port_b
   (pos/a)                  (neg/b)
```

Üretilen denklemler:
1. Across difference domain'e göre tanımlanır:
   - Electrical: `v_diff = v_a - v_b` (`v_p - v_n`)
   - Translational/Rotational: `v_diff = v_b - v_a` (`s_b - s_a`, `phi_b - phi_a`)
2. `0 = i_a + i_b`       (KCL: through balance)
3. Through alias domain'e göre tanımlanır:
   - Electrical: `through = i_a`
   - Translational/Rotational: `through = i_b`

Bileşenin constitutive law'ı `v_diff` ve `through` kullanır:
- Resistor: `v_diff = R × through`
- Capacitor: `through = C × der(v_diff)`
- Inductor: `v_diff = L × der(through)`
- Spring: `through = k × v_diff`  (burada v_diff aslında s_rel)
- Damper: `through = d × der(v_diff)` (burada der(v_diff) = v_rel)

### 3.2 Rigid Pair (add_rigid_pair) — Mass

```
   port_a ──┤ Mass ├── port_b
   (a)                 (b)
```

Üretilen denklemler:
1. `v_a = v_center`  (rigid coupling)
2. `v_b = v_center`  (rigid coupling)
- KCL YOK! Mass kendi Newton denklemini yazar.

Mass'ın constitutive law'ı:
- `m × der(v_center) = f_a + f_b`

Dikkat: `f_a + f_b` toplamı, KCL'deki `f_a + f_b = 0` DEĞİL.
Mass'ta `f_a + f_b = m×a ≠ 0`.

### 3.3 Kaynaklar (IdealSource)

Kaynak türleri — bond-graph değil, açık isimlendirme:
- `prescribed_across`: Across değişkenini sabitler (VoltageSource, PositionSource)
- `prescribed_through`: Through değişkenini sabitler (CurrentSource, ForceSource)
- `prescribed_derivative_across`: der(across) sabitler (VelocitySource)

Kaynak işareti: `v_diff = V_source` veya `through = I_source`
(passive sign convention ile tutarlı: kaynak güç üretir → P < 0)

### 3.4 Ground / Fixed (add_one_port)

Tek port, referans constraint:
- Electrical Ground: `v = 0`
- Mechanical Fixed: `s = 0` (ve dolayısıyla `v = 0`)

---

## 4. Connection (Node) Kuralları

Bir node'a bağlı tüm portlar için:
- **Across eşitliği**: Aynı node'daki tüm across değişkenleri eşit
  - `v_p1 = v_p2 = ... = v_node`
- **Through dengesi (KCL/KFL)**: Node'a giren through'lar toplamı = 0
  - `Σ through_in = 0`
  - İşaret: port'un direction_hint'ine göre; positive→giren, negative→çıkan

---

## 5. Reducer İçin Kurallar

1. Connection-set'ten across eşitliği ve through dengesi oluştur.
2. Bileşenlerin `symbolic_equations()` listesini al.
3. `der()` terimlerini tanı → state variables.
4. Algebraic değişkenleri elimine et.
5. `power_order=1` olan domain'lerde: flow=der(across), bu ek state yaratır.
6. Sonuç: `ẋ = Ax + Bu`, `y = Cx + Du`

---

## 6. Test Doğrulama Kontrol Listesi

Her yeni bileşen için şu testler yazılmalı:
- [ ] Passive sign convention: R/Spring/Damper pozitif parametre ile pozitif güç tüketmeli
- [ ] KCL: OnePort pair'de i_a + i_b = 0 olmalı
- [ ] No KCL: Rigid pair'de i_a + i_b ≠ 0 (= m×a)
- [ ] across_diff işareti: electrical `v_a - v_b`; mechanical `v_b - v_a`
- [ ] Transfer function DC gain işareti: bilinen referans değerle karşılaştır
- [ ] Source işareti: prescribed_across kaynak pozitif V verince v_diff > 0 olmalı
