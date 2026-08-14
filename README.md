# ⚡ VólticvS — Asesor Energético Inteligente (Fullstack MVP)

Plataforma interactiva para el diagnóstico de consumo eléctrico, estimación de ahorro y recomendaciones energéticas personalizadas mediante IA.

---

## 🚀 Mejoras y Actualizaciones (Rama: `feature/fullstack-update`)

Se reestructuró la aplicación conectando el motor del agente con una **interfaz de usuario (UI/UX) optimizada**, reduciendo la carga cognitiva y acelerando la recolección de datos:

### 🎨 1. Experiencia de Usuario (Frontend & UX)
- **Navegación Categorizada por Pestañas:** Selección intuitiva de artefactos organizados por módulos (*Línea Blanca, Entretención & Oficina, Hogar, Iluminación y Mis Artefactos*).
- **Reducción de Carga Cognitiva:** Formulario simplificado en pasos (*Paso 1: Ubicación y Clima → Paso 2: Método de Ingreso de Consumo*).
- **Gestión Geográfica:** Selectores de **País y Provincia/Estado** para alimentar la estimación climática del modelo.
- **Medidor Dinámico en Tiempo Real:** Cálculo instantáneo de kWh/mes conforme se agregan o quitan equipos.
- **Vista de Impresión Limpia:** Estilos CSS (`@media print`) optimizados para exportar reportes en PDF/Hoja Blanca.

### ⚙️ 2. Optimización de API y Lógica de Negocio
- **Estandarización de Payloads:** Integración directa con el endpoint REST (`/api/analisis-energetico`).
- **Mapeo Directo sin Sobrecarga de LLM:** Selección por botones (vivienda, rangos de consumo) asignando valores de forma inmediata para minimizar llamadas innecesarias al modelo.
- **Manejo de Errores e Idioma:** Validaciones de formularios e interfaces totalmente adaptadas al español.

---

## 🛠️ Tecnologías Utilizadas

| Capa | Stack |
|---|---|
| **Backend** | Python 3.12+, Flask, LangChain, Groq API (Llama-3.3-70b) |
| **Frontend** | HTML5, CSS3 (dark mode / CleanTech), JavaScript ES6+ |
| **Datos** | JSON de referencia energética, cálculo de consumo determinista |
| **Infraestructura** | python-dotenv, pdfplumber, Werkzeug |

---

## ⚙️ Ejecución Local

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/alejolanda/challengerRagAlura.git
   cd challengerRagAlura
   ```

2. **Crear y activar entorno virtual:**
   ```bash
   python -m venv venv
   # Linux / macOS:
   source venv/bin/activate
   # Windows:
   venv\Scripts\activate
   ```

3. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar variables de entorno:**
   ```bash
   cp .env.example .env
   # Editar .env y añadir tu GROQ_API_KEY real
   ```

5. **Lanzar la aplicación:**
   ```bash
   python app.py
   ```
   La app estará disponible en `http://localhost:5000`

---

## 🔐 Variables de Entorno

| Variable | Descripción | Requerida |
|---|---|---|
| `GROQ_API_KEY` | Clave de API de Groq | ✅ Sí |
| `GROQ_MODEL` | Modelo a usar (default: `llama-3.3-70b-versatile`) | No |
| `PORT` | Puerto del servidor (default: `5000`) | No |
| `FLASK_DEBUG` | Modo debug (`0` en producción) | No |

> ⚠️ **Nunca subas el archivo `.env` a Git.** Ya está incluido en `.gitignore`.

---

## 📁 Estructura del Proyecto

```
challengerRagAlura/
├── app.py                  # Servidor Flask y endpoints REST
├── src/
│   └── calculos.py         # Lógica de cálculo determinista
├── data/
│   └── consumo_referencia.json  # Referencia de consumo por artefacto y país
├── static/
│   ├── css/style.css       # Estilos dark mode (CleanTech)
│   └── js/app.js           # Lógica de interfaz y comunicación con API
├── templates/
│   └── index.html          # Interfaz principal (SPA con pestañas)
├── uploads/                # Archivos temporales (ignorado por Git)
├── .env.example            # Plantilla de variables de entorno
├── requirements.txt
└── README.md
```