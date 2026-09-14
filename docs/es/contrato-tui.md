# contrato TUI

La TUI es una superficie de presentación y consentimiento, nunca una autoridad o un caparazón. eso
utiliza las mismas operaciones de plano de control escritas que el Codex en lenguaje natural y no puede
omita políticas, aprobación, zona de pruebas, evidencia o puertas de auditoría.

La arquitectura detallada, el lenguaje natural/canal de acción compartido, la entrega.
Las fases y las pruebas de aceptación se definen en `tui-implementation-plan.md`.

## Límite de implementación actual

`tui/` tiene una canalización controlada por un corredor. La captura y la presentación preceden
admisión: una entrada de usuario se representa como `resolving_intent` y se retiene el envío
para esa tarea hasta un resultado final o de aclaración. Un segundo Enter o Enviar
se rechaza sin borrar el borrador o poner el trabajo en cola.

Las solicitudes en lenguaje natural ingresan primero a un planificador local conservador para áreas acotadas.
lecturas del sistema de archivos y candidatos de mutación exacta. Preguntas sobre inspección de paquetes
ingrese el turno de especialista con capacidad de paquete seleccionado para que el agente posea la evidencia
selección, filtrado, explicación y recomendación a través de registros
herramientas de paquete de solo lectura. Las solicitudes de Power Expert son una excepción intencional a
el planificador local también: ingresan el turno del agente Power Expert seleccionado para
el agente posee aclaración, planificación, recomendación y explicación; el
El agente utiliza herramientas eléctricas escritas registradas en lugar de un planificador de palabras clave local.
Las solicitudes exactas de lista/lectura/búsqueda del sistema de archivos local utilizan el ejecutor local limitado
y nunca cree un turno de App Server, invoque Bash ni solicite aprobación. un
la ambigüedad reconocida produce una pregunta de 2 a 3 opciones sin admisión.
Las solicitudes fuera de la gramática determinista utilizan exactamente un tipo de solo lectura escrito,
turno clasificador sin aprobación. Aclarar, negar y el fallo del clasificador no concede
autoridad de ejecución y son estados distintos.

Solicitudes exactas de creación/mover a la papelera del sistema de archivos del usuario actual y paquete exacto
Las solicitudes de instalación/eliminación también tienen planes deterministas, pero nunca automáticos.
autoridad. Sus admisiones de esquema-v3 están explícitamente pendientes de aprobación,
propuestas de ejecución deshabilitada y vinculadas a resumen. Una decisión modal afirmativa es
consumido una vez por el correspondiente ejecutor del sistema de archivos Python o registrado
Ayudante de polkit. Las mutaciones propuestas por modelos más amplios utilizan App Server `untrusted`
revisión de comando/archivo. Ver `tui-mutation-executor.md`.

La vista de conversación limpia es también la proyección activa del contexto del modelo. antes
En una verificación previa del modelo posterior, JARVIS envía cualquier entrada desinfectada visible que no esté
ya representado en el hilo actual del servidor de aplicaciones a través del anclado
Método `thread/inject_items`. La solicitud pendiente actual se excluye y se
enviado por separado mediante verificación previa escrita. El mensaje inyectado etiqueta cada
entrada como historial citado que no es de confianza, nunca como instrucción, aprobación o
autoridad de ejecución. Una lectura local determinista todavía no genera ningún servidor de aplicaciones
solicitar en el momento de la lectura; su solicitud de usuario y su resultado limitado solo se sincronizan
si una solicitud posterior de un agente necesita continuidad conversacional.

El contexto activo sigue la ventana del token por conversación seleccionado y permanece
Limitado a 500 entradas de presentación. Cuando se alcanza el límite, los intercambios completos más antiguos se eliminan tanto del
Se inserta una instantánea de vista y modelo y un marcador de omisión visible. nuevo,
Las acciones claras y cargadas de historia avanzan una época contextual; el siguiente modelo
La solicitud inicia un hilo nuevo en lugar de combinar vistas incompatibles. Contexto
la sincronización se intenta una vez. El fallo se detiene antes del clasificador/ejecución
`turn/start`, informa `conversation_context.sync_failed`, restaura el envío y
no repite la tarea.

