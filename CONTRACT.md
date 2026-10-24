# CONTRACT.md — gpower-clone Arayüz Sözleşmesi

**Sözleşme sürümü:** `1.0.0`  
**Ders:** YZM301 · Teardown Sprint  
**Referans (kâhin):** G*Power 3.1.9.7 (Windows)

Bu belge, yeniden yazdığınız hesap motorunun dış dünyayla nasıl konuştuğunu tanımlar: komut, parametre adları, çıktı alanları, hata biçimi ve karşılaştırma kuralları. Gizli test vektörleri, bütün takımların uygulamalarında aynı düzenekle, otomatik olarak çalıştırılacak. Sözleşmeye uymayan bir uygulama, hesabı doğru olsa bile değerlendirilemez.

---

## Etik niyet

Bu çalışma, G*Power'ın yazarlarının (Faul, Erdfelder, Lang ve Buchner) bilim dünyasına ücretsiz sunduğu emeğe saygıyla, yalnızca eğitim amacıyla yürütülen bir derstir; G*Power'ı değiştirmiyor, dağıtmıyor, satmıyor ve hiçbir çıktımızı G*Power olarak sunmuyoruz. G*Power'ı yalnızca davranışını gözlemlediğimiz bir referans olarak kullanıyoruz: kaynak kodu ya da kaynak koda dönüştürülmüş çıktısı yayımlanmıyor, hesap yayımlanmış yöntemlerden ve gözlenen davranıştan bağımsız olarak yeniden yazılıyor. Amacımız G*Power'la yarışmak değil, ona ajan çağı için bir katkı önermektir; en iyi çalışmaları yazarların değerlendirmesine sunacak, yazarların talebi hâlinde ilgili materyali derhal yayından kaldıracağız.

*This is a non-commercial university course run solely for educational purposes, with respect for the work the authors of G*Power (Faul, Erdfelder, Lang and Buchner) have made freely available to the scientific community; we do not modify, redistribute or sell G*Power, and none of our outputs is presented as G*Power. G*Power serves only as a behavioural reference: no source code or decompiled output is published, and the calculations are reimplemented independently from published methods and observed behaviour. Our aim is not to compete with G*Power but to propose a contribution for the age of AI agents; we will offer the best results to the authors for their review and will promptly withdraw any material at their request.*

> **Not:** Sözleşme arayüzü tanımlar, davranışı tanımlamaz. $N$'nin nasıl yuvarlandığı, eşit olmayan oranda $n_1/n_2$'nin nasıl dağıldığı, iterasyonun ne zaman durduğu ya da hangi girdilerin reddedildiği burada yazmıyor. Bunlar G*Power'ın davranışıdır ve bulmanız gereken şeylerdir (kanıt defterinde `[REA]`).

---

## 1. Kapsam

| Kapsamda | Kapsam dışı |
| :--- | :--- |
| 5 test ailesi (Bölüm 4) | G*Power'daki diğer tüm testler |
| 5 analiz modu (Bölüm 3) | Grafik (X-Y plot) ve protokol çıktısı |
| Etki büyüklüğünün doğrudan girilmesi | Etki büyüklüğünü ortalama ve standart sapmadan hesaplama ("Determine" penceresi) |

Zorunlu modlar: `a-priori` ve `post-hoc`. Bonus modlar: `compromise`, `criterion`, `sensitivity`.

---

## 2. Genel kurallar

### 2.1 Komut

```bash
gpower-clone --test <TEST_ID> --mode <MODE_ID> [--<alan> <değer> ...]
```

- Çalıştırılabilir dosyanın adı `gpower-clone`. Dil serbest. `README.md`'de kurulumu ve çalıştırmayı tek komutla gösterin.
- Her parametre `--<alan> <değer>` biçimindedir. Alan adları Bölüm 4'teki tablolarla birebir aynıdır.
- Varsayılan değer yoktur. Bir mod için gerekli olan her alan açıkça verilmelidir. Eksik alan hatadır.
- Tanınmayan bir alan hatadır. Modla ilgisiz bir alan (örneğin `post-hoc` modunda `--power`) da hatadır.
- Ondalık ayırıcı her zaman noktadır (`0.05`). İşletim sisteminin dil ayarından etkilenmemelisiniz.
- Ağ erişimi yoktur. Her çağrı 2 saniye içinde tamamlanmalıdır.
- Aynı girdi her zaman aynı çıktıyı verir (deterministik).

