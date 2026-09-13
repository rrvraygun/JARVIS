# Ejecutores de mutación TUI controlados por aprobación

**Contrato vigente:** 2026-08-27

Este documento define el límite de mutación actual que complementa la
lector limitado sin aprobación en `host-inspection-executor.md`. no gira
la TUI en un caparazón y no otorga autoridad permanente de anfitrión.

## Comportamiento del producto

Las tareas de lenguaje natural utilizan un canal de intermediario en este orden:

1. capturar y representar la entrada de usuario pendiente;
2. intentar una planificación de lectura limitada determinista;
3. intentar una planificación determinista exacta de las mutaciones del sistema de archivos;
4. retener raíces de paquete exactas deterministas como candidato, luego usar una escrita
   verificación previa de planificación de agentes para aclaración/confirmación de paquetes;
5. utilizar una verificación previa del modelo escrito cuando no coincida ninguna gramática determinista;
6. enrutar las solicitudes de Power Expert seleccionadas directamente al flujo de trabajo del agente de solo lectura, donde
   Herramientas Power MCP mecanografiadas propias de observación, redacción, validación y aprobación.
   puesta en escena.

Las lecturas exactas siguen estando libres de aprobación y solo en Python. Cada mutación espera una
decisión fresca, visible y de un solo uso. Rechazar y cancelar no otorgar autoridad, realizar
no escribir y restaurar Enviar. Ninguna aprobación se pone en cola, se fusiona ni persiste como un
concesión permanente o reproducida.

La ruta del modelo sigue siendo útil para solicitudes fuera del ámbito deliberadamente pequeño
gramática determinista. La admisión escrita puede otorgar un turno de agente de usuario actual, pero
no la mutación en sí. Los turnos de los agentes son de solo lectura. Las operaciones registradas cruzan el límite gráfico de revisión exacta; La aprobación genérica de comando/archivo no puede garantizar la ejecución. Consulte `governed-operations.md` para conocer el contrato por etapas.
El trabajo de raíz no está disponible a través de Bash arbitrario; debe utilizar un registrado
Ayudante de polkit.

## Mutaciones en el sistema de archivos del usuario actual

`local_mutation.py` reconoce formas conservadoras en inglés y español para:

- crear un directorio nuevo;
- crear un nuevo archivo de texto UTF-8 vacío; y
- mover un archivo o directorio regular existente propiedad del usuario actual al
  Papelera de escritorio libre del usuario actual.

Acepta XDG Desktop/Escritorio, Documentos/Documentos, y
Alias de Descargas/Descargas, alias del espacio de trabajo/proyecto y absoluto exacto
caminos. La configuración de XDG se analiza como datos y nunca se obtiene. El objetivo debe
ser escribible por el usuario actual y no debe ser ambiguo, oculto, sensible,
especial, protegido o accesible a través de un enlace simbólico de directorio. Crear operaciones
nunca sobrescribir. Eliminar significa mover el mismo sistema de archivos a la Papelera, nunca desvincularlo
o eliminación recursiva.

Un plan inmutable vincula la operación, la identidad principal y de destino, y el resumen de contenido.
y tamaño cuando corresponda, redacción de reversión, riesgo y un resumen del plan estable. un
una revisión determinista separada vincula su propio resumen. El modal acuña un
aprobación en memoria solo después de un clic afirmativo. Ejecución se reserva el
planifica una vez, consume la aprobación una vez, vuelve a verificar la política y la identidad del descriptor,
utiliza las API del sistema de archivos Python en un subproceso de trabajo, fsyncs escribe material y
verifica la poscondición inmediata. Una operación de basura repite lo aprobado.
comparación de dispositivo/inodo/tipo en la última búsqueda de nombre de ruta inmediatamente antes
el cambio de nombre atómico. Nunca utiliza Bash o argv creado por el usuario.

El diario de eventos recibe el tipo de operación, la categoría de destino, los recuentos/estado,
duración, código de error y resúmenes. Nunca recibe texto de ruta, nombres de archivos,
contenido creado, nombres de la papelera o resultados renderizados.

## Instalación y eliminación exacta del paquete

`package_mutation.py` reconoce los nombres exactos de los paquetes de Fedora para su instalación y
eliminar en inglés y español, incluidos nombres entre comillas y formas comunes como
`uninstall "rust" package`. Una solicitud de paquetes "relacionados con" raíces con nombre
usa esas raíces únicamente; DNF, no un barrido de coincidencia de nombres, determina el dependiente
mudanzas. Los objetivos genéricos como “lo último” o “todo” aclaran en lugar de
adivinando. Kernel, arranque, autenticación, administrador de paquetes, escritorio y otros
Se deniegan las eliminaciones de paquetes explícitamente protegidos.Antes de la aprobación, JARVIS realiza una simulación DNF de caché únicamente. Usos de eliminación
el formulario DNF5 `remove --no-autoremove`; el cuadro de diálogo muestra el conjunto de instalación/eliminación resuelto y delimitado
(como máximo 200 paquetes) y la vista previa. Una solicitud reconocida no crea una
turno de verificación previa del modelo o un diálogo intermedio de elección de dependencia: el único
La aprobación se aplica al efecto exacto resuelto por DNF. El resumen de aprobación vincula la operación,
nombres exactos, estado actual de RPM,
y obtener una vista previa del resumen. El asistente de propiedad raíz vuelve a ejecutar la misma vista previa de solo caché,
rechaza la deriva o las eliminaciones protegidas, escribe un estado previo duradero, ejecuta uno fijo
Comando de instalación/eliminación de DNF y verifica el estado posterior. Los nombres son datos validados;
URL del repositorio, fragmentos de shell, opciones arbitrarias, actualizaciones y repositorio
No se aceptan cambios.