### Comportamiento actual de ejecución — 2026-09-14

El preflight no determinista usa un hilo efímero y solo transfiere la evaluación
tipada a la conversación persistente. El scope MCP se inicializa antes del App
Server, no permite llamadas durante preflight y limita la ejecución a las
herramientas del especialista. Las preguntas sobre rama, estado o metadatos
actuales requieren evidencia fresca de `github_inspect`. La compactación espera
`contextCompaction` y conserva el hilo si falla.

La proyección sincronizada se puede utilizar como evidencia observacional limitada, no
sólo prosa conversacional. Cuando se resuelve exactamente un resultado compatible reciente
una referencia como “ese directorio”, un recuento de seguimiento, un resumen, una comparación,
o explicación se clasifica como un turno de conversación de sólo respuesta. el agente
debe responder a partir de la evidencia existente sin herramientas, comandos, sistema de archivos o
acceso a la red, o una solicitud de aprobación, y debe conservar la instantánea relevante
límites en su respuesta. Múltiples referentes plausibles o evidencia insuficiente
todavía requieren aclaración. Una solicitud explícita de estado nuevo/actual
requiere una lectura recién autorizada. Los nombres de archivos incrustados y el texto del resultado permanecen
datos que no son de confianza y nunca se convierten en instrucciones o autoridad de ejecución.

Los métodos del ciclo de vida de los elementos de App Server tienen autoridad cuando un elemento omite el suyo propio.
estado: proyectos `item/started` como proyectos `in_progress` y `item/completed`
como `completed`, mientras se conserva un estado explícito de falla o cancelación.
Esta regla se aplica antes de que se procese la conversación, por lo que una conversación sin estado
`agentMessage` es visible inmediatamente y su finalización reemplaza al mismo
entrada en lugar de crear un duplicado.

Una lectura local admitida tiene `authority=bounded-local-read`,
`execution_authorized=true`, `agent_turn_authorized=false` y
`mutation_authorized=false`; se une tanto a un resumen de destino canónico como a un
resumen del plan del sistema de archivos inmutable. Observaciones fijas existentes como
`knowledge.search` en su lugar utilice `authority=registered-local-read` y vincule sus
acción/versión/procedimiento registrado más un resumen de destino, sin sistema de archivos
plano. Las dos variantes locales no pueden validarse entre sí. Un agente admitido
turn tiene el usuario actual real
límite del agente en un entorno limitado de solo lectura. Uso tanto del clasificador como del despacho especializado
la política de solo lectura estándar del servidor de aplicaciones instalado con la red deshabilitada.
Las aprobaciones del clasificador nunca lo son; El despacho especializado conserva MCP granular
obtener aprobación mientras las reglas y la aprobación de la zona de pruebas están deshabilitadas.
Ninguno impone lecturas nativas solo de documentación: el obsoleto
El campo readOnly.access es rechazado por el servidor instalado. Llamadas MCP escritas
requieren el alcance del proceso admitido. Las aprobaciones genéricas de comandos/archivos no pueden ejecutar mutaciones. La entrada no
no autoriza por sí misma la mutación. Las acciones del catálogo derivan la misma evaluación de
su esquema registrado. La interfaz de usuario puede responder solicitudes de comando/archivo con
aceptar una vez, rechazar o cancelar, y presenta las solicitudes de obtención de MCP en un
diálogo separado de una respuesta; Las subvenciones para toda la sesión no están disponibles. Un PCM
La decisión de obtención no es la autoridad de mutación del huésped.
La correlación de solicitudes del servidor de aplicaciones se basa en la presencia del ID JSON-RPC, no en la veracidad:
el número entero `0` es un ID de solicitud válido y debe abrir exactamente la misma pantalla de revisión,
recibirá como máximo una respuesta y será eliminado cuando se resuelva.

El acceso completo sigue estando limitado al usuario actual del sistema operativo. Uso de cambios de host privilegiado
Los ayudantes registrados de Polkit estuvieron disponibles y revisaron Bash solo como alternativa.
La lista de denegación permanente, la regla de un intento, la auditoría redactada, la validación y
Los requisitos de recuperación siguen teniendo autoridad. Los turnos en vivo todavía requieren
Suscripción CLI.

