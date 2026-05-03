# cirugiademama.cl

Sitio informativo sobre cáncer de mama y enfermedades benignas de la mama, de la **Dra. Marcia Valenzuela**. Construido con Jekyll y publicado en GitHub Pages bajo el dominio `cirugiademama.cl`.

La especificación de comportamiento del sitio (modelo de contenido, ciclo de curación, accesibilidad y SEO) está en [`cirugiademama.allium`](cirugiademama.allium).

## Requisitos

- **Ruby** ≥ 3.0 (recomendado vía `rbenv` o `asdf`).
- **Bundler** (`gem install bundler`).
- **Python** ≥ 3.10 — sólo para el script de migración (no para servir el sitio).

## Levantar el sitio en local

```bash
# 1. Instalar dependencias Ruby (sólo la primera vez)
bundle install

# 2. Servir con autorrecarga en http://127.0.0.1:4000
bundle exec jekyll serve --livereload

# Variantes útiles:
bundle exec jekyll serve --drafts          # incluye _drafts/
bundle exec jekyll serve --host 0.0.0.0    # acceso desde otros dispositivos en la red
bundle exec jekyll build                   # genera _site/ sin servir
```

El sitio queda en <http://127.0.0.1:4000>. Cualquier cambio en `.md`, `.html`, `_data/*.yml` o `_includes/` se recarga automáticamente. Cambios en `_config.yml` requieren reiniciar el servidor.

## Estructura del repositorio

```
.
├── _config.yml              # configuración Jekyll
├── _data/navigation.yml     # menú principal y secundario
├── _layouts/                # plantillas HTML
├── _includes/               # head, header, footer
├── _pages/                  # páginas curadas (publicables)
├── _drafts/                 # output del scrape, pendiente de revisión
├── _glossary/               # entradas del glosario (collection sin output)
├── assets/
│   ├── css/main.scss
│   ├── js/{glossary,color-scheme}.js
│   ├── images/              # imágenes descargadas desde el sitio antiguo
│   └── favicon{.ico,.png}, apple-touch-icon.png
├── glosario/glossary.json   # índice del glosario, consumido por glossary.js
├── index.html               # home
├── glosario.html            # listado completo
├── 404.html
├── robots.txt
├── CNAME                    # cirugiademama.cl
├── scripts/migrate.py       # WXR → Jekyll (one-shot)
├── cirugiademama.allium     # especificación del sitio
└── cncerdemama.WordPress.*.xml  # export legado (no se publica)
```

## Migración desde WordPress

El sitio se migra una sola vez desde el export `cncerdemama.WordPress.2026-05-02.xml`.

```bash
# Instalar dependencias Python
python3 -m pip install requests markdownify beautifulsoup4 lxml

# Ejecutar la migración
python3 scripts/migrate.py cncerdemama.WordPress.2026-05-02.xml

# Variantes:
python3 scripts/migrate.py <xml> --dry-run     # no escribe archivos
python3 scripts/migrate.py <xml> --no-images   # no descarga imágenes
```

Resultado:

- `_drafts/<slug>.md` — un draft por cada página publicable, con front matter completo y `status: scraped`.
- `_glossary/<slug>.md` — los 47 términos del glosario, listos para servir tooltips.
- `assets/images/<archivo>` — imágenes descargadas y reescritas en los Markdown.

### Flujo de curación

1. **Revisar** cada archivo en `_drafts/`. Editar `description` (≤160 caracteres, importante para SEO), opcionalmente `lead`, ajustar contenido.
2. **Mover** el archivo a `_pages/<slug>.md` cuando esté listo. Cambiar `status: scraped` → `status: published`.
3. **Levantar el sitio en local** y verificar que la página se ve bien y los tooltips de glosario funcionan.
4. **Commit y push**. GitHub Pages reconstruye automáticamente.

## Despliegue

GitHub Pages reconstruye y despliega automáticamente al hacer push a la rama por defecto. Requisitos previos:

1. Repositorio público (necesario para dominio personalizado en plan gratuito).
2. En **Settings → Pages**, seleccionar `Deploy from branch` y la rama por defecto.
3. El archivo [`CNAME`](CNAME) ya contiene `cirugiademama.cl`.
4. En el panel del registrador de dominios:
   - Apuntar el A record de `cirugiademama.cl` a las IPs de GitHub Pages: `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`.
   - Apuntar el CNAME `www.cirugiademama.cl` a `<usuario>.github.io`.
5. En **Settings → Pages**, marcar **Enforce HTTPS** una vez que el certificado se haya emitido (puede tardar minutos a horas).

## Accesibilidad

El sitio busca cumplir **WCAG 2.1 AA**:

- Contraste mínimo 4.5:1 (texto normal) y 3:1 (texto grande), en ambos esquemas de color.
- Navegación operable por teclado, foco visible, skip-link.
- Tooltips de glosario activables por click, tap y teclado; nunca dependen del hover.
- Tamaño base 18px, escala respetando la preferencia del usuario.
- `prefers-reduced-motion` deshabilita transiciones.

Verificar con: Lighthouse, axe DevTools, navegación con sólo teclado, NVDA/VoiceOver.

## SEO

- `jekyll-seo-tag` genera title, description, canonical, Open Graph, Twitter cards y JSON-LD por página.
- `jekyll-sitemap` genera `/sitemap.xml`.
- `robots.txt` permite todos los crawlers y enlaza el sitemap.
- Cada página debe tener `description` (≤160 caracteres) en su front matter para que el meta description sea óptimo.
- Tipos schema.org por página: `MedicalWebPage` (default), `Physician` (`/marcia/`), `DefinedTermSet` (`/glosario/`), `FAQPage` (`/preguntas-y-respuestas/`).

## Licencia

Contenido: © Dra. Marcia Valenzuela. Todos los derechos reservados.
Código del sitio (layouts, estilos, scripts): MIT.