### 2.2 Sürüm sorgusu

```bash
gpower-clone --version
```

```json
{"contract_version": "1.0.0", "name": "gpower_chi2_forge", "engine": "Python 3.12 / SciPy"}
```

### 2.3 Başarılı çıktı

- `stdout`'a tek satır JSON yazılır. Başka hiçbir şey yazılmaz (log, uyarı ve ilerleme bilgisi `stderr`'e).
- Çıkış kodu `0`.
- Sayılar JSON `number` olarak yazılır, tam `double` hassasiyetle. Yuvarlamayın; karşılaştırmayı düzenek yapar (Bölüm 6).
- Tam sayı alanları (`n1`, `n2`, `n_total`, `df`, `df1`, `df2`) JSON tam sayısıdır (`88`, `88.0` değil).
- Bölüm 4'te listelenen alanlar zorunludur. Fazladan alan yazabilirsiniz; düzenek onları yok sayar.

### 2.4 Hata çıktısı

```json
{"error": "Power, alpha değerinden büyük olmalı", "code": "INCONSISTENT", "field": "power"}
```

- `stdout`'a tek satır JSON. `error` alanı insan için açıklamadır (Türkçe ya da İngilizce).
- Çıkış kodları: `2` geçersiz girdi, `1` iç hata (hesap yapılamadı, beklenmeyen durum).

| `code` | Anlamı |
| :--- | :--- |
| `MISSING_PARAM` | Mod için gerekli bir alan verilmedi |
| `UNKNOWN_PARAM` | Tanınmayan ya da bu modla ilgisiz alan |
| `INVALID_VALUE` | Sayı değil, tam sayı olması gereken yerde ondalık vb. |
| `OUT_OF_RANGE` | Bölüm 5'teki aralığın dışında |
| `INCONSISTENT` | Değerler tek tek geçerli ama birlikte anlamsız |
| `UNSUPPORTED` | Bilinmeyen `--test` ya da `--mode` |
| `NO_SOLUTION` | Girdiler geçerli ama G*Power da bir sonuç üretemiyor |

Ödev metnindeki `{"error":"<açıklama>"}` biçimi geçerliliğini korur. `code` ve `field` alanları bu sürümle eklendi; düzenek önce `error` alanının varlığına, sonra `code` değerine bakar.

---

## 3. Analiz modları

| `MODE_ID` | G*Power'daki adı | Ne hesaplar | Durum |
| :--- | :--- | :--- | :--- |
| `a-priori` | A priori: Compute required sample size | Gerekli örneklem büyüklüğü | Zorunlu |
| `post-hoc` | Post hoc: Compute achieved power | Ulaşılan güç | Zorunlu |
| `compromise` | Compromise: Compute implied α & power | β/α oranına göre α ve güç | Bonus |
| `criterion` | Criterion: Compute required α | Gerekli α | Bonus |
| `sensitivity` | Sensitivity: Compute required effect size | Saptanabilir en küçük etki büyüklüğü | Bonus |

G*Power'da dört büyüklükten ($\alpha$, güç, $N$, etki büyüklüğü) üçünü verirsiniz, dördüncüsünü hesaplar. Mod, hangisinin hesaplanacağını seçer.

---

## 4. Test aileleri

### 4.0 Ortak alanlar

| Alan | G*Power etiketi | Tür | Not |
| :--- | :--- | :--- | :--- |
| `test` | — | metin | Test kimliği (aşağıda) |
| `mode` | Type of power analysis | metin | Bölüm 3 |
| `tails` | Tail(s) | tam sayı: 1 ya da 2 | Yalnızca t testlerinde |
| `alpha` | α err prob | ondalık | |
| `power` | Power (1-β err prob) | ondalık | |
| `beta_alpha_ratio` | β/α ratio | ondalık | Yalnızca `compromise` |

**Çıktıda kullanılan ortak alanlar:**

