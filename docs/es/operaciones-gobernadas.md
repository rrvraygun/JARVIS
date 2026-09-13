# Candidato de operaciones gobernadas: récord histórico, 2026-09-08

> Instantánea histórica. El comportamiento actual está definido por `current-product-state.md`,
> `tui-contract.md` y la raíz `CHANGELOG.md`; este archivo se conserva para auditoría
> procedencia y no es una especificación de implementación.

Este es un candidato preparado, no un lanzamiento activado. El pago activo y sus
El perfil de tiempo de ejecución no ha sido reemplazado. Una implementación no es una promoción.

## Límites implementados

El agente planifica a través de herramientas MCP escritas. La TUI revisa la propuesta exacta y
emite una aprobación efímera. El ejecutor consume ese objeto una vez, se reserva un
ID de operación duradera antes de los efectos, revalida el estado y registra el resultado.
No existe ningún punto final de aplicación o aprobación orientado al modelo. Rechazar no crea ejecución
reserva. Los fallos del proceso, el tiempo de espera, la deriva de estado y el desbordamiento de salida nunca vuelven a intentarlo.

Las propuestas vinculan ID, dominio, operación, objetivos, argv, entorno permitido, tiempo de espera,
límite de salida, privilegio, efecto de red, limitaciones de reversión, estado previo y
poscondiciones. La reseña debe ajustarse a su límite de visualización antes de ofrecer la aprobación.
La verificación independiente de un resultado es un artefacto separado con el mismo ID y
resumen y el conjunto de verificación completo requerido.

| Dominio | Operación implementada | Límite práctico |
| --- | --- | --- |
| Desarrollo | Comprobación de carga/construcción/prueba/comprobación fmt/clippy | Se requiere una instantánea exacta, caché vacía sin conexión, controlador de recursos de usuario systemd y envoltura de burbujas. Sin respaldo. |
| Desarrollo | Cambio Cargo.toml/Cargo.lock | Crea un nuevo espacio de trabajo. Una operación apply_dependencies aprobada por separado puede reemplazar los manifiestos existentes en los archivos desplazados originales y conservarlos. TOML y las comprobaciones de archivos exactos no prueban la resolución de dependencias ni una compilación exitosa. |
| Recuperación | Copia de seguridad y restauración de proyectos de texto | Solo nuevo destino; R0, no datos binarios, disco, arranque o recuperación de todo el sistema. |
| Red | Un intento de accesibilidad TCP | IP y puerto canónicos exactos, sin DNS ni datos de aplicación, aprobación de un solo uso por separado. El registro remoto no se puede deshacer. |
| Salud | Reiniciar/habilitar/deshabilitar el servicio auxiliar y cliente | No hay ayudantes desplegados ni unidades inscritas. Se requiere una póliza R1 de propiedad raíz que venza. Mecanismos complejos de dependencia/instalación/instalación rechazados. |
| Red | Configuración DNS IPv4 guardada | Ayudante fijo/cliente preparado; Se requiere UUID y valores de conexión exactos, inscripción de raíz y R1 actual. No desplegado. |
| Seguridad | Etiqueta de archivo SELinux predeterminada/servicio de firewall de ejecución simple | Ayudante fijo/cliente preparado; sin enlaces físicos, reetiquetado recursivo ni expansión del servicio. No desplegado. |
| Seguridad | Actualizaciones y cambios de arranque | Propuestas bloqueadas; todavía no hay albacea. |
| Recuperación | Recuperación del sistema R1–R3 | Contratos existentes/puertas de pruebas; no implementado por el backend de copia del proyecto de texto. |

## Límites de recursos y instantáneas

Este backend requiere un marcador de proyecto de texto conocido. Las instantáneas del proyecto rechazan enlaces, archivos especiales, archivos sin propietario/escribibles en grupo,
Contenido en forma de secreto, contenido binario y rutas inseguras. Unen hashes para el
todo el árbol permitido antes de la revisión, no solo los manifiestos de carga. Los límites son 2000.
entradas, profundidad ocho, 1 MiB por archivo y 8 MiB por árbol. Archivos ocultos, candidatos con nombres confidenciales, destino,
node_modules y runtime están excluidos y listados explícitamente. Como máximo dieciséis
Se pueden preparar instantáneas antes de que sea necesario realizar una limpieza revisada.Cargo recibe una instantánea del código fuente de solo lectura, /usr de solo lectura, /tmp privado y build
tmpfs, sin inicio de usuario y espacios de nombres separados. solicitudes systemd-run MemoryMax = 1G,
TasksMax=32, CPUQuota=100%, RuntimeMaxSec=120 y LimitFSIZE=256M. Un guardia controla el
Valores efectivos de memoria/proceso/CPU de cgroup antes de ejecutar bubblewrap. Una prueba de carga mínima real pasó por estos controles el 9 de septiembre de 2026 en el contexto del host. Esto no establece soporte para proyectos que generan dependencia ni para todos los entornos restringidos. El estado de salida de la compilación no demuestra la seguridad del hardware.

