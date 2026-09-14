# Registro de cambios

## 2026-09-14 — Contexto y ejecución de especialistas

- El preflight no determinista usa un hilo efímero y solo transfiere su
  evaluación tipada a la conversación persistente.
- Los snapshots recalculan digest tras recortar, las peticiones aceptadas siguen
  conocidas aunque fallen y la contabilidad de preflight queda separada.
- El catálogo MCP se inicializa antes del App Server y se limita al especialista
  seleccionado; durante preflight las llamadas se rechazan.
- Los envelopes de explicación son compactos y la compactación condicionada
  espera el item autoritativo `contextCompaction`.
- `New` reinicia la actividad visible y separa el hilo anterior para que una
  conversación nueva no reutilice contexto antiguo.
- Al cargar una conversación guardada se restaura su resumen de uso y el nuevo
  turno se muestra como incremento, no como un baseline aislado.

## 2026-09-13 — Context accounting

Medición de contexto: conservar cifras de respuesta/hilo/petición y caché, corregir estimación de contexto y compactar texto repetido. Regresiones y comparación real de explicación validadas; sin ahorro demostrado ni paridad con CLI.

Aislamiento de contexto y herramientas por especialista: filtrar el catálogo MCP
por scope, rechazar llamadas durante el preflight no ejecutable y enviar una vez
por digest/hilo el contrato personalizado antes de usar una referencia.

Todos los cambios notables en JARVIS se registran aquí. Las fechas utilizan Europa/Madrid local
hora en la que el registro de origen proporcionó marcas de tiempo locales.

## [Inédito] — 2026-09-13

### Agregado

- GitHub Agent, seleccionable en Agents y Conversation, con inspección Git local
  acotada, preflight de publicación y planes de operación exactos.
- El adaptador GitHub CLI acotado valida repositorios, PR, issues, releases y
  artefactos de Actions; si el conector no está disponible, falla de forma segura.
- El inglés es ahora el idioma principal de la documentación. Un español reflejado
  El árbol de documentación está disponible en `docs/es/`.
- Vistas de dominio limpias para Salud, Desarrollo, Red, Seguridad y Recuperación,
  con una vista JSON sin formato retenida detrás de un selector por dominio.
- Explicaciones por campo `[i]` que abren un breve diálogo de información flotante.
- Selección global de modelos para todos los especialistas: GPT-6 Astra, GPT-5.6 Sol, GPT-5.6
  Terra, GPT-5.6 Luna y GPT-5.5.
- Selección global de razonamiento-esfuerzo: Ninguno, Mínimo, Bajo, Medio, Alto, Xalto,
  Max y Ultra.
- Selección de ventana de contexto global: Auto, 8k, 16k, 32k, 64k, 128k, 256k, 512k,
  Tokens de 800k, 1M y 1,05M.
- Configuración global persistente en `runtime/jarvis-model.json`, aplicada a nuevos
  giros sin cambiar un giro activo.
- Marcador de contexto en vivo debajo de la actividad del agente, que muestra usado/ventana/restante
  porcentaje cuando el uso del token de App Server está disponible y `unavailable` antes
  el primer evento de uso.
- Análisis del uso de tokens del servidor de aplicaciones anidado para `thread/tokenUsage/updated`, incluido
  `tokenUsage.total.totalTokens` y `modelContextWindow`.
- El uso del contexto se restablece a cero después de la restauración del punto de control y nuevas conversaciones.
- Modo de ejecución de terminal normal con E/S de terminal de usuario heredada y sin JARVIS
  límites de tiempo de ejecución/recursos, separados de los flujos de trabajo de carga aislados.
- Contratos de ayuda de transacciones DNF y arranque revisados desde la raíz con políticas de Polkit,
  reservas exactas de un solo uso, recibos inmutables y revisión de recuperación independiente.
- Sondeo persistente del servidor de aplicaciones autenticado y terminal normal inofensivo visible
  prueba de humo.
- Panel de actividad en vivo dentro de Conversación con fragmentos de transmisión, nombre de herramienta,
  consulta, estado y tiempo transcurrido.

### Cambiado

- La verificación previa del servidor de aplicaciones ahora utiliza el protocolo `readOnly` actual con
  `networkAccess=false`; Se eliminó el `readOnly.access` obsoleto.
- La inicialización declara `experimentalApi=true` para soporte de aprobación granular.
- Las rutas de inspección de paquetes exponen automáticamente la información del especialista en instalación.
  capacidad de solo lectura `inspect_packages` existente y vincular términos de consulta completos.
- Las observaciones faltantes permanecen en estado de actividad y ya no se inyectan duplicadas.
  texto predefinido en la conversación.
- Los controles del punto de control de conversación utilizan un selector modal estable y ya no
  alterar la geometría de la conversación.
- El carril de acción de conversación está agrupado debajo del selector especializado; su posición
  permanece fijo cuando se abre el selector.
- El manifiesto de publicación y el inventario de origen resuelven correctamente las exclusiones relativas a
  la raíz del paquete y rechazar los manifiestos vacíos.

### Validación

- Se pasan las pruebas de App Server, sesión, corredor, actividad, Clean/Raw y especialistas
  el candidato preparado; el manifiesto de lanzamiento se regenera después de la documentación
  cambios.
- Verificación de integridad del repositorio Ristic proporcionada por el usuario completada sin errores;
  No se realizó ninguna mutación de paquete, arranque o disco durante el desarrollo.

### Límites conocidos

- La publicación de GitHub utiliza el control remoto SSH del repositorio y la rama `main`.
- Mutaciones reales de paquetes/arranque privilegiados y un turno de agente completamente autenticado
  seguir siendo pruebas de implementación separadas; Las pruebas de fijación no los certifican.
- El uso del contexto no está disponible hasta que el servidor de aplicaciones envíe un evento de uso; la interfaz de usuario
  no estima el uso de los caracteres.

## Registros históricos

Los registros de auditoría y de fase anterior permanecen bajo `docs/` y `docs/sessions/`. ellos
describir las decisiones de diseño y la evidencia en sus fechas registradas. Consultar
`docs/current-product-state.md` para conocer el comportamiento actual.
