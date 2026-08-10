# Applied NLP — From Tokens to Agents

ODTÜ'de bilgisayar mühendisi olmayan mühendisler ve İstatistik öğrencilerine
verilen Applied NLP dersinin herkese açık, etkileşimli, canlı kitabı.
İngilizce sürüm (`en/`) aktif; Türkçe sürüm (`tr/`) çeviri iskeleti olarak
hazır ve aynı pipeline'dan yayınlanıyor.

**Stack:** [Quarto](https://quarto.org) book × 2 (EN + TR) → GitHub Actions →
GitHub Pages. İnteraktifler Observable JS (tarayıcıda çalışır, sunucu yok);
kod bölümleri Python + Jupyter engine + `freeze`.

```
.
├── en/                      # İngilizce kitap (tam Quarto projesi)
│   ├── _quarto.yml          # bölüm listesi, tema, footer — ana kontrol dosyası
│   ├── index.qmd            # landing page (BPE-chip hero)
│   ├── chapters/            # 12 bölüm (05 ve 03 örnek olarak dolu)
│   ├── appendices/          # setup, math refresher, EN↔TR sözlük
│   ├── theme/               # custom-light.scss / custom-dark.scss
│   └── _templates/          # chapter-template.qmd — yeni bölüm için kopyala
├── tr/                      # Türkçe kitap (aynı yapı, çeviri iskeleti)
├── .github/workflows/
│   ├── publish.yml          # main push → render en + tr → Pages deploy
│   └── pr-check.yml         # PR → render kontrolü (deploy yok)
├── index.html               # kök yönlendirme → /en/
└── Makefile                 # preview / render / serve kısayolları
```

## 1) Lokal kurulum ve önizleme

```bash
# Quarto: https://quarto.org/docs/get-started/  (>= 1.10)
pip install -r requirements.txt      # sadece Python'lu bölümler için
make preview                          # EN canlı önizleme (kaydettikçe yenilenir)
make preview-tr                       # TR canlı önizleme
make render && make serve             # iki dili birleştirip localhost:4200'de gez
```

## 2) İçerik değiştirme (günlük iş akışı)

- **Metin düzenleme:** ilgili `.qmd` dosyasını aç, yaz, kaydet — önizleme
  anında yenilenir. Bölümlerdeki `<!-- TODO(draft): ... -->` blokları yazım
  planıdır; render'da görünmez.
- **Bölüm ekleme:** `en/_templates/chapter-template.qmd` dosyasını
  `en/chapters/NN-isim.qmd` olarak kopyala → `en/_quarto.yml` içindeki
  `chapters:` listesine doğru part altına ekle. Silme/sıralama da aynı
  listeden.
- **İmza stiller:** vurgu için `[önemli ifade]{.hl}` (fosforlu kalem
  efekti); interaktifleri `::: {.anlp-widget}` bloğu içine al.
- **Çapraz referans:** başlık çapasıyla `@sec-transformers`; kaynakça için
  `en/references.bib`'e ekle, metinde `[@vaswani2017attention]`.
- **Tema:** tüm renk/font kararları `en/theme/custom-light.scss` başındaki
  altı token'da. TR tarafı kopya kullanır — değiştirince
  `cp en/theme/*.scss tr/theme/` ile eşitle.

## 3) İnteraktifler (OJS)

Örnekler `en/chapters/06-transformers.qmd` içinde: attention-head explorer
ve temperature/top-k/top-p sampling explorer. Desen: `viewof x =
Inputs.range(...)` girdileri → hesap hücresi → `Plot.plot(...)`. Tamamı
tarayıcıda çalışır; build sırasında Python gerekmez. Yeni widget için bu
bloklardan birini kopyalayıp veriyi değiştir.

## 4) Python'lu bölümler ve `freeze`

`execute: freeze: auto` açık: bir bölümü lokalde render ettiğinde sonuçlar
`en/_freeze/` altına yazılır ve **commit edilir**. CI notebook'ları yeniden
çalıştırmaz — publish hızlı ve deterministik kalır. Kod hücresini
değiştirdiğinde lokalde bir kez `quarto render en` çalıştırıp `_freeze/`
değişikliklerini commit etmen yeterli.

## 5) Yayınlama

Kurulum tamamlandı — repo [bbardakk/metu-applied-nlp](https://github.com/bbardakk/metu-applied-nlp),
Pages kaynağı **GitHub Actions**. `main`'e her push iki dili render edip
yayınlar:

| URL | İçerik |
|---|---|
| <https://bbardakk.github.io/metu-applied-nlp/> | köke gelen `/en/`'e yönlenir |
| <https://bbardakk.github.io/metu-applied-nlp/en/> | İngilizce sürüm |
| <https://bbardakk.github.io/metu-applied-nlp/tr/> | Türkçe sürüm |

İki workflow var:

- `.github/workflows/publish.yml` — `main` push'unda render + Pages deploy.
- `.github/workflows/pr-check.yml` — pull request'te iki dili de render eder,
  deploy etmez. Kırık build main'e giremez.

**Custom domain:** Settings → Pages → Custom domain; `public/` köküne CNAME
workflow'da eklenebilir (assemble adımına `echo "alan.adi" > public/CNAME`).

## 6) Yorumlar (giscus)

Repo public olduktan sonra: Discussions'ı aç → giscus app'i kur →
[giscus.app](https://giscus.app)'ten `repo-id`/`category-id` al →
`en/_quarto.yml` içindeki hazır `comments:` bloğunun yorumunu kaldırıp
değerleri yapıştır. TR için aynısını `tr/_quarto.yml`'a kopyala.

## 7) Türkçe sürümü büyütme

1. Terim önce `en/appendices/c-glossary.qmd`'de sabitlenir (tek doğruluk
   kaynağı), sonra çeviri yapılır.
2. `en/chapters/NN-xxx.qmd` → `tr/chapters/NN-xxx.qmd` olarak çevir,
   `tr/_quarto.yml` `chapters:` listesine ekle.
3. `tr/index.qmd`'deki çeviri durumu tablosunu güncelle.
4. Sidebar'daki dil değiştirici (🌐) iki yönü de bağlıyor; kök `/`
   yönlendirmesi `index.html`'de.

## 8) Viral dağıtım disiplini (her bölüm yayını)

- Bölümün "hero" görselini/interaktifini tek başına paylaşılabilir tut —
  paylaşılan şey link'tir, kitap trafiği ondan gelir.
- `en/index.qmd` sonundaki **Updates** tablosuna satır ekle (changelog).
- Duyuru seti: X/LinkedIn kısa thread + Show HN + r/MachineLearning;
  başlıkta hedef kitleyi söyle ("for engineers who aren't CS majors").

## Lisans

Metin **CC BY 4.0**, kod **MIT** — ayrıntı `LICENSE` dosyasında.