## Alcance de la herramienta y evidencia

El controlador genera una ID de alcance del proceso, la pasa al comando MCP fijo,
y publica los permisos después de la admisión. El alcance incluye controlador PID/arranque
Identidad y caducidad. Se revoca ante eventos terminales, interrupción, desconexión y
Inicio de giro fallido/cancelado. Los turnos de explicación no reciben alcance MCP.

Los esquemas de herramientas siguen siendo detectables para el almacenamiento en caché de App Server; cada invocación verifica
el alcance del especialista en vivo. Un esquema no es autoridad. Activación de lecciones y
La atribución de aprobación/auditoría creada por el modelo no está disponible en esta superficie.

La evidencia del estado actual está vinculada a la tarea y el alcance, la clase de herramienta requerida y la declarada.
argumentos. Los valores de argumento esperados se almacenan como hashes. La inspección del paquete debe
primero utilice la solicitud original delimitada exacta como consulta con una colección nueva;
actualizar = falso, los resultados obsoletos, la telemetría o las consultas no relacionadas no pueden desbloquearlo.
Se permiten búsquedas más específicas. Relevancia semántica del final de un modelo.
la interpretación aún necesita evaluación; el recibo por sí solo no es prueba de ello.

Las lecturas de turnos nativos están restringidas a la documentación del proyecto; otra inspección va
a través de herramientas acotadas. La verificación previa no tiene raíces legibles explícitas. el candidato
El perfil desactiva aplicaciones, complementos y enlaces y permite un servidor MCP fijo. Inicio
comprueba el resultado efectivo de configuración/lectura, así como el perfil. Soporte de tiempo de ejecución
para estas configuraciones y valores predeterminados de la plataforma sigue siendo una puerta de aceptación de la integración.

## Transcripción y semántica de recuperación

Las transcripciones de operaciones desinfectadas son distintas de las conversaciones y auditorías. mecanografiado
Las comprobaciones de campo rechazan el razonamiento, los entornos sin procesar y las claves sensibles, incluidas
variantes anidadas. Los límites son 128 entradas y 64 KiB serializados por entrada, con un
Caducidad de lectura de siete días para nuevos registros. El contenido caducado se retiene; la eliminación/rotación aún requiere
revisión. Un presupuesto de transcripción completo no puede ocultar el resultado de una operación que ya es duradera.

El verificador independiente se ejecuta bajo un envoltorio de sólo lectura. Si no puede iniciar o
su conjunto de identidad/resumen/verificación no es válido, la verificación sigue siendo desconocida. tcp
la verificación valida únicamente un intento registrado; no hace otro control remoto
conexión. Los servicios requieren tanto un recibo encuadernado exitoso como un estado/enlace nuevo
cheques. Las operaciones de nueva copia conservan destinos parciales en caso de error; originales
nunca se sobrescriben y la limpieza es una acción revisada por separado.

## Puertas de activación

Antes del lanzamiento: controles deterministas completos, revisión independiente de la exactitud
candidato, pruebas de permisos negativos reales e integración de App Server/MCP. antes
uso del servicio de host: instale artefactos de ayuda/Polkit revisados e inscriba unidades exactas
con evidencia de recuperación actual revisada de forma independiente. Ninguna plantilla lo permite.
Las actualizaciones del sistema, los cambios de arranque y la orquestación automatizada de captura/restauración del sistema completo siguen siendo ejecutores no implementados. Se conservan el runbook y el comparador Restic manual de cinco límites existentes; el usuario eligió copias de seguridad controladas en el disco externo detectado. Ver `sessions/2026-09-08-external-backup-target.md`.