| Alan | G*Power etiketi |
| :--- | :--- |
| `ncp` | Noncentrality parameter $\delta$ ya da $\lambda$ |
| `n_total` | Total sample size |
| `actual_power` | Actual power (`a-priori` çıktısı) |
| `power` | Power (1-β err prob) (`post-hoc` ve `compromise` çıktısı) |
| `alpha` | α err prob (`criterion` ve `compromise` çıktısı) |
| `beta` | β err prob (`compromise` çıktısı) |

### 4.1 `t2-indep` · K1

**G*Power:** `t tests – Means: Difference between two independent means (two groups)`  
**Klinik örnek:** İlaç ve plasebo grubu

| Mod | Girdi alanları | Çıktı alanları |
| :--- | :--- | :--- |
| `a-priori` | `tails`, `d`, `alpha`, `power`, `ratio` | `ncp`, `critical_t`, `df`, `n1`, `n2`, `n_total`, `actual_power` |
| `post-hoc` | `tails`, `d`, `alpha`, `n1`, `n2` | `ncp`, `critical_t`, `df`, `power` |
| `compromise` | `tails`, `d`, `beta_alpha_ratio`, `n1`, `n2` | `ncp`, `critical_t`, `df`, `alpha`, `beta`, `power` |
| `criterion` | `tails`, `d`, `power`, `n1`, `n2` | `ncp`, `critical_t`, `df`, `alpha` |
| `sensitivity` | `tails`, `alpha`, `power`, `n1`, `n2` | `ncp`, `critical_t`, `df`, `d` |

| Alan | G*Power etiketi |
| :--- | :--- |
| `d` | Effect size d |
| `ratio` | Allocation ratio N2/N1 |
| `n1`, `n2` | Sample size group 1, Sample size group 2 |
| `critical_t` | Critical t |
| `df` | Df |

**Örnek:**
```bash
gpower-clone --test t2-indep --mode a-priori --tails 1 --d 0.5 --alpha 0.05 --power 0.95 --ratio 1
```
```json
{"ncp": 3.3166248, "critical_t": 1.6536580, "df": 174, "n1": 88, "n2": 88, "n_total": 176, "actual_power": 0.9514254}
```
*Sensitivity modunda G*Power yalnızca $d \ge 0$ yönünü hesaplar. Sözleşmede yön parametresi yoktur.*

### 4.2 `t-paired` · K2

**G*Power:** `t tests – Means: Difference between two dependent means (matched pairs)`  
**Klinik örnek:** Aynı hastalarda önce ve sonra tansiyon

| Mod | Girdi alanları | Çıktı alanları |
| :--- | :--- | :--- |
| `a-priori` | `tails`, `dz`, `alpha`, `power` | `ncp`, `critical_t`, `df`, `n_total`, `actual_power` |
| `post-hoc` | `tails`, `dz`, `alpha`, `n_total` | `ncp`, `critical_t`, `df`, `power` |
| `compromise` | `tails`, `dz`, `beta_alpha_ratio`, `n_total` | `ncp`, `critical_t`, `df`, `alpha`, `beta`, `power` |
| `criterion` | `tails`, `dz`, `power`, `n_total` | `ncp`, `critical_t`, `df`, `alpha` |
| `sensitivity` | `tails`, `alpha`, `power`, `n_total` | `ncp`, `critical_t`, `df`, `dz` |

| Alan | G*Power etiketi |
| :--- | :--- |
| `dz` | Effect size dz |
| `n_total` | Total sample size (çift sayısı) |

**Örnek:**
```bash
gpower-clone --test t-paired --mode a-priori --tails 1 --dz 0.5 --alpha 0.05 --power 0.95
```
```json
{"ncp": 3.3541020, "critical_t": 1.6802300, "df": 44, "n_total": 45, "actual_power": 0.9512400}
```

### 4.3 `anova-oneway` · K3

**G*Power:** `F tests – ANOVA: Fixed effects, omnibus, one-way`  
**Klinik örnek:** Üç tedavi kolu

