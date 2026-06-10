# ⚾ MLB Predictor — Configuración paso a paso

## ¿Qué hace este proyecto?
Todos los días a las **9 AM CST** automáticamente:
1. Obtiene los partidos de hoy de la API oficial de MLB (gratis)
2. Descarga las ERAs de los abridores confirmados
3. Calcula el Top 5 con el modelo de predicción
4. Actualiza el historial con los resultados de ayer
5. Publica la web actualizada en Netlify

**Todo gratis. Sin servidores. Sin configuración diaria.**

---

## Paso 1 — Crear cuenta en GitHub (5 min)
1. Ve a **github.com** y crea una cuenta gratuita
2. Haz clic en **"New repository"** (botón verde)
3. Nombre: `mlb-predictor`
4. Selecciona **"Public"**
5. Haz clic en **"Create repository"**

---

## Paso 2 — Subir los archivos (5 min)
En tu repositorio nuevo, sube estos archivos manteniendo la estructura:

```
mlb-predictor/
├── .github/
│   └── workflows/
│       └── daily_update.yml    ← automatización diaria
├── scripts/
│   └── update_data.py          ← script principal
├── public/
│   ├── index.html              ← tu web
│   └── history.json            ← (se crea automáticamente, sube uno vacío: [])
└── README.md
```

Para subir archivos: en tu repo → **"Add file"** → **"Upload files"**

---

## Paso 3 — Crear cuenta en Netlify (3 min)
1. Ve a **netlify.com** y crea cuenta (con tu cuenta de GitHub)
2. Haz clic en **"Add new site"** → **"Import an existing project"**
3. Conecta con GitHub → selecciona tu repo `mlb-predictor`
4. En **"Publish directory"** escribe: `public`
5. Haz clic en **"Deploy site"**
6. Netlify te dará una URL como: `https://mlb-predictor-abc123.netlify.app`

---

## Paso 4 — Obtener las credenciales de Netlify (5 min)

### Token de Netlify:
1. En Netlify → tu foto de perfil → **"User settings"**
2. → **"Applications"** → **"New access token"**
3. Nombre: `GitHub Actions`
4. Copia el token (solo aparece una vez)

### Site ID de Netlify:
1. En Netlify → tu sitio → **"Site configuration"**
2. Copia el **"Site ID"** (formato: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)

---

## Paso 5 — Agregar los secrets en GitHub (3 min)
1. En tu repo de GitHub → **"Settings"** → **"Secrets and variables"** → **"Actions"**
2. Agrega estos dos secrets:

| Nombre | Valor |
|--------|-------|
| `NETLIFY_AUTH_TOKEN` | El token que copiaste en Netlify |
| `NETLIFY_SITE_ID` | El Site ID que copiaste en Netlify |

---

## Paso 6 — Correr el script por primera vez (2 min)
1. En tu repo de GitHub → pestaña **"Actions"**
2. Verás el workflow **"MLB Predictor — Actualización diaria"**
3. Haz clic en él → **"Run workflow"** → **"Run workflow"** (botón verde)
4. Espera ~2 minutos mientras corre
5. Ve a tu URL de Netlify — ¡ya tienes datos!

---

## ¿Qué pasa cada día?
- A las **9 AM CST** GitHub Actions corre solo
- Actualiza `public/data.json` con los datos del día
- Netlify despliega automáticamente en segundos
- Tú abres la web y ves el Top 5 listo

---

## Agregar momios manualmente (opcional)
El script de Python obtiene automáticamente partidos, abridores y ERAs de la API de MLB. Los momios de FanDuel no tienen API pública gratuita, pero puedes agregarlos editando el archivo `scripts/update_data.py` en la sección de `GAMES` si quieres incluirlos manualmente cada día.

---

## ¿Algo salió mal?
- Ve a tu repo → pestaña **"Actions"** → haz clic en el último run → verás los logs detallados
- El error más común: secrets mal escritos (verifica que no tengan espacios)

---

**Tiempo total de configuración: ~20 minutos**
**Costo mensual: $0**
