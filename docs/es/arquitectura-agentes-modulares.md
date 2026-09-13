# Arquitectura modular especializada

**Estado:** implementación activa
**Actualizado:** 2026-08-29

## Propósito

JARVIS es un sistema especializado seleccionado por el usuario. El usuario elige al especialista
desde el selector de Conversaciones; una solicitud nunca cambia silenciosamente de especialistas.
Cada especialista proporciona instrucciones limitadas, referencias de conocimientos, registros
referencias de herramientas, política de contexto, política de red y política de mutación. el
El plano central de intermediario/control sigue siendo la única autoridad que puede admitir,
aprobar, reservar o ejecutar una operación.

## Especialistas actuales

| Especialista | Selección | Responsabilidad |
| --- | --- | --- |
| JARVIS Arquitecto | seleccionable | Orientación general sobre proyectos, sistemas y diseño especializado |
| Especialista en instalación | seleccionable | Inventario de paquetes de Fedora, explicaciones, instalación/eliminación exacta de DNF, verificación, recuperación y reversión |
| Experto en energía | seleccionable | Inventario de energía de hardware/software, telemetría, planificación de perfiles, cambios de perfiles aprobados y recomendaciones de paquetes con transferencia de especialista en instalación |

Los descriptores especializados se encuentran en complementos locales revisados en
`plugins/*/specialist.json`. La TUI los carga a través
`tui/src/jarvis_tui/agent_registry.py`. Descriptores no válidos y no registrados
Las referencias de herramientas se ignoran o rechazan en caso de error.

## Superficies de usuario

El espacio de trabajo normal conserva descripción general, conversación, iluminación, energía,
Paquetes, cronograma y operaciones. Acciones, Conocimiento, Plan y Aprobaciones
ya no son pestañas principales:

- las acciones registradas son metadatos de herramientas internas;
- el conocimiento es recuperación y evidencia propiedad de especialistas;
- el plan/progreso se proyecta en la conversación y en los registros de estado;
- la aprobación sigue siendo una decisión modal del plano de control de un solo uso.

La pestaña Agentes aparece inmediatamente después de Conversación. Se muestra operativo
resúmenes de agentes, herramientas registradas, referencias de conocimientos, política de contexto,
política de red/mutación y estado de la versión. Ofrece tanto estructurado como crudo.
Edición de definiciones JSON.

## Definición de ciclo de vida

Solo se pueden editar los ID de agentes instalados revisados. Una edición se lleva a cabo primero como
borrador en memoria, luego validado para esquema, límites, valores de política y
referencias de herramientas registradas. La diferencia exacta se muestra en un modal de confirmación.
Una nueva aprobación activa atómicamente la definición. el anterior activo
La definición se archiva en el directorio de estado de tiempo de ejecución exclusivo del propietario y se puede
restaurado con otra aprobación de un solo uso.

El editor puede seleccionar herramientas registradas existentes pero no puede crear archivos ejecutables.
comandos o eludir privilegios centrales, red, aprobación, auditoría o recuperación
reglas. Las definiciones de agentes son configuración, no autoridad.

## Contrato de contexto

El especialista seleccionado recibe la conversación completa, visible y acotada.
transcripción más su contexto específico del especialista, evidencia inmediata y limitada.
La transcripción contiene todos los roles visibles, incluidos los mensajes de usuario,
aclaraciones, preguntas/opciones de JARVIS, resultados de acciones, estado del sistema y
respuestas de los agentes. Las transcripciones de especialistas persistentes utilizan conversaciones existentes
límites y redacción terminal. Razonamiento privado, credenciales, tokens y
Los datos ambientales confidenciales no redactados nunca se conservan.

El ID y la versión del especialista seleccionado se adjuntan al contexto de la tarea y al
La última selección se restaura desde el estado de ejecución exclusivo del propietario después del reinicio.

## Contrato de especialista en instalación

La pestaña Paquetes y las operaciones de conversación relacionadas con los paquetes utilizan el mismo
backend del paquete limitado. El especialista en instalación está limitado al actual
Flujo de trabajo de Fedora: raíces RPM exactas, inspección de catálogos instalados/en caché,
vistas previas de DNF de solo caché, verificaciones de instalación aditiva y eliminación limitada, el
asistente raíz registrado, aprobación exacta de un solo uso, verificación posterior al estado y
recuperación/reversión aprobada por separado. Descargas oficiales, repositorio
Los cambios, las opciones arbitrarias de DNF y otros administradores de paquetes permanecen fuera de este
especialista hasta que se diseñe por separado.Las inspecciones de paquetes en lenguaje natural utilizan el especialista seleccionado y texto recién escrito
Pruebas del PCM. La vista Paquetes sigue siendo una superficie de inventario local separada. el
MCP orientado al modelo rechaza herramientas fuera de su alcance de proceso propiedad del corredor, incluso cuando
un agente conoce el nombre de la herramienta. El alcance se establece después de la admisión y se revoca.
al finalizar el turno. Ninguna herramienta orientada al modelo puede activar una lección.

## Reglas de extensión

Los nuevos especialistas ingresan a través de complementos locales revisados. Un descriptor puede declarar
acceso a la red sólo a través de su valor político explícito; uso de red no declarado
no está disponible. Los traspasos, cuando se agregan posteriormente, pasan por el coordinador y
preservar la transcripción visible. Un especialista no puede otorgar autoridad para
otro.