| Mod | Girdi alanları | Çıktı alanları |
| :--- | :--- | :--- |
| `a-priori` | `f`, `alpha`, `power`, `groups` | `ncp`, `critical_f`, `df1`, `df2`, `n_total`, `actual_power` |
| `post-hoc` | `f`, `alpha`, `n_total`, `groups` | `ncp`, `critical_f`, `df1`, `df2`, `power` |
| `compromise` | `f`, `beta_alpha_ratio`, `n_total`, `groups` | `ncp`, `critical_f`, `df1`, `df2`, `alpha`, `beta`, `power` |
| `criterion` | `f`, `power`, `n_total`, `groups` | `ncp`, `critical_f`, `df1`, `df2`, `alpha` |
| `sensitivity` | `alpha`, `power`, `n_total`, `groups` | `ncp`, `critical_f`, `df1`, `df2`, `f` |

| Alan | G*Power etiketi |
| :--- | :--- |
| `f` | Effect size f |
| `groups` | Number of groups |
| `critical_f` | Critical F |
| `df1`, `df2` | Numerator df, Denominator df |

**Örnek:**
```bash
gpower-clone --test anova-oneway --mode a-priori --f 0.25 --alpha 0.05 --power 0.95 --groups 5
```
```json
{"ncp": 19.0625, "critical_f": 2.4017397, "df1": 4, "df2": 300, "n_total": 305, "actual_power": 0.9521313}
```

### 4.4 `chi2-contingency` · K4

**G*Power:** `χ² tests – Goodness-of-fit tests: Contingency tables`  
**Klinik örnek:** Tedaviye yanıt oranları

| Mod | Girdi alanları | Çıktı alanları |
| :--- | :--- | :--- |
| `a-priori` | `w`, `alpha`, `power`, `df` | `ncp`, `critical_chi2`, `n_total`, `actual_power` |
| `post-hoc` | `w`, `alpha`, `n_total`, `df` | `ncp`, `critical_chi2`, `power` |
| `compromise` | `w`, `beta_alpha_ratio`, `n_total`, `df` | `ncp`, `critical_chi2`, `alpha`, `beta`, `power` |
| `criterion` | `w`, `power`, `n_total`, `df` | `ncp`, `critical_chi2`, `alpha` |
| `sensitivity` | `alpha`, `power`, `n_total`, `df` | `ncp`, `critical_chi2`, `w` |

| Alan | G*Power etiketi |
| :--- | :--- |
| `w` | Effect size w |
| `df` | Df (girdi; bu ailede çıktı değildir) |
| `critical_chi2` | Critical χ² |

**Örnek:**
```bash
gpower-clone --test chi2-contingency --mode a-priori --w 0.3 --alpha 0.05 --power 0.95 --df 5
```
```json
{"ncp": 19.8, "critical_chi2": 11.0704977, "n_total": 220, "actual_power": 0.9502155}
```

### 4.5 `multireg-r2` · Bonus aile

**G*Power:** `F tests – Linear multiple regression: Fixed model, R² deviation from zero`  
**Klinik örnek:** Risk faktörlerinin açıkladığı varyans

| Mod | Girdi alanları | Çıktı alanları |
| :--- | :--- | :--- |
| `a-priori` | `f2`, `alpha`, `power`, `predictors` | `ncp`, `critical_f`, `df1`, `df2`, `n_total`, `actual_power` |
| `post-hoc` | `f2`, `alpha`, `n_total`, `predictors` | `ncp`, `critical_f`, `df1`, `df2`, `power` |
| `compromise` | `f2`, `beta_alpha_ratio`, `n_total`, `predictors` | `ncp`, `critical_f`, `df1`, `df2`, `alpha`, `beta`, `power` |
| `criterion` | `f2`, `power`, `n_total`, `predictors` | `ncp`, `critical_f`, `df1`, `df2`, `alpha` |
| `sensitivity` | `alpha`, `power`, `n_total`, `predictors` | `ncp`, `critical_f`, `df1`, `df2`, `f2` |

| Alan | G*Power etiketi |
| :--- | :--- |
| `f2` | Effect size f² |
| `predictors` | Number of predictors |

**Örnek:**
```bash
gpower-clone --test multireg-r2 --mode a-priori --f2 0.15 --alpha 0.05 --power 0.95 --predictors 2
```
```json
{"ncp": 16.05, "critical_f": 3.0837059, "df1": 2, "df2": 104, "n_total": 107, "actual_power": 0.9518556}
```