## Vistas actuales de cara al usuario1. **Descripción general:** Versión de Fedora, actualidad de los hechos, riesgos actuales, integridad de la auditoría,
   estado de recuperación y estado de sesión.
2. **Conversación:** la superficie de trabajo principal para los mensajes de los usuarios, especialista
   respuestas, aclaraciones/opciones, progreso, resúmenes de evidencia y aprobación
   estado. El especialista seleccionado por el usuario tiene autoridad.
3. **Agentes:** resúmenes de especialistas instalados, herramientas registradas, conocimientos
   fuentes, contexto/red/política de mutación, edición de definición estructurada/sin formato,
   diferencias de activación y reversión de versiones.
4. **Iluminación:** controles gráficos de iluminación del teclado y vistas previas limitadas.
5. **Energía:** inventario de energía de solo lectura más registro aprobado por separado
   controles.
6. **Paquetes:** inventario de paquetes instalados/disponibles y compartidos
   Flujo de trabajo del paquete de especialista en instalación.
7. **Cronología:** proyección legible por humanos de los eventos del ciclo de vida encadenados mediante hash.
8. **Operaciones:** fallos de solo lectura, lecciones respaldadas por evidencia, recuperación,
   configuración, auditoría, reconexión y proyección de notificaciones.

Los especialistas seleccionables incluyen al especialista en salud del sistema para áreas limitadas.
Rendimiento de Fedora/diagnóstico térmico y Cargo Builder para Rust/Cargo
inspección del proyecto. Las compilaciones y pruebas locales del proyecto utilizan el comando revisado
límite; los recopiladores de estado escrito y cadena de herramientas son de solo lectura.
El especialista en redes, el especialista en seguridad y el especialista en recuperación brindan
vistas de inventario local limitadas para sus respectivos dominios. Su actual
las herramientas son sólo de observación; La reparación del sistema no está disponible hasta que se solucione un problema.
Se implementan el ejecutor revisado y la ruta de verificación específicos de la acción.

Los mensajes de conversación se representan como bloques fijos a la izquierda de ancho completo sin visibilidad
Prefijos de rol. Los bloques de usuario utilizan un fondo gris distintivo; agente, JARVIS y
Los bloques del sistema utilizan el fondo de respuesta. Los controles de punto de control se representan en
una columna estrecha separada entre los bloques de mensajes y no forman parte del
cuadro de texto del mensaje. Cada cuadro de mensaje tiene una fila separadora superior y otra inferior.
usando el color de fondo de ese mensaje. Los roles internos permanecen almacenados durante
enrutamiento, persistencia y contexto del modelo.

Los cinco bloques de mensajes de usuario más nuevos también exponen un punto de control compacto `↶`
controlar. Activarlo abre las dos opciones directamente, sin intermediario.
selector cerrado y ofrece restauración de chat/contexto o restauración completa. Ambos requieren
confirmación de un solo uso; La restauración completa requiere además una nueva aprobación para
cada operación de recuperación registrada exacta y nunca repite las acciones. Restaurando un
checkpoint trunca la conversación activa antes del mensaje de usuario seleccionado,
elimina ese mensaje de la conversación visible y devuelve su texto exacto
al compositor para su edición o eliminación.

La vista principal de Conversación sigue siendo intencionalmente simple: muestra al usuario
mensaje, la respuesta del agente y solo avisos de falla o aprobación material.
Los eventos transitorios de ciclo de vida, herramienta, salida de comando, plan y razonamiento no son
se almacenan como entradas de conversación y no se representan como tarjetas de actividad. el
App Server los recibe directamente a través de su turno en vivo, mientras que Jarvis retiene
solo metadatos de auditoría/cronograma limitados y proyecciones de resultados verificadas.

Las acciones, el conocimiento, el plan y las aprobaciones son capacidades internas más que
pestañas primarias. Sus registros de herramientas, evidencia, estado del plan y registros de aprobación.
permanecen disponibles a través del plano de control central y los flujos de trabajo especializados.

