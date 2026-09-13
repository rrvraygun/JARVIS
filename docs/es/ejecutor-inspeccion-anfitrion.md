# Ejecutor de inspección de host de solo lectura

> **Nota de estado (2026-08-09):** este documento cubre las distintas versiones de solo lectura
> ejecutor de inspección. El asistente de control de paquetes no forma parte de este ejecutor;
> su alcance actual y sus requisitos de implementación están en
> [`current-product-state.md`](estado-actual-producto.md).

## Alcance

El corredor de TUI puede solicitar una inspección del host local delimitado antes de iniciar un
conversación del agente. Esta es una operación explícita del plano de control de sólo lectura, no
una herramienta de App Server y no una autoridad de ejecución de host.

El ejecutor acepta el texto de la solicitud del usuario y selecciona solo recolectores fijos:

- `platform`: `/etc/os-release` y `os.uname()`.
- `power`: el inventario de energía existente, los metadatos de RPM instalados relacionados y
  nombres de módulos del kernel cargados/expuestos.
- `packages`: base de datos RPM y metadatos del repositorio DNF en caché. nunca
  actualiza los repositorios o inicia una transacción.

Sin comando, ruta, ejecutable, fragmento de shell ni URL de repositorio proporcionados por el usuario
es aceptado por el ejecutor.

## Lector de sistema de archivos delimitado distinto

Los recopiladores de inspección de host fijos anteriores permanecen sin cambios. exacto
Las solicitudes del sistema de archivos del usuario actual utilizan el archivo separado.
`tui/src/jarvis_tui/local_filesystem.py` planificador/ejecutor. Esa ruta acepta un
plan de ruta escrito pero nunca un comando o argv. Sólo apoya a los conservadores.
Formularios `list`, `read` y `search` en inglés/español, alias de directorio de usuarios XDG,
alias de espacios de trabajo y rutas explícitas inequívocas.

El plan vincula el token de destino original, las rutas solicitadas y canónicas,
dispositivo/inodo/tipo de identidad, operación, modo de búsqueda/resumen de consulta, oculto y
opciones de recursividad, límites y un resumen general del plan. La ejecución revalida la
vinculante inmediatamente, usa `O_NOFOLLOW` relativo al descriptor abierto y Python
API del sistema de archivos en un subproceso de trabajo y realiza un intento de operación. eso
niega almacenes confidenciales, nombres que contienen secretos, árboles/archivos especiales, directorios
enlaces simbólicos, lecturas binarias, búsquedas amplias del sistema y lecturas caseras recursivas amplias.

La lista predeterminada no es recursiva y tiene como máximo 500 entradas. Las lecturas directas consumen en
máximo 64 KiB antes del límite de presentación. La búsqueda está limitada a la profundidad 8, 2000
archivos normales, 1 MiB por archivo, 200 coincidencias y una fecha límite corta y monótona.
Las entradas ocultas requieren una redacción explícita y los descendientes sensibles permanecen
excluido. Los eventos de auditoría contienen sólo objetivos, recuentos y categorías categorizados/digeridos.
duración, estado y límites aplicados, no rutas, consultas, listados, coincidencias o
contenidos del archivo.

Esta autoridad de lectura nunca se actualiza a autoridad de escritura. Exacto crea,
mover a la Papelera y las transacciones de paquetes utilizan el sistema distinto controlado por aprobación
contratos en `tui-mutation-executor.md`.

## Conocimiento del paquete

Los escaneos de paquetes persisten en `runtime/knowledge/package-catalog.json.gz`,
modo `0600`, como un catálogo JSON gzip. Cada registro conserva la identidad del paquete,
versión, estado, origen/repositorio, proveedor, resumen, categoría y clasificado
propósito. Las consultas devuelven coincidencias clasificadas limitadas y etiquetan instaladas con el mismo propósito
paquetes como una inferencia, nunca un conflicto de RPM.

Los paquetes instalados pueden exponer la documentación de RPM enviada a pedido. Oficial
La documentación no se recupera intencionalmente de forma implícita: su actualización requiere una
operación futura explícitamente aprobada por la red, con procedencia de la fuente y
frescura registrada por separado.

## Límite del agente

El informe formateado es evidencia de entrada para la conversación con el agente. el modelo
no puede invocar recopiladores, una terminal, escrituras en sistemas de archivos, transacciones de paquetes,
o ayudantes privilegiados. El corredor registra únicamente la identidad del recopilador, seleccionada
alcances, recuentos y estado; no registra listas de paquetes sin procesar ni solicitudes
texto.
