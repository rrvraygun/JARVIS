# Auditoría y diseño estatal.

## Diseño```text
runtime/
estado/actual/redactado últimas vistas
estado/instantáneas/instantáneas con marca de tiempo inmutables por convención
estado/líneas de base/líneas de base comparables de salud y desempeño
  audit/events.jsonl      append-only event stream
  audit/manifests/        hashes covering stored artifacts
  reports/                human-readable summaries
  knowledge/knowledge.db  versioned structured facts and lessons
documentación/local.jsonl importación de documentación local limitada
exportaciones/recibos de solo anexación remota cuando se configura
```Cada registro incluye la versión del esquema, la marca de tiempo UTC, el seudónimo del nombre de host o
identificador aprobado, versión del recopilador, cobertura, privilegio utilizado, redacciones,
comando de origen, estado de salida y ruta de evidencia. Cambiar eventos enlace adicional
el objetivo, riesgo, aprobación, instantáneas antes/después, objetivos exactos, validación,
retroceso y riesgo residual.

Lista de campos recopilados permitidos. Nunca persista valores secretos, volcados de entorno completo,
claves privadas, bases de datos de autenticación, datos del navegador o comandos sin restricciones
salida. Trate el texto de auditoría como confidencial. Utilice permisos restrictivos, retención,
rotación, copias de seguridad y manifiestos de integridad. Los hashes locales revelan errores accidentales o
alteración poco sofisticada pero no son protección contra un atacante privilegiado;
Las implementaciones de alta seguridad necesitan almacenamiento remoto firmado solo para anexos.

El diario TUI en `runtime/tui/events.jsonl` se escanea y se verifica mediante hash una vez
cuando una instancia de `EventJournal` lo carga por primera vez. Su encabezado en caché vincula el archivo
identidad, evidencia de tamaño/cambio, desplazamiento de bytes verificado, secuencia, último hash y
Claves de idempotencia. Cada anexo posterior valida sólo la nueva versión del escritor cooperante.
sufijo debajo del bloqueo del archivo; reemplazo, truncamiento o cambio in situ
La evidencia obliga a un escaneo completo. `verify()` siempre realiza una evaluación completa independiente
escaneo en cadena. Los agregados permanecen en modo `0600`, bloqueados, vaciados y sincronizados; esto hace
No rotar, truncar, reescribir ni eliminar el diario existente.

Las deltas del servidor de aplicaciones de streaming se acumulan solo como recuentos limitados en memoria,
totales de caracteres/bytes, indicadores de desinfección y un resumen continuo. Un resumen es
escrito al finalizar el artículo autorizado o al limpiar la terminal. Texto delta sin formato,
salida de verificación previa, razonamiento privado, resultados del sistema de archivos, texto de ruta/consulta y
Los listados de directorios no son campos de diario.

Solo entrada/carácter de diarios de sincronización de contexto de Active Conversation
recuentos, recuento de intentos, estado, una categoría de error cuando corresponda y un resumen
de enlaces de entrada ya desinfectados. La carga útil del contexto citado no se copia
en este diario. Los resultados del sistema de archivos local desinfectados y visibles para el usuario se conservan en una conversación JSON limitada; La salida sin formato del sistema de archivos permanece excluida del diario de auditoría. Cuando una solicitud de agente posterior se envía activa
contexto a través del Codex App Server `thread/inject_items`, se aplica la retención del Codex
fuera del límite de retención local de JARVIS.

La ejecución del sistema de archivos local se reserva una vez por tarea y resumen del plan inmutable
antes de que comience el recorrido, por lo que el envío duplicado no puede repetir una operación.
Las admisiones al sistema de archivos requieren vinculaciones tanto de plan como de destino; registro fijo
las observaciones utilizan una autoridad de lectura local registrada distinta.

Las reservas de mutación también son únicas. Se omiten los registros de mutación del sistema de archivos
rutas, nombres, contenido, destinos de la Papelera y resultados renderizados; ellos contienen
solo operación escrita, destino categorizado, estado, duración, error/reversión
banderas y resúmenes vinculantes. Los registros de paquetes omiten el texto de vista previa y los nombres de los paquetes.
del diario TUI y conserva solo la operación, los recuentos, el estado, el recuento de intentos,
y planificar/revisar/previsualizar resúmenes. La recuperación específica del propietario del asistente raíz
El registro es un artefacto operativo protegido independiente, nunca una aprobación reutilizable.

Los registros restringidos y secretos se rechazan hasta que se realice el almacenamiento cifrado.
implementado y desbloqueado explícitamente por el usuario. Los intentos de comando crean un error
observaciones en busca de fallas y resultados inesperados. Revisiones de conocimientos nunca.
reemplazar los eventos de auditoría de seguridad.