El resumen de vista previa se calcula a partir de filas de paquetes de transacciones DNF normalizadas.
(identidad/arquitectura del paquete y lanzamiento de versión), con información conocida
Se omitió el mantenimiento de registros/caché no semántico y se normalizó el orden de filas. esto
mantiene la aprobación vinculada al efecto exacto del paquete resuelto al tiempo que permite
La segunda simulación requerida del ayudante para que coincida con la vista previa de la interfaz de usuario.

Las mutaciones de paquetes están orquestadas por un agente, no ejecutadas por un shell de agente. el mecanografiado
El planificador del agente puede solicitar una aclaración sobre la fuente de instalación o la exactitud.
raíces. Una vez claro, solo entrega `package_install`/`package_remove` y exacto
raíces en la ruta de vista previa/aprobación registrada; no debe proponer `sudo`,
`dnf`, Bash o una aprobación de comando del servidor de aplicaciones.

Antes de una vista previa, ejecución o revisión de recuperación del paquete, la TUI compara el
hash de ayuda raíz implementado con la fuente de ayuda revisada en el paquete activo.
Se informa una discrepancia antes de cualquier aprobación; reinstalar el asistente es entonces una
acción de implementación privilegiada separada que no ejecuta ninguna transacción de paquete.

Las líneas de recuento de resumen de transacciones DNF5 no son secciones de lista de paquetes. ambos
las capas de vista previa dejan de analizarse en esos recuentos, por lo que el texto de estado DNF final no puede
confundirse con un objetivo de eliminación. Cuando un rumbo de eliminación está localizado o
extendidos, utilizan sólo filas en forma de RPM de la tabla de transacciones de DNF; mixto
Las transacciones de instalación/actualización siguen siendo rechazadas.

Puede existir un registro de reversión autorizado por usuario. Deshacer es un proceso separado
operación con una nueva reserva de un solo uso, confirmación y Polkit
autenticación. Deshacer la eliminación solicita la época/versión/lanzamiento/arco exacto
registrado antes de la transacción y elimina el registro de recuperación sólo después de la
Se verifica el mismo estado de RPM enlazado. El asistente primero realiza otra operación de solo caché.
Simulación de retroceso y rechaza cualquier efecto fuera del conjunto grabado. ambiguo
El estado previo de multilib se rechaza antes de la eliminación original. El historial del paquete es una prueba útil, pero
no representado como recuperación completa del sistema.

Si un intento de ayuda anterior dejó un registro `prepared`, una nueva revisión de recuperación
puede reconciliarlo sólo cuando cada pre-estado registrado todavía esté exactamente presente.
Eso borra un registro incompleto sin ejecutar DNF. Cualquier diferencia de estado
permanece indeterminado y no se borra automáticamente.

Un registro aplicado cuya reversión se haya vuelto insegura puede archivarse con
una confirmación separada. El asistente sincroniza una copia sellada propiedad de root y luego
retira el registro activo; no ejecuta ningún comando DNF y lo elimina permanentemente
capacidad de reversión de registros, lo que permite transacciones de paquetes posteriores.

## Autoridad y admisión

Presentación del paquete TUI versión 0.7.0-dev y de la canalización de tareas versión 3.0.0
esquema de admisión de tareas versión 3, que distingue:

- `local_read`: ejecución autorizada para una lectura limitada, sin mutación;
- `local_mutation`: plan de sistema de archivos del usuario actual revisado, aprobación pendiente;
- `registered_mutation`: plan de paquete registrado revisado, aprobación pendiente;
- `agent_conversation`: superficie de agente de usuario actual con aprobación en la aplicación
  Límite de la herramienta del servidor; y
- `blocked`: sin autoridad.Una admisión pendiente de aprobación tiene `execution_authorized=false` y
`mutation_authorized=false`. La autoridad existe sólo después de que se realiza la revisión exacta.
afirmado y es consumido por la reserva de ejecución única.

## Fracaso y recuperación

Hay un intento. Desviación del objetivo, deriva previa, ausencia del ayudante, Polkit
rechazo, error de permiso, cancelación antes de la reserva, inesperado
La salida o el error de verificación se detiene sin volver a intentarlo. Una vez que se produce una mutación
reservado y en ejecución, la TUI no pretende poder cancelar o reproducir de forma segura
el trabajador. Un resultado indeterminado se informa como tal y requiere
inspección antes de cualquier nuevo plan.

La ruta del sistema de archivos proporciona una reversión a nivel de operación a través de la Papelera, no una
instantánea del sistema de archivos. La ruta del paquete proporciona un registro de ayuda limitado, no
arranque, configuración o recuperación de datos de usuario. Los cambios de mayor riesgo siguen sujetos
a los niveles de recuperación en `direct-host-deployment-and-recovery.md`.