---

## 5. Girdi aralıkları

Bu aralıkların dışındaki bir değer `OUT_OF_RANGE` ile reddedilir. Aralığın içindeki bir değerin kabul edilip edilmeyeceğine G*Power'ın davranışı karar verir; bunu keşfetmek sizin işiniz.

| Alan | Tür | Aralık |
| :--- | :--- | :--- |
| `tails` | tam sayı | `1` ya da `2` |
| `alpha` | ondalık | `0 < alpha < 1` |
| `power` | ondalık | `0 < power < 1` |
| `beta_alpha_ratio` | ondalık | `> 0` |
| `d`, `dz`, `f`, `w`, `f2` | ondalık | `> 0` |
| `ratio` | ondalık | `> 0` |
| `n1`, `n2`, `n_total` | tam sayı | `≥ 2` |
| `groups` | tam sayı | `≥ 2` |
| `df` ($\chi^2$ girdisi) | tam sayı | `≥ 1` |
| `predictors` | tam sayı | `≥ 1` |

---

## 6. Karşılaştırma kuralları

Düzenek, uygulamanızın çıktısını G*Power'ın protokolde gösterdiği değerle karşılaştırır.

| Alan türü | Kural |
| :--- | :--- |
| Tam sayılar: `n1`, `n2`, `n_total`, `df`, `df1`, `df2` | Tam eşleşme |
| Ondalıklar: `ncp`, `critical_*`, `actual_power`, `power`, `alpha`, `beta`, etki büyüklüğü | `|sizin − G*Power| ≤ 1e-6` ya da göreli fark `≤ 1e-6` |
| Hata beklenen vektör | `error` alanı var ve çıkış kodu `0` değil. `code` eşleşirse ek puan. |

G*Power ondalıkları 7 basamakla gösterir (`0.9514254`). Bu basamakta yuvarlanmış değerle tam `double` değeriniz arasında en fazla `5e-8` fark olur, yani tolerans bunu rahatça karşılar. Toleransın içinde kalamıyorsanız sorun yuvarlamada değil, hesaptadır.

### Kapı
Gizli `a-priori` vektörlerinde $N$ alanlarının (`n_total`, varsa `n1` ve `n2`) en az **%90** oranında tam eşleşmesi gerekir. Bu oran tutmazsa MCP ve ajan bonusları puanlanmaz.

---

## 7. MCP sunucusu (bonus)

- **Tek bir araç:** `power_analysis` (geriye dönük uyumluluk için `chi2_power_analysis`, `calculate_chi2_power` ve `chi2_effect_size_from_table` da desteklenir).
- Girdi şeması, CLI ile aynı alan adlarını kullanır. `test` ve `mode` zorunludur; diğer alanlar Bölüm 4'teki tablolara göre zorunlu olur.
- Çıktı, CLI'nin `stdout` JSON'u ile aynıdır ve metin içeriği olarak döner.
- Hata durumunda aynı hata JSON'u döner.
- Hesap mantığı MCP katmanına kopyalanmaz; MCP aynı motoru çağırır.
- **Eşdeğerlik testi zorunlu:** Bölüm 9'daki 25 vektörün her biri için CLI çıktısı ile MCP çıktısı aynı olmalı.

---

## 8. AI ajanı (bonus)

Ajan, MCP aracını çağırır; hesabı asla kendisi yapmaz. Araç çağrılarını `logs/agent_calls.jsonl` dosyasına, her çağrı bir satır olacak biçimde yazın:

```json
{"ts": "2026-10-23T10:15:00+03:00", "question": "<kullanıcının sorusu>", "tool_input": {...}, "tool_output": {...}, "tokens_in": 0, "tokens_out": 0}
```

Değerlendirme sorularında ve loglarda yalnızca kurgusal araştırma senaryoları kullanılır. Gerçek hasta verisi, kimlik bilgisi ya da bir kişiyi tanımlayabilecek herhangi bir bilgi soruya, loga ya da repoya girmez.

---

## 9. Referans vektörleri (açık)

