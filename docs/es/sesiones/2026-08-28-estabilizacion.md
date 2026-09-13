# 2026-08-28 sesión de estabilización

**Objetivo:** comenzar la versión de saneamiento y auditoría del código base de desarrollo de JARVIS 0.7.0.

## Cambios en esta sesión

- Se agregaron controles de ingreso de protocolo y entorno de App Server delimitados.
- Se eliminó la aprobación automática de comandos de red y el asistente sudo/DNF obsoleto.
- Persistencia de conversación reforzada, privacidad del portapapeles, liquidación de cancelación,
  escrituras de objetivos de energía, verificación genérica de anexos al libro mayor y diagnósticos seguros.
- Se agregó el primer índice de documentación viva, mapa de arquitectura, generado.
  inventario, informe de auditoría, trabajo pendiente, herramientas de desarrollo bloqueadas y local
  esqueleto de puerta de calidad.

## Evidencia

- El archivo previo al cambio y la línea de base se registran en `audits/2026-08-28-codebase-audit.md`.
- Se aprobaron las pruebas enfocadas de servidor de aplicaciones/sesión/evento/conversación.
- Se pasaron las pruebas de mutación enfocada/poder/sin cabeza.
- La suite TUI completa pasó fuera del sandbox: 223 pruebas en 121,667 segundos
  sobre el estado final del paquete/fuente de cancelación.
  Dentro del sandbox restringido, la misma suite pasó 220 pruebas y solo el
  El entorno denegó la prueba de vinculación de socket Unix esperada.
- Tres revisiones independientes de Luna de solo lectura encontradas y correcciones guiadas para el protocolo
  privacidad, instantáneas de persistencia, pedidos del ciclo de vida del paquete, cancelación
  liquidación, identidad del objetivo de poder, documentación y cobertura de validación.
- Un intento completo de control de calidad expuso archivos de caché transitorios de Ruff/Mypy en el
  manifiesto de liberación. El generador ahora excluye los cachés de herramientas; el regenerado
  El manifiesto de origen verifica 728 entradas propias.
- El primer intento de acceso completo también excedió el límite de tiempo de ejecución porque
  ejecutó la suite TUI completa dos veces. El perfil exterior ahora posee esa suite y
  le dice al validador heredado anidado que omita solo la invocación duplicada.
- El seguimiento final del validador expuso un esquema de controlador de VM obsoleto. Ahora admite
  solo la línea base de solo contrato o el estado de solo lectura H1 Tier-0 documentado.
- Se conciliaron esquemas de observación y acción relacionados con los mismos actuales.
  estado H1; sus mutaciones, privilegios y negaciones de redes permanecen sin cambios.
- Se aprobó el perfil de calidad rápido final. El validador de contratos/fichas heredadas
  también pasó con la parte de TUI ya completada explícitamente omitida a
  Evite la ejecución duplicada.

## Riesgo no verificado y residual

- Validación completa de la versión, archivo de documentación, extracción más amplia del flujo de trabajo,
  Endurecimiento de la raíz del almacén de MCP, aplicación del umbral de cobertura y nivel medio/bajo
  Los hallazgos del análisis estático permanecen abiertos.
- No se produjo ningún paquete de host en vivo, energía, servicio, Polkit o activación de ayuda.

## Revertir

Restaure los archivos del proyecto desde el archivo de origen registrado en la auditoría fechada.
No restaure, rote, trunque ni elimine diarios de ejecución ni datos de usuario.
