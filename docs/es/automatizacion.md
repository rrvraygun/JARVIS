# Diseño de automatización

Utilice `codex exec` con zona de pruebas de solo lectura, modo de aprobación explícita, efímero
sesiones, JSONL cuando se requiere un seguimiento completo y un esquema de salida para datos estables.
resultados. Configure el servidor Jarvis MCP como `required` para que la automatización falle.
que funcionar sin políticas ni herramientas de auditoría.

La automatización programada es solo de observación de forma predeterminada. Puede producir alertas y
planes listos para aprobación, pero no puede interpretar una aprobación conversacional anterior como una
nueva autorización de cambio. Cada ejecución de mutación necesita un resumen de acción coincidente,
objetivos, actor, vencimiento, versión del procedimiento, ventana de mantenimiento y recuperación.

Almacene mensajes y esquemas en el control de versiones. Anclar la versión del Codex/complemento en
automatización de la producción, validar actualizaciones en un entorno desechable y conservar
Seguimientos JSONL según el ciclo de vida de los datos. Nunca exponga claves API a trabajos que
ejecutar código de repositorio que no es de confianza.
