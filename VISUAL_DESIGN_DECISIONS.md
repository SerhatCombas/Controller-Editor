# Visual System Design Decisions

> Phase 5 sonrasi mimari degerlendiermeden cikan uc kritik tasarim karari.
> Bu dokuman, canvas/connection/flatten katmanlarinin tutarli calismasini saglar.

---

## Karar 1: SVG Sadece Gorseldir

**Soru:** SVG dosyasi port anchor bilgisi de tasir mi, yoksa sadece gorsel temsil mi?

**Karar:** SVG **sadece gorsel temsildir**. Fiziksel model bilgisi SVG'den turetilmez.

### Ne SVG'de kalir:
- Sembol cizimi (path, line, rect, circle)
- `{{name}}`, `{{R}}` gibi placeholder text element'leri
- `viewBox="0 0 64 64"` standart boyut
- `stroke="currentColor"` tema uyumlulugu

### Ne SVG'de KALMAZ:
- Port sayisi, port domain'i, port direction
- Sign convention (across/through yonu)
- Denklemler, parametre tanimlari, default degerler
- Port anchor koordinatlari (x, y)

### Port Anchor'lari Nerede?
`ComponentEntry.port_anchors` icerisinde, Python tarafinda explicit:

```python
ComponentEntry(
    name="Resistor",
    ...
    port_anchors={
        "p": (0.0, 32.0),   # positive terminal, SVG (x,y)
        "n": (64.0, 32.0),  # negative terminal
    },
)
```

**Gerekce:** Port koordinatlari SVG comment'lerinden parse edilirse:
- SVG degistiginde fizik kirilir
- Farkli tema/boyut icin SVG degistirince port'lar kayar
- Hit-test, snapping, connection line hesaplamasi guvenilmez olur

---

## Karar 2: Registry Sorumluluk Siniri

**Soru:** Registry hangi metadata'larin tek kaynagi (single source of truth)?

**Karar:** Registry **kayit ve kesif katmani**dir. Fizik veya UI davranisi tasiMAZ.

### Registry'nin Sorumlulugu (Single Source):
| Metadata | Tip | Ornek |
|----------|-----|-------|
| `name` | str | "Resistor" |
| `component_class` | Type | Resistor sınıfı |
| `domain` | str | "electrical" |
| `category` | str | "passive" |
| `tags` | tuple[str] | ("ohm", "passive") |
| `icon_path` | str | "electrical/resistor.svg" |
| `description` | str | "Linear resistor: v = R*i" |
| `default_params` | dict | {"R": 1000.0} |
| `port_anchors` | dict | {"p": (0, 32), "n": (64, 32)} |

### Registry'nin Sorumlulugu OLMAYAN Seyler:
| Bilgi | Gercek Kaynak |
|-------|---------------|
| Symbolic equations | `component.symbolic_equations()` |
| Port domain/direction | `component.ports` (BaseComponent) |
| Sign convention | DomainSpec + SIGN_CONVENTION.md |
| Simulation strategy | Reducer / Backend |
| UI layout state | Canvas / ViewModel |
| State contribution | `component.state_contributions()` |

### Neden Bu Sinir?
Registry ileride "god object" olabilir. Eger fizik denklemi, UI davranisi,
simulasyon strategy, sembol render mantigi ayni sinifta birlesirse coupling
artar. Registry kesfeder ve fabrika uretir; fizik ve UI kendi katmanlarinda kalir.

---

## Karar 3: Rotate/Flip Gorseldir, Fiziksel Degil

**Soru:** Rotate/flip islemi fiziksel port yonunu degistirir mi?

**Karar:** **Hayir.** Rotate/flip tamamen gorsel bir transform'dur.

### Kurallar:
1. **Gorsel transform**: SVG'ye `transform="rotate(90, 32, 32)"` veya
   `transform="scale(-1,1)"` uygulanir.
2. **Port anchor'lar transform ile birlikte doner**: Canvas, gorsel port
   pozisyonunu hesaplarken transform'u anchor koordinatlarina uygular.
3. **Fiziksel anlam degismez**: Flip edilmis bir resistor'un `port_a` hala
   `port_a`'dir. Sign convention aynidir. `v_diff = v_b - v_a` degismez.
4. **Connection compiler fiziksel port kullanir**: Baglanti "port_a to port_b"
   seklinde fiziksel ID ile yapilir, gorsel pozisyonla degil.

### Ornek:
```
Normal:     [p]----/\/\/----[n]     v_diff = v_n - v_p
Flipped:    [n]----/\/\/----[p]     v_diff = v_n - v_p  (AYNI!)
```

Kullanici gorselde flip yaptiginda sadece ekrandaki yon degisir.
Flattener ve reducer tamamen ayni denklemleri gorur.

### Neden Onemli?
Modelica'da `connect(a.p, b.n)` fiziksel baglanti tanimlar. Gorsel
yerlesim (placement annotation) fizigi etkilemez. Ayni prensibi koruyoruz:
- `SystemGraph.connect(port_a_id, port_b_id)` fiziksel
- Canvas placement/rotation gorsel

---

## Ek Guvenlik Kararlari

### XML Escape (Injection Onleme)
SVG placeholder substitution sirasinda tum degerler XML-safe hale getirilir:
- `<` → `&lt;`
- `>` → `&gt;`
- `&` → `&amp;`
- `"` → `&quot;`
- `'` → `&#x27;`

Bu, kullanici tarafindan girilen bilesen adlari (`R<test>` gibi) SVG yapisini
bozmasini veya injection olusturmasini engeller.

### Placeholder-Parametre Eslesmesi
Registry `default_params` key'leri ile SVG `{{placeholder}}` key'leri
**birebir ayni olmalidir**. Implicit mapping yoktur:
- Parametre adi `R` ise placeholder `{{R}}` olur
- Parametre adi `k` ise placeholder `{{k}}` olur
- `test_has_param_placeholder_if_params` testi bu tutarliligi dogrular

### Asset Loading Stratejisi (Gelecek)
Su an `Path(__file__).parent / "symbols"` kullaniyoruz. Dagitim asamasinda
(PyInstaller, wheel, macOS app bundle) bu yol kirilabilir. Gecis plani:
1. Simdiki hali: dosya yolu (gelistirme icin yeterli)
2. Dagitim oncesi: `importlib.resources` veya `pkg_resources` ile degistir
3. Test: CI'da frozen build ile asset erisimi dogrula