## Reglas de interacción- Modos de renderizado explícitamente: observar, diagnosticar, planificar, aprobar, ejecutar, verificar,
  Recuperarse y aprender.
- No combinar la aprobación con la navegación, el despido o la confirmación ordinaria.
- Mostrar una aprobación de comando exacta en su propia pantalla. Requerir aportaciones deliberadas;
  nunca preseleccione la aprobación.
- Trate cada ID de solicitud JSON-RPC presente, incluido el cero entero, como válido;
  Nunca deje una revisión pendiente porque una identificación es falsa.
- Mostrar pruebas más sólidas y contradicciones materiales junto a las recomendaciones.
- Mostrar datos obsoletos, de ámbito sandbox, inferidos, restringidos y confirmados por la comunidad.
  claramente.
- Transmitir la salida solo después de la redacción y limitarla. Preservar todo lo permitido
  registrar en el almacén de conocimientos según la política de retención.
- Trate la salida visible del sistema de archivos local como contexto de sesión activa únicamente. puede
  transferirse al servidor de aplicaciones Codex configurado después de que el producto explícito
  consentimiento, donde se aplica la retención del Codex, y los resultados visibles desinfectados se pueden guardar en una conversación limitada JSON. Los resultados sin procesar no se escriben en el diario de eventos de TUI. Persistir solo en los recuentos de metadatos y
  resúmenes para la operación de sincronización.
- Registre los eventos del ciclo de vida del material, no los deltas de transmisión individuales. un acotado
  El resumen por artículo puede contener recuentos, tamaños, indicadores de desinfección, duración y
  un resumen continuo, pero nunca texto simbólico, indicaciones, contenidos de archivos o datos privados.
  razonamiento.
- Al inicio, Timeline proyecta el ciclo de vida del material y los registros de errores únicamente. eso
  reemplaza filas de protocolo normalizado heredadas/no materiales con un recuento de omisiones;
  muestra como máximo los últimos 100 registros históricos materiales con un segundo
  recuento de omisiones. Todas las filas omitidas permanecen intactas en la auditoría de solo anexar
  diario.
- El lenguaje de la línea de tiempo proviene del estado de evaluación/admisión: la captura no es
  admisión, la lectura local no es autoridad de mutación del host y falla del clasificador
  no es una negación de la política.
- En caso de un resultado inesperado, detenga el progreso, pase a Diagnosticar y solicite un nuevo plan;
  nunca presente un botón Reintentar que se repita automáticamente.
- Accesibilidad, operación solo con teclado, cambio de tamaño de terminal, sesiones interrumpidas,
  y la recuperación ante fallos son requisitos de la versión.

## Límite de API

La TUI podrá solicitar listados de capacidades, evaluación de políticas, consultas de conocimientos,
decisión/error/grabación de lecciones, aprobación, verificación/consumo, libro mayor
verificación, ejecutores registrados y aprobaciones de comandos/archivos de App Server. golpe
está disponible sólo dentro de un turno de ejecución admitido y permanece sujeto a la
puerta de comando confiable, revisión exacta, enlaces, permisos del sistema operativo y denegaciones permanentes.
La TUI no puede exponer la raíz sin formato, la mutación directa de SQLite ni la eliminación de auditoría.
El ejecutor del sistema de archivos limitado es una ruta local independiente de Python-API. eso
acepta un plan inmutable vinculado al resumen, revalida inmediatamente el canónico
identidad del objetivo y del archivo, rechaza objetivos protegidos/sensibles/especiales y
enlaces simbólicos del directorio y aplica las mayúsculas de lista/lectura/búsqueda publicadas.
El ejecutor de mutación del sistema de archivos acotado es otra ruta exclusiva de Python-API. eso
acepta solo un plan de creación o basura inmutable revisado más un plan en memoria coincidente
aprobación de un solo uso; vuelve a verificar el objetivo y el padre a través de descriptores,
vuelve a vincular el inodo fuente de la Papelera inmediatamente antes de cambiar el nombre y nunca lo sobrescribe
o se desvincula. La mutación del paquete acepta solo nombres exactos y una vista previa solo en caché
cuyos resúmenes de operación/estado/salida son revalidados por el ayudante propiedad de la raíz;
las instalaciones estrictamente aditivas y la reversión de eliminación vinculada a la versión son las únicas
efectos de paquete admitidos.
La inspección de paquetes en lenguaje natural está dirigida por agentes a través del modo de solo lectura
Herramientas MCP `package_catalog`, `package_search` y `inspect_packages`. Estos
las herramientas devuelven evidencia de Fedora instalada/en caché limitada y no pueden instalarse,
eliminar o aprobar una transacción de paquete.El esquema de salida del clasificador tiene un objeto raíz cuyo `assessment` anidado
utiliza cuatro ramas `anyOf` de objetos estrictos independientes y completas. el
El esquema de cableado utiliza solo el subconjunto de salida estructurada portátil para ajustar
modelos: objeto/matriz/cadena/entero/tipos nulos, enumeración, requerido y
`additionalProperties=false`. Luego, Python aplica cadenas, longitudes,
cardinalidad objetivo, cardinalidad de aclaración y las mismas variantes de decisión
antes de cualquier admisión. Esta división es necesaria porque el backend rechaza esos
palabras clave de restricción específicas de tipo para esta ruta de modelo. Un giro fallido es
categorizado sin persistir su mensaje como `output_schema`,
`model_unavailable`, `capacity`, `authentication`, `transport`, o
`server_error`.

