# Sistema de aprendizaje y conocimiento consciente de la versión

## Propósito

El sistema de conocimiento mejora la selección de comandos sin desactivar la salida previa.
en autoridad. Responde cuatro preguntas diferentes con evidencia separada:

1. ¿Qué es cierto acerca de esta estación de trabajo ahora?
2. ¿Qué sintaxis y comportamiento se aplican a las versiones instaladas?
3. ¿Qué pasó cuando se intentó una orden?
4. ¿Qué lecciones operativas reutilizables ha aprobado el usuario?

Nunca colapses esas preguntas en un único campo de memoria mutable.

## Modelo de almacenamiento

`storage/schema.sql` define una base de datos SQLite con revisiones inmutables para:

- fuentes de documentación y contenido almacenado en caché local;
- Datos de Fedora y su actualidad/requisitos previos;
- un catálogo de comandos Bash/Fedora incluidos en la lista permitida;
- resultados de comandos de un solo intento e informes de errores vinculados automáticamente;
- revisiones de lecciones y evidencia independiente de éxito/conflicto;
- resúmenes de decisiones auditables;
- aprobaciones de comandos, procedimientos y transacciones más registros de reproducción;
- Recibos de exportación que se pueden adjuntar de forma remota.

Los activadores de la base de datos bloquean actualizaciones y eliminaciones de filas históricas críticas. un nuevo
El estado del hecho o lección es una nueva revisión. El libro de contabilidad JSONL externo sigue siendo el
secuencia de eventos de seguridad; SQLite no lo reemplaza.

## Registro fuente

`registry/sources.json` clasifica las pruebas por aplicabilidad y autoridad. Clasificaciones
son reglas de enrutamiento, no puntuaciones de verdad automáticas. Versión local y oficial coincidente
La documentación gana a una página más nueva pero incompatible. Los registros fuente incluyen
editor, localizador, tiempo de recuperación, versiones aplicables, hash de contenido,
integridad y requisitos de confirmación de la comunidad.

`scripts/index_local_docs.py` recopila solo ayuda Bash local incluida en la lista permitida, hombre
páginas, o versión explícitamente segura/salida de ayuda. Invoca procesos directamente,
no utiliza entradas de shell arbitrarias, limita la salida, realiza un intento por método y
escribe un archivo de importación JSONL privado. El contenido SQLite resultante proporciona la
núcleo fuera de línea. La recuperación de la red y las actualizaciones de actualización permanecen más adelante, por separado.
característica controlada.

## Datos de Fedora

`scripts/collect_fedora_inventory.py` lee el registro del recopilador y lo ejecuta
matrices de argumentos exactas sin privilegios con un entorno fijo, tiempo de espera, límite de salida,
y límite de un intento. Excluye nombre de host, nombre de usuario, direcciones, números de serie,
ID de máquina, datos del navegador, documentos, almacenes de credenciales y volcados de entorno.
No puede invocar asistentes de privilegios ni ejecutables arbitrarios proporcionados por un usuario.

Los hechos recopilados no son una verdad permanente. Cada uno lleva tiempo de recogida,
versión del recopilador, intento de origen, requisitos previos, clase de privacidad y estado.
Las puertas de frescura de las políticas deciden si el hecho puede respaldar una acción posterior.

Los comandos de Codex CLI se ejecutan dentro de un entorno limitado que puede cambiar las opciones de montaje, denegar
escrituras en tiempo de ejecución, oculta datos protegidos del dispositivo y aparece como un contenedor para
Detección de virtualización. Por lo tanto, cada hecho registra el alcance de la observación.
Los resultados exclusivos del observador no pueden establecer la configuración del host. Una salida exitosa
El código es insuficiente cuando la salida contiene advertencias, efectos secundarios negados, extra.
restricciones o no cumple con una expectativa específica del comando.

## Construcción de comandos

Almacene comandos como `executable` más `argv[]`. Representar texto Bash solo para el usuario
interfaz. Antes de la ejecución, registre las expansiones de shell, redirecciones, canalizaciones,
clase de directorio de trabajo, claves de entorno, objetivos exactos, códigos de salida esperados,
expectativas de salida, tiempo de espera, riesgo, reversión y validación.