Aşağıdaki 25 vektör, eğitmenin G*Power protokol kayıtlarından birebir alınmıştır (5 aile × 5 mod). Değerler G*Power'ın gösterdiği 7 basamaklıdır. Her satır bir JSON nesnesidir; dosya olarak `public_vectors.jsonl` adıyla kaydedip test düzeneğinizde doğrudan kullanabilirsiniz.

> **Dikkat:** Bu vektörlerin hepsi tek kuyruklu ve her modda tek bir parametre seti var. Gizli vektörler çift kuyruk, eşit olmayan oran, sınır değerler ve geçersiz girdiler içerir. Yalnızca bu 25 vektörü geçmek yetmez.

```jsonl
{"id":"t2-indep/a-priori","input":{"test":"t2-indep","mode":"a-priori","tails":1,"d":0.5,"alpha":0.05,"power":0.95,"ratio":1},"expected":{"ncp":3.3166248,"critical_t":1.6536580,"df":174,"n1":88,"n2":88,"n_total":176,"actual_power":0.9514254}}
{"id":"t2-indep/post-hoc","input":{"test":"t2-indep","mode":"post-hoc","tails":1,"d":0.5,"alpha":0.05,"n1":88,"n2":88},"expected":{"ncp":3.3166248,"critical_t":1.6536580,"df":174,"power":0.9514254}}
{"id":"t2-indep/compromise","input":{"test":"t2-indep","mode":"compromise","tails":1,"d":0.5,"beta_alpha_ratio":1,"n1":88,"n2":88},"expected":{"ncp":3.3166248,"critical_t":1.6606859,"df":174,"alpha":0.0492887,"beta":0.0492887,"power":0.9507113}}
{"id":"t2-indep/criterion","input":{"test":"t2-indep","mode":"criterion","tails":1,"d":0.5,"power":0.95,"n1":88,"n2":88},"expected":{"ncp":3.3166248,"critical_t":1.6676050,"df":174,"alpha":0.0485965}}
{"id":"t2-indep/sensitivity","input":{"test":"t2-indep","mode":"sensitivity","tails":1,"alpha":0.05,"power":0.95,"n1":88,"n2":88},"expected":{"ncp":3.3025887,"critical_t":1.6536580,"df":174,"d":0.4978840}}
{"id":"t-paired/a-priori","input":{"test":"t-paired","mode":"a-priori","tails":1,"dz":0.5,"alpha":0.05,"power":0.95},"expected":{"ncp":3.3541020,"critical_t":1.6802300,"df":44,"n_total":45,"actual_power":0.9512400}}
{"id":"t-paired/post-hoc","input":{"test":"t-paired","mode":"post-hoc","tails":1,"dz":0.5,"alpha":0.05,"n_total":45},"expected":{"ncp":3.3541020,"critical_t":1.6802300,"df":44,"power":0.9512400}}
{"id":"t-paired/compromise","input":{"test":"t-paired","mode":"compromise","tails":1,"dz":0.5,"beta_alpha_ratio":1,"n_total":45},"expected":{"ncp":3.3541020,"critical_t":1.6864315,"df":44,"alpha":0.0493959,"beta":0.0493959,"power":0.9506041}}
{"id":"t-paired/criterion","input":{"test":"t-paired","mode":"criterion","tails":1,"dz":0.5,"power":0.95,"n_total":45},"expected":{"ncp":3.3541020,"critical_t":1.6922637,"df":44,"alpha":0.0488334}}
{"id":"t-paired/sensitivity","input":{"test":"t-paired","mode":"sensitivity","tails":1,"alpha":0.05,"power":0.95,"n_total":45},"expected":{"ncp":3.3417616,"critical_t":1.6802300,"df":44,"dz":0.4981604}}
{"id":"anova-oneway/a-priori","input":{"test":"anova-oneway","mode":"a-priori","f":0.25,"alpha":0.05,"power":0.95,"groups":5},"expected":{"ncp":19.0625000,"critical_f":2.4017397,"df1":4,"df2":300,"n_total":305,"actual_power":0.9521313}}
{"id":"anova-oneway/post-hoc","input":{"test":"anova-oneway","mode":"post-hoc","f":0.25,"alpha":0.05,"n_total":100,"groups":5},"expected":{"ncp":6.2500000,"critical_f":2.4674936,"df1":4,"df2":95,"power":0.4663312}}
{"id":"anova-oneway/compromise","input":{"test":"anova-oneway","mode":"compromise","f":0.25,"beta_alpha_ratio":1,"n_total":100,"groups":5},"expected":{"ncp":6.2500000,"critical_f":1.4272492,"df1":4,"df2":95,"alpha":0.2309247,"beta":0.2309247,"power":0.7690753}}
{"id":"anova-oneway/criterion","input":{"test":"anova-oneway","mode":"criterion","f":0.25,"power":0.95,"n_total":100,"groups":5},"expected":{"ncp":6.2500000,"critical_f":0.6552638,"df1":4,"df2":95,"alpha":0.6245994}}
{"id":"anova-oneway/sensitivity","input":{"test":"anova-oneway","mode":"sensitivity","alpha":0.05,"power":0.95,"n_total":100,"groups":5},"expected":{"ncp":19.5245874,"critical_f":2.4674936,"df1":4,"df2":95,"f":0.4418664}}
{"id":"chi2-contingency/a-priori","input":{"test":"chi2-contingency","mode":"a-priori","w":0.3,"alpha":0.05,"power":0.95,"df":5},"expected":{"ncp":19.8000000,"critical_chi2":11.0704977,"n_total":220,"actual_power":0.9502155}}
{"id":"chi2-contingency/post-hoc","input":{"test":"chi2-contingency","mode":"post-hoc","w":0.3,"alpha":0.05,"n_total":100,"df":5},"expected":{"ncp":9.0000000,"critical_chi2":11.0704977,"power":0.6235846}}
{"id":"chi2-contingency/compromise","input":{"test":"chi2-contingency","mode":"compromise","w":0.3,"beta_alpha_ratio":1,"n_total":100,"df":5},"expected":{"ncp":9.0000000,"critical_chi2":7.6804954,"alpha":0.1747455,"beta":0.1747455,"power":0.8252545}}
{"id":"chi2-contingency/criterion","input":{"test":"chi2-contingency","mode":"criterion","w":0.3,"power":0.95,"n_total":100,"df":5},"expected":{"ncp":9.0000000,"critical_chi2":4.6618452,"alpha":0.4585253}}
{"id":"chi2-contingency/sensitivity","input":{"test":"chi2-contingency","mode":"sensitivity","alpha":0.05,"power":0.95,"n_total":100,"df":5},"expected":{"ncp":19.7801344,"critical_chi2":11.0704977,"w":0.4447486}}
{"id":"multireg-r2/a-priori","input":{"test":"multireg-r2","mode":"a-priori","f2":0.15,"alpha":0.05,"power":0.95,"predictors":2},"expected":{"ncp":16.0500000,"critical_f":3.0837059,"df1":2,"df2":104,"n_total":107,"actual_power":0.9518556}}
{"id":"multireg-r2/post-hoc","input":{"test":"multireg-r2","mode":"post-hoc","f2":0.15,"alpha":0.05,"n_total":100,"predictors":2},"expected":{"ncp":15.0000000,"critical_f":3.0901867,"df1":2,"df2":97,"power":0.9371108}}
{"id":"multireg-r2/compromise","input":{"test":"multireg-r2","mode":"compromise","f2":0.15,"beta_alpha_ratio":1,"n_total":100,"predictors":2},"expected":{"ncp":15.0000000,"critical_f":2.9610326,"df1":2,"df2":97,"alpha":0.0564634,"beta":0.0564634,"power":0.9435366}}
{"id":"multireg-r2/criterion","input":{"test":"multireg-r2","mode":"criterion","f2":0.15,"power":0.95,"n_total":100,"predictors":2},"expected":{"ncp":15.0000000,"critical_f":2.8223021,"df1":2,"df2":97,"alpha":0.0643616}}
{"id":"multireg-r2/sensitivity","input":{"test":"multireg-r2","mode":"sensitivity","alpha":0.05,"power":0.95,"n_total":100,"predictors":2},"expected":{"ncp":15.9319908,"critical_f":3.0901867,"df1":2,"df2":97,"f2":0.1593199}}
```

