# JARVIS Arquitecto y Experto en Energía

El arquitecto JARVIS es el principal especialista en proyectos. Lee el
contratos de proyecto versionados, capacidades registradas, registros de conocimiento local,
y evidencia actual de la estación de trabajo para producir agentes especializados acotados.
Puede preparar cambios en un árbol de trabajo aislado y validarlos, pero no puede
fusionar, implementar, aprobar o dar fe de forma independiente de sus propios cambios.

El Power Expert es el primer especialista generado. Combina las pestañas de Energía
inventario de host observado con RPM/documentación local y la fuente oficial
política en `plugins/jarvis-power-expert/policy/sources.json`. Sus respuestas deben
identificar la frescura y procedencia de la evidencia, distinguir las recomendaciones de
hechos y presentar únicamente acciones registradas existentes.

La investigación de la red puede consultar las clases fuente oficiales configuradas. persistente
El nuevo contenido permanece visible y auditable: el localizador de origen, el tiempo de recuperación,
El hash de contenido, la versión aplicable y el nivel de autoridad se registran en el
base de datos de conocimiento inmutable existente. El contenido de la comunidad no tiene autoridad.

La conversación muestra el selector de especialistas activo. Seleccionar un especialista añade
su contexto versionado para la tarea de conversación; no otorga autoridad de host
o pasar por alto el corredor, registro de acciones, confirmación, verificación o deshacer
requisitos.

El flujo de trabajo del arquitecto ahora puede crear una propuesta especializada vinculada a un resumen en
`runtime/agent-proposals/`. Las propuestas permanecen inactivas y requieren
revisión y aprobación explícita del usuario antes de que puedan convertirse en un complemento. generado
los agentes solicitan `gpt-5.6-luna` con un razonamiento bajo por política, pero la activación permanece
bloqueado cuando ese modelo no está disponible en el tiempo de ejecución configurado.

Los cambios de paquete actualmente admiten una vista previa de transacciones DNF solo en caché a través de
`dnf --cacheonly --assumeno`. Una vista previa es evidencia para una aprobación posterior, nunca
una aprobación o una instalación. El ejecutor de paquetes privilegiado sigue siendo un
paso de implementación separado.
