# Flujo de trabajo de Power impulsado por agentes - 2026-08-30

## Resultado

Las solicitudes de dominio de poder del Power Expert seleccionado ahora ingresan a una aplicación real
El agente del servidor gira en lugar de ser respondido por el analizador de palabras clave local. el
El agente posee aclaraciones, decisiones de perfil, recomendaciones de control,
análisis de compensaciones y explicaciones. El agente recibe al especialista.
contrato y utiliza herramientas MCP registradas para inventario limitado, telemetría,
capacidades, validación de borradores de perfil, preparación de aprobación y recuperación
propuestas.

Power Expert utiliza una zona de pruebas de solo lectura y no recibe comandos arbitrarios
aprobación. La TUI revalida los borradores de perfil generados por el agente antes de
se muestran. Un marcador de activación de agente puede abrir la aprobación exacta existente
revisión, pero el marcador en sí no tiene autoridad. El Jarvis de un solo uso existente
aprobación, autorización del sistema operativo, ayudante registrado, verificación independiente y
Los límites de recuperación siguen siendo la autoridad de mutación.

La TUI presenta las solicitudes de obtención de MCP como una respuesta única separada
Permitir una vez/Rechazar/Cancelar diálogo. Los turnos de energía utilizan una política de aprobación granular
que permite esas decisiones de MCP mientras deshabilita la regla de comando y la zona de pruebas
aprobación; el turno en sí sigue siendo de sólo lectura. La respuesta se limita a la
solicitud de MCP pendiente y no otorga autoridad de mutación del host.

La superficie Power MCP está registrada en el servidor MCP de control Jarvis. Perfil
planificar y aplicar propuestas rechazan controles no revisados, estados previos obsoletos y
valores no soportados. La herramienta de solicitud es intencionalmente solo para propuestas hasta que
El límite de aprobación de TUI invoca al ayudante registrado.

El lanzador canónico ahora exporta el `runtime/codex-home` del checkout, cuyo
La configuración MCP requerida explícitamente `jarvis_control` habilita las herramientas eléctricas.
Esto evita que el perfil global del Codex de un usuario inicie la TUI sin la
servidor Power MCP del repositorio.

## Evidencia de validación

- Pruebas de Focused Power, especialista, App Server y presentación: 19 aprobadas.
- Descubrimiento completo del control de calidad de TUI: se alcanzaron 250 pruebas; 249 aprobados y 1 sandbox
  Se produjo un error de entorno cuando un dispositivo intentó vincular un socket Unix.
  (`PermissionError: [Errno 1] Operation not permitted`).
- Formato Ruff y pelusa pasados ​​para archivos Python modificados.
- Lista de herramientas MCP expuesta: `power_inventory`, `power_telemetry`,
  `power_capabilities`, `power_profile_plan`, `power_profile_apply`,
  `power_profile_rollback` y `stage_registered_power_action`.
- Se aprobó el contrato de documentación y el inventario de base de código regenerado; la liberación
  manifiesto fue regenerado y verificado.

Sin configuración de energía del host, transacción de paquetes, servicio o privilegios.
La operación se ejecutó durante esta implementación.