---

## 10. Alan sözlüğü (klinik anlamı)

Hekimin diliyle bu alanlar ne anlama geliyor? Ajan katmanı kuran takımlar için özellikle önemli.

| Kavram | Alan | Anlamı |
| :--- | :--- | :--- |
| **Hipotez yönü** | `tails` | Araştırmacı yön iddia ediyorsa ("yeni tedavi daha iyi") tek kuyruk (`1`). Yalnızca fark iddia ediyorsa ("fark var") çift kuyruk (`2`). Bu karar veriden önce, etik kurula sunulan hipotezde verilir. |
| **I. tip hata** | `alpha` | Gerçekte fark yokken fark var deme riski. Genellikle `0.05` ya da `0.01`. Araştırmacı belirler. |
| **Test gücü** | `power` | Gerçekte fark varken onu yakalama olasılığı ($1 - \beta$). Genellikle `0.80` ve üzeri. |
| **Etki büyüklüğü** | `d`, `dz`, `f`, `w`, `f2` | Farkın standartlaştırılmış büyüklüğü. Literatürden alınır. Büyüdükçe gereken $N$ küçülür. |

### Cohen'in (1988) geleneksel eşikleri:

| Alan | Küçük | Orta | Büyük |
| :--- | :---: | :---: | :---: |
| `d`, `dz` | `0.2` | `0.5` | `0.8` |
| `f` | `0.10` | `0.25` | `0.40` |
| `w` | `0.1` | `0.3` | `0.5` |
| `f2` | `0.02` | `0.15` | `0.35` |

