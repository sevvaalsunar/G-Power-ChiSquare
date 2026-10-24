# G*Power χ² Olumsallık Tabloları ve Yanıt Oranları — Temiz Oda Yeniden Yazımı

YZM301 Yazılım Gerçekleme ve Test · Teardown Sprint
**Test ailesi:** χ² tests → Goodness-of-fit tests: Contingency tables (olumsallık tabloları ve yanıt oranları)
**Ekip:** Şevval Sunar (temiz oda yeniden yazımı), Arda Erdem, Sıla Çördük, Kübra Başımoğlu

G*Power, klinik araştırmacıların “kaç denek gerekir?” sorusunu yanıtladığı ücretsiz bir araçtır, ama yalnızca grafik arayüzü vardır. Bir AI ajanı onu ancak ekran görüntüsü alıp tıklayarak kullanabilir. Bu depo, G*Power 3.1.9.7'nin olumsallık tablosu güç hesabını tersine mühendislikle (REA) inceler, bulguları `LEDGER.md`'de kanıtlarıyla belgeler, `SPEC.md`'ye döker ve temiz odada yeniden yazar. Motor; CLI, MCP sunucusu ve doğal dil ajanı üzerinden kullanılabilir.

**Ajanın söktüğü şeyin doğru olduğunu nasıl kanıtlıyoruz?** Her davranış iki yoldan doğrulanır: (1) ekip üyeleri aynı girdileri G*Power penceresine girip sonucu klonla karşılaştırır (`oracle/`, `index.html`); (2) motor bağımsız bir referansa, SciPy'nin `ncx2` dağılımına karşı sayısal olarak test edilir. Kılavuzda yazmayan davranışlar `[REA]` etiketiyle, G*Power ekran görüntüleriyle belgelenir.

---

## 1. Ödev kriterleri

| Kriter | Puan | Durum | Nerede |
|---|---|---|---|
| Temel: CLI | 85 | Uygulandı | `src/chi2power/cli.py`, `gpower-clone` komutu |
| Kapı: gizli vektörlerde N ≥ %90 tam eşleşme | Zorunlu | C01–C06 G*Power ile eşleşiyor; C07–C08 ölçüm bekliyor | `oracle/`, `tests/test_oracle_chi2.py` |
| MCP sunucusu | +15 | Uygulandı | `src/chi2power/mcp_server.py` (`chi2_contingency` aracı) |
| AI ajanı (MCP üzerinden, doğal dilde) | +10 | Uygulandı | `src/chi2power/agent.py` |
| Kural 1: `[REA]` kanıtları | Kural | 2 doğrulanmış `[REA]`, 5 hipotez test aşamasında | `LEDGER.md`, `docs/evidence/` |
| Kural 2: iki ayrı ajan oturumu | Kural | İnceleme oturumu → `SPEC.md` → yazım oturumu | `docs/sessions/` |
| Kural 3: tek motor | Kural | CLI, MCP ve ajan yalnızca `engine.py`'yi çağırır | `src/chi2power/engine.py` |
| Kural 4: decompile çıktısı ve GPower.exe yok | Kural | `.gitignore` ikili dosyaları ve decompile klasörlerini dışlar | `.gitignore` |

**Kural 3 ile ilgili not:** `index.html` puanlanan bir katman değildir; ekibin G*Power ölçümlerini toplayıp klonla karşılaştırdığı test platformudur. Tarayıcıda Python çalışmadığı için motorun bir JavaScript portunu içerir. Bu port, Python motoruyla aynı çıpalara ve SciPy referansına karşı doğrulanmıştır.

---

## 2. Kurulum ve çalıştırma

Harici bağımlılık yoktur (saf Python ve vanilla JS). Python 3.9 veya üstü gerekir.

```bash
pip install -e ".[test]"
```

### Testler
```bash
python -m pytest -v
```
`pyproject.toml`, `src/` klasörünü test yoluna eklediği için testler paket kurulmadan da çalışır.

### CLI
```bash
# A priori: w'den N bulma
gpower-clone --w 0.30 --alpha 0.05 --power 0.80 --df 1

# Yanıt oranlarından (Grup 1 %45, Grup 2 %25)
gpower-clone --p1 0.45 --p2 0.25 --alpha 0.05 --power 0.80
```
Paketi kurmadan çalıştırmak için: `python -m chi2power.cli ...` (`src/` klasöründeyken veya `PYTHONPATH=src` ile).