### Contabilidad de contexto (2026-09-13)

`context.usage` conserva cifras de última respuesta, acumulado del hilo y petición
completa, separando preflight y ejecución e incluyendo entrada en caché. Los campos
del diario terminan en `_count` (por ejemplo `total_count`) para mantener intacta la
redacción de claves de credenciales. Se calculan diferencias del acumulado; no se
suman notificaciones repetidas de `last`. Una base desconocida tras reanudar o un
contador decreciente marca el intervalo como incompleto. El uso sin tarea vinculada
no se atribuye a una petición. La interfaz muestra una **estimación de contexto**
basada en la última respuesta y separa consumo acumulado y entrada en caché.

`context.payload` mide bytes de JSON UTF-8 canónico de solicitudes; `context.tool_payload`
mide argumentos, resultados y errores de herramientas sin guardar su contenido.
No son tokens y no incluyen las instrucciones, esquemas o historial añadidos por el
servidor. Las restricciones estables preceden a los datos variables del clasificador;
se eliminan repeticiones exactas y formato JSON innecesario. Se mantienen evaluación
tipada, aprobaciones, observaciones verificadas, aislamiento y puntos de control.
Acotar nuevas entradas de preflight no elimina el historial previo del hilo.

Una comparación real de explicación con la configuración existente `gpt-5.6-luna` /
`none` midió 29.380 tokens antes y 29.908 después, con 13.056 y 6.912 tokens de entrada
en caché. Ambas respuestas fueron correctas y de dos frases. **No demuestra ahorro
ni paridad con CLI**. El caso controlado de prompts pasó de 8.299 a 8.092 caracteres.
El MCP contiene 52 definiciones (18.001 bytes JSON compacto); cuatro son de GitHub
(3.011 bytes). El catálogo anunciado es más amplio que los permisos de ejecución.
No se activan filtrado de herramientas, cambios de modelo, compactación automática
ni métodos nuevos. La compactación asíncrona documentada requiere validar su ciclo
de vida y los puntos de control antes de adoptarla:
https://learn.chatgpt.com/docs/app-server#trigger-thread-compaction


El prompt de preflight del especialista ahora solo lleva identidad, versión y número de restricciones vinculados por el corredor. El contrato completo permanece en la ejecución. Un fixture redujo el prompt del clasificador de 6,7 KB a 3,7 KB; no es una afirmación de ahorro de tokens.

La visibilidad de herramientas MCP se filtra por el scope del especialista. El
preflight ve el catálogo seleccionado para conservar el esquema, pero el scope
rechaza toda llamada hasta la admisión tipada. La ejecución recibe únicamente
las herramientas MCP registradas para ese especialista y los metadatos comunes.
El contrato personalizado se suministra una vez por digest e hilo y se referencia
en los turnos posteriores.