> **Ajan katmanı için uyarı:** "orta etki" bir kategoridir, bir değer değildir. Kullanıcı yalnızca "orta" dediyse ajan `0.5` değerini sessizce varsaymamalı; varsayımı kullanıcıya açıkça söylemeli ya da onay istemelidir.

---

## 11. Değişiklik politikası

- Sözleşme [anlamsal sürümleme](https://semver.org/lang/tr/) kullanır. Düzeltmeler `1.0.x`, geriye uyumlu eklemeler `1.x.0` olarak yayımlanır.
- Her değişiklik Classroom'da duyurulur ve bu dosyanın sonundaki değişiklik kaydına eklenir.
- Sözleşmede bir belirsizlik bulursanız ödev gönderisine yorum olarak yazın. Belirsizliği ilk bulan takım artı puan alır.

### Değişiklik kaydı

| Sürüm | Tarih | Değişiklik |
| :--- | :--- | :--- |
| `1.0.0` | 2026-10-21 | İlk yayın |
| `1.1.0` | 2026-10-24 | Gölge (Shadow) Sonlu Örneklem Denetimi ve Güven Haritası Araçları Eklendi (`shadow_power_audit`, `generate_shadow_trust_map`) |

---

## 12. Gölge (Shadow) Sonlu Örneklem Denetim Sözleşmesi (`v1.1.0` Uzantısı)

G*Power asimptotik hesaplamalarının sonlu örneklem geçerliliğini denetlemek üzere iki yeni MCP aracı ve karşılık gelen CLI bayrakları (`--shadow-audit`, `--trust-map`) sözleşmeye eklenmiştir:

### 12.1 `shadow_power_audit`
Kombinatoryal multinomial sayım veya Monte Carlo kâhini ile Pearson $X^2$ testinin sonlu güç ve $\alpha$ değerini hesaplar.

- **Girdi:** `arm_outcome_probs` (2D float matris), `alpha` (float), `target_power` (isteğe bağlı), `allocation_ratio` (isteğe bağlı), `arm_sizes` (isteğe bağlı), `design` (`"fixed-arms"` veya `"cross-sectional"`).
- **Çıktı:** `mode`, `design`, `df`, `effect_size_w`, `gpower_n_total`, `asymptotic_power`, `exact_power`, `exact_alpha`, `shadow_gap`, `robust_exact_n`, `verdicts`.

### 12.2 `generate_shadow_trust_map`
Belirli bir tablo yapısında örneklem büyüklüğü $N$ ızgarası üzerinde G*Power'ın asimptotik varsayımlarının çöktüğü tehlike bölgelerini (`UNDERPOWERED`, `ALPHA-INFLATION`, `COCHRAN<5`) haritalar.