### AI ajanı (MCP üzerinden)
```bash
gpower-clone-agent "Grup 1 yanıt oranı %25, Grup 2 %45, anlamlılık 0.05, hedef güç 0.85 için kaç hasta gerekir?"
gpower-clone-agent "Post-hoc analiz: 120 denek topladık, w=0.25 ve alpha=0.05 iken elde ettiğimiz güç nedir?"
gpower-clone-agent -i     # etkileşimli mod
```

### MCP sunucusu
Claude Desktop, Cursor gibi istemcilere stdio üzerinden bağlanır:
```bash
gpower-clone-mcp
```

---

## 3. Test platformu (`index.html`)

Tarayıcıda açın veya GitHub Pages ile yayınlayın (Settings → Pages → `main` / root). Kurulum ve internet gerektirmez.

- **Hesaplayıcı:** G*Power'daki pencereyle aynı girdiler (a priori / post hoc, yanıt oranları / doğrudan w). “Bu senaryoyu G*Power'da nasıl ölçerim?” kutusu, Determine penceresine girilecek hücre olasılıklarını hazır verir.
- **Karşılaştırma listesi:** Klon değerleri otomatik hesaplanır; G*Power değerlerini test eden kişi kendisi yazar. Durumlar: Uyumlu, Sapma, Bekliyor. %90 kapısı yalnızca ölçülmüş satırlardan hesaplanır.
- **Test rehberi:** Değerlerin anlamı, senaryoların rolü, istenmeyen durumlar ve G*Power ölçüm adımları.
- **Veri:** Ölçümler her ekip üyesinin kendi tarayıcısında saklanır. JSON ile dışa aktarılıp birleştirilir; birleşmiş liste CSV olarak `oracle/` klasörüne konur.

---

## 4. Motor özeti

Ayrıntılar `SPEC.md`'dedir.

1. **w türetimi (R-02):** 2 × 2 tabloda hücre olasılıkları p₁₁ = a₁p₁, p₁₂ = a₁(1 − p₁), p₂₁ = a₂p₂, p₂₂ = a₂(1 − p₂); w = √Σ (pᵢⱼ − Eᵢⱼ)² / Eᵢⱼ, Eᵢⱼ = Rᵢ·Cⱼ.
2. **Kritik değer (R-03):** merkezi χ² dağılımının (1 − α) kuantili.
3. **Güç (R-05):** λ = w²·N ile merkezi olmayan χ² dağılımı; Poisson ağırlıklı seri, moddan iki yöne toplanır.
4. **A priori N (R-06, `[REA]`):** hedef güce ulaşan en küçük tamsayı N. G*Power sürekli çözümü yuvarlamaz; bu yüzden w = 0.30'da N = 88 ve gerçekleşen güç 0.8035'tir.

---

## 5. Dosya yapısı

```
gpower-chi2-teardown/
├── index.html                    # Ekip test platformu (puanlanan katman değil)
├── SPEC.md                       # Temiz oda şartnamesi (R-01 … R-08)
├── LEDGER.md                     # Kanıt defteri ([REA] / [DOK])
├── README.md
├── pyproject.toml
├── .gitignore                    # Kural 4
├── docs/
│   ├── evidence/                 # G*Power ekran görüntüleri (LEDGER kanıtları)
│   └── sessions/                 # İnceleme ve yazım ajan oturumlarının kayıtları (Kural 2)
├── oracle/
│   └── gpower_chi2_vectors.csv   # G*Power'da ölçülmüş doğrulama vektörleri
├── src/chi2power/
│   ├── __init__.py
│   ├── engine.py                 # Tek hesap motoru
│   ├── cli.py                    # CLI katmanı
│   ├── mcp_server.py             # MCP stdio JSON-RPC sunucusu
│   └── agent.py                  # Doğal dil ajanı (MCP istemcisi)
└── tests/
    ├── test_oracle_chi2.py       # oracle vektörleri
    └── test_agent_and_mcp.py     # MCP protokolü ve ajan testleri
```