El catálogo de comandos describe si un ejecutable puede mutar y qué local
Los métodos de búsqueda de documentación son seguros. No es una lista de ejecución permitida. real
la ejecución aún requiere una política de capacidad, permiso y aprobación para el entorno de pruebas/sistema operativo.

## Máquina de estado de lección y error```text
attempt
  ├─ expected success ──> verified success evidence
  ├─ failure ───────────> error observation ──> diagnosis
└─ resultado inesperado ─> observación de error ──> diagnóstico

diagnosed + working verified solution
  └─> draft lesson
       └─> three independent matching successes
            └─> promotion candidate
└─>aprobación explícita del usuario
                      └─> active lesson
└─ conflicto/cambio de versión/efecto inesperado
                                └─> suspended revision
```La automatización no puede activar una lección. El recuento de éxitos por sí solo es insuficiente a menos que
Los requisitos previos coinciden y la validación es independiente. Un conflicto impide que el candidato
promoción. Los cambios de versión suspenden la aplicabilidad hasta que se revalidan.

En la interfaz de lenguaje natural, `activate_lesson` es la única activación
herramienta y su política MCP es `prompt`, lo que obliga a una interacción de aprobación directa del usuario.
No trate la aprobación de otro comando, una declaración de chat del alcance anterior o
un objeto de decisión generado por el agente como activación de lección.

También se revisa el diagnóstico de errores. La observación original permanece inmutable;
un diagnóstico o resolución posterior anexa una revisión vinculada al funcionamiento verificado
intento. Los intentos fallidos y exitosos nunca se editan para que aparezca el historial.
limpiador.

## Registros de decisiones

Un registro de decisión contiene objetivos, hechos, referencias de fuentes, alternativas,
acción, riesgo, validación y resultado seleccionados. Excluye deliberadamente a los privados
razonamiento del modelo. Esto produce un artefacto de auditoría estable sin tratar detalles detallados.
razonamiento como prueba fáctica.

## Modelo de aprobación

Todos los ámbitos están modelados con datos:

| Alcance | Encuadernación | Ejecución inicial |
|---|---|---|
| Comando | ejecutable exacto, argv, objetivos, resúmenes de estado/acción, nonce, vencimiento | habilitado |
| Procedimiento | procedimiento versionado exacto y secuencia acotada | discapacitados |
| Transacción | grupo atómico revisado, ordenamiento, recuperación | discapacitados |

Incluso la aprobación futura de procedimientos o transacciones puede conservar puertas por comando.
Las aprobaciones son emitidas por el usuario, vencen, están sujetas al estado, están sujetas a objetivos, son intransferibles,
y de un solo uso. La función de lista segura preautorizada inicial está definida pero desactivada.

## Límite de privacidad y cifrado

Actualmente, la base de datos acepta solo registros `public` y `internal` redactados.
Las escrituras de `restricted` o `secret` fallan hasta que se configura el estado de cifrado y
desbloqueado. Esto es intencional: un TODO cifrado nunca debe convertirse en un permiso.
para almacenar texto plano confidencial. La liberación definitiva requiere autenticación
cifrado, desbloqueo de claves mediado por el usuario, recuperación de claves de respaldo y pruebas.

## Límite de integridad remota

El esquema de receptor remoto admite anexiones SSH restringidas, bloqueo de objetos,
registro de transparencia o recibos de medios fuera de línea. No hay ningún destino configurado y no
se produce la exportación de red. Habilitar un receptor requiere la aprobación del usuario por separado, cifrada
transporte/almacenamiento, credenciales con privilegios mínimos y verificación de solo anexar.

## Limitaciones actuales

- Los hashes locales y los activadores SQLite inmutables no resisten a un atacante privilegiado.
- La recuperación y actualización de documentación aún no están conectadas a la red.
- El cifrado y la copia de seguridad remota de solo anexos bloquean la liberación.
- En esta fase no existe ningún ejecutor de Fedora que cambie de estado.
- Los datos del host protegido que el entorno limitado del Codex no puede exponer permanecen desconocidos hasta
  el usuario aprueba una ruta de lectura diseñada por separado; el agente no debe pasar por alto
  Sandbox para que el inventario parezca completo.
- La TUI y la monitorización desatendida son interfaces de futuro.