Base del protocolo: [official App Server documentation](https://learn.chatgpt.com/docs/app-server)
para raíces de lectura restringidas, configuración/lectura y políticas por turno. Implementación local
y las pruebas proporcionan evidencia del comportamiento del candidato; documentación del protocolo
no establece una integración en vivo exitosa.

## Recibos de verificación y recuperación de puntos de controlLos nuevos puntos de control utilizan el esquema 2; El esquema 1 permanece legible solo para chat/contexto.
La recuperación completa rechaza el historial heredado y no rastreado, incompleto o sin soporte
mutaciones. Cada Energía, iluminación y operación registrada registra una reserva
antes del envío. Una transacción de un solo paquete requiere que su coincidencia sea exitosa
recibo y registro de recuperación autorizado vigente. Restauración de la conversación
ocurre solo después de que la deshacer aprobada por separado se realiza correctamente y no hay mutación concurrente
aparece. Otras familias de operaciones requieren su propio flujo de trabajo de recuperación; no genérico
Se reclama la reversión del sistema.

Las observaciones de herramientas conllevan una generación de alcance única capturada antes de la recopilación.
Reemplazar o revocar un turno evita que los resultados tardíos desbloqueen el siguiente turno.
La verificación del recibo de operación se deriva de manera consistente para UI, MCP y transcripciones.
El registro de ejecución sin formato inmutable no es en sí mismo una verificación independiente.

## Continuación de la implementación del cuestionario

La operación general aislada `command` acepta un argumento exacto acotado con raíz en
/usr/bin, incluido el código de intérprete que se muestra en la revisión. Vincula lo resuelto
hash ejecutable, instantánea, entorno y recursos. Sin host, raíz o red
la ejecución está implícita. Su veredicto verifica explícitamente los hechos del proceso, no la
objetivo general del usuario. Los comandos arbitrarios de host/root/red permanecen pendientes.

Los comandos generales y de carga comparten un bloqueo de archivos en torno a la validación del historial pendiente
y reserva duradera. El guardia confiable de Python se ejecuta con `-I` y escribe un
identidad de grupo c vinculada antes de invocar el plástico de burbujas. El acuerdo requiere lo mismo.
arranque y un cgroup ausente o una identidad coincidente con `populated=0`; después de reiniciar,
La antigua ejecución necesariamente termina. Los recibos de lanzamiento faltantes siguen siendo inciertos.
Un resultado duradero previo al lanzamiento sin solicitud de lanzamiento permite el trabajo posterior; un
la reserva sin resultado no lo es. Historiales de ejecución más antiguos y no versionados
Necesitamos una reconciliación explícita antes de que se pueda traspasar esta nueva frontera.

`apply_dependencies` deriva únicamente de un espacio de trabajo de dependencia verificado y sin cambios.
Reemplaza los manifiestos existentes uno a la vez utilizando el intercambio atómico de Linux y
Conserva los archivos desplazados. Un grupo de dos reemplazos no es atómico. deriva del estado,
la falla de metadatos o el intercambio parcial retiene la evidencia y se detiene sin reintentos,
reversión o limpieza automática. Los editores externos no respetan un bloqueo JARVIS:
un cambio acelerado se retiene y se informa, no se descarta silenciosamente. Recuperación de un
la operación parcial requiere inspeccionar los candidatos retenidos y la instantánea; no
se realiza la reversión automática. La recuperación puede preparar una nueva propuesta de copia de dependencia inversa, con ejecución, verificación y aprobaciones de aplicaciones separadas, solo mientras los cambios actuales sigan siendo atribuibles. La creación de nuevos manifiestos es independiente.

### Descargas de dependencias aprobadas

`fetch_dependency` propone un paquete/versión de crates.io existente
Entrada de bloqueo de carga. Expone la URL exacta de static.crates.io, la suma de comprobación y la información privada.
archivo, límite de bytes de 8 MiB y fecha límite de proceso de 30 segundos. El trabajador HTTPS fijo
realiza una solicitud, no sigue redirecciones y no utiliza proxy ni credenciales.
Los archivos interrumpidos/no válidos permanecen para su limpieza revisada. No se ejecuta ningún código de proyecto
en el proceso de descarga.

Una operación de carga puede seleccionar un conjunto completo de ID de descarga verificadas que coincidan con el
archivo de bloqueo actual. Los hashes de archivo se verifican nuevamente y se montan como de solo lectura en el
zona de pruebas sin conexión. Un trabajador de extracción vinculado rechaza recorridos, enlaces y duplicados
archivos y archivos de gran tamaño/sobreexpandidos y crea metadatos de suma de comprobación para un
Fuente del directorio de carga. Las entradas siguen siendo de sólo lectura; El código de compilación no tiene red.
Esto admite archivos de bloqueo de crates.io dentro de los límites declarados, no Git arbitrario.
o registros privados. Una suma de verificación coincidente no es un reclamo de código de paquete benigno.Base del protocolo: [Cargo source replacement](https://doc.rust-lang.org/cargo/reference/source-replacement.html).
La prueba de integración de dependencia sintética valida la compilación fuera de línea; nada real
La descarga del registro aún se ha realizado mediante una operación aprobada por el usuario.
