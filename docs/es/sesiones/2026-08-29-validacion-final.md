# 2026-08-29 continuación de la validación final

## Resultado

Los cambios de estabilización de desarrollo 0.7.0 completaron su validación disponible:

- Perfil de calidad rápido aprobado: integridad de dependencia, formato, pelusa,
  documentación, inventario generado, tipificación estricta del módulo de autoridad y 22
  pruebas enfocadas.
- La suite TUI completa pasó fuera del entorno limitado de pruebas: 223 pruebas.
- El resto del contrato/accesorio no TUI del validador heredado aprobado con el
  La suite TUI se omitió intencionalmente para evitar la ejecución duplicada.
- El manifiesto de lanzamiento final verifica 728 entradas.

## Revisión independiente

Se completaron tres revisiones anteriores de Luna de solo lectura y sus altos hallazgos fueron
remediado. Se solicitó una nueva revisión final de tres carriles después del esquema final.
conciliación, pero cada revisor fue bloqueado por el límite de uso del servicio del Codex
antes de inspeccionar la fuente. Esta es una limitación de validación externa, no una
pasando la revisión. La auditoría primaria y la evidencia del revisor anterior permanecen registradas.
en `../audits/2026-08-28-codebase-audit.md`.

## Trabajo residual

Sólo queda el retraso medio/bajo en `../stabilization-backlog.md`. sin vivir
host, instalación auxiliar, paquete, energía, servicio o activación de Polkit.
realizado.

## Continuación de la capacidad del paquete

Los clasificadores relacionados con paquetes ahora reciben la corriente limitada instalada/en caché
evidencia del paquete disponible. Objetivos de modelos no exactos, incluido un funcionario
lanzamiento de Go ascendente, se convierte en una aclaración de la raíz exacta de Fedora en lugar de una
falla en el despacho interno. Esto no agrega descargas ni repositorios arbitrarios.
autoridad de gestión.

El último seguimiento del usuario mostró una ejecución indeterminada de `golang` mientras que el
cuadro de diálogo de recuperación expuesto `rust`/`rustd`. JARVIS ahora realiza una lectura de solo
informes y comprobaciones vinculantes de registros de recuperación tras un fallo
`package_helper.recovery_record_mismatch` en lugar de dejar esa discrepancia
implícito.

El asistente raíz ahora también maneja un registro de recuperación ausente como un registro vacío delimitado.
estado en lugar de filtrar un rastreo de Python a través de la TUI.
La TUI trata ese estado vacío explícito como una operación no operativa previa a la ejecución; solo un
Un registro no vacío con diferentes paquetes produce una discrepancia en el registro de recuperación.

Luego se demostró la causa fundamental del fallo de Go: el ayudante privilegiado carecía
el respaldo de la tabla de instalación DNF5 de la TUI y rechazó un conjunto resuelto vacío antes
escribir un registro de recuperación. El ayudante ahora comparte ese analizador limitado y su
El resumen del instalador se ha actualizado. Una segunda cuestión vinculante se encontró en el
resumen de vista previa sin procesar: DNF puede agregar diagnósticos de registro/caché no semánticos entre el
Vista previa de la interfaz de usuario y nueva vista previa del asistente. Ambas partes ahora canonicalizan a aquellos conocidos
diagnóstico antes del hash; el resumen del instalador se ha actualizado al nuevo
hash de origen del asistente, por lo que el asistente debe volver a ejecutarse después de este cambio de origen. el
Pasan las pruebas de inventario y ayuda de paquetes enfocadas (33 pruebas).

El diagnóstico posterior `install_set_incomplete` identificó un segundo analizador
divergencia: el ayudante a veces sólo veía las filas de encabezado mientras que el TUI veía las
Paquete DNF5/Mesa de arco. El ayudante ahora une ambas vistas limitadas; el paquete
Pases de la suite de regresión auxiliar (15 pruebas).

La evidencia limitada mostró nombres de paquetes falsos (`Repositorios`, `Resumen`)
de un respaldo demasiado amplio y omitió una fila raíz en línea. Esa alternativa es
ahora restringido a encabezados explícitos de tablas de paquetes y `Installing:` en línea
Las filas conservan su paquete raíz. Se actualizó el resumen del instalador auxiliar.

La persistencia del historial de conversaciones se amplió posteriormente para retener cada
Función de conversación visible (`user`, `agent`, `jarvis`, `action`, `system`) y
estado de entrada/identidad. Los archivos heredados de dos funciones siguen siendo compatibles; omitido mayor
El texto JARVIS/opciones no se puede reconstruir.La recarga del historial luego expuso un defecto de formato de clave: el cargador intentó analizar
claves persistentes opacas como `task:<id>` como índices enteros, borrando el
pantalla después del reinicio. Recargar la contabilidad ahora usa la posición de la matriz enumerada;
Se superan 26 pruebas de conversación/presentación.

El contrato completo de persistencia de rol visible ahora está cubierto por el enfoque
pruebas, incluidos los resultados locales de JARVIS y opciones de aclaración. Estado de entrada
las actualizaciones persisten incluso cuando la longitud del texto no cambia. La suite completa funcionó
236 pruebas y solo la prueba de vinculación de socket Unix de sandbox conocida no se pudo ejecutar.

Los envíos de aclaraciones ahora mantienen la solicitud original en su entrada existente.
y mostrar solo la nueva respuesta `User clarification:` en la nueva entrada; el
La solicitud combinada sigue siendo el texto de la tarea interna del clasificador. Esto evita
indicaciones originales repetidas preservando al mismo tiempo el contexto del agente.

La composición de la conversación ahora aplica un desplazamiento visual izquierdo de una celda a
corrija el sesgo de redondeo porcentual de celdas impares del renderizador de terminal. Componente
Los tamaños, el orden y el espaciado interno permanecen sin cambios.

La base modular del especialista ya está activa: el especialista seleccionado por el usuario
persiste, JARVIS Architect y Installation Specialist son seleccionables, el
La pestaña Agentes proporciona resúmenes operativos y estructurados/sin formato validados.
edición de definiciones y la pestaña Paquetes comparte la del especialista en instalación.
backend del paquete limitado. Las acciones, el conocimiento, el plan y las aprobaciones ya no son
pestañas primarias; la aprobación sigue siendo una decisión modal del plano de control de un solo uso. completo
Los roles de conversación visibles siguen siendo parte del contexto especializado, sujeto a la
límites de redacción y tamaño existentes.

La expansión Power Expert se agregó el 30 de agosto de 2026: topología completa desinfectada y
inventario de software/proveedor, telemetría pasiva, perfil persistente de CA/batería
planificación, una transacción auxiliar atómica de control múltiple con estado previo exacto
recuperación, actualizaciones en vivo de Power-tab y transferencia explícita de recomendaciones de paquetes
al especialista en instalación. Las capacidades a nivel de proveedor permanecen controladas por el adaptador.

Luego, el editor de Agentes se perfeccionó hasta convertirlo en un formulario estructurado desplazable y etiquetado.
para identidad, versión, propósito, límite de contexto, red/mutación/seleccionabilidad
configuraciones, herramientas registradas, fuentes de conocimiento, capacidades e instrucciones.
Sus controles fijos de validación/activación/reversión permanecen visibles durante la edición,
y el resaltado del catálogo ahora coincide con la definición cargada.

Conversación que representa entradas de usuario alineadas a la derecha con ajuste rígido frente al
El ancho de ajuste real de TextArea y ajusta suavemente las entradas entrantes, evitando largas
salida del agente/herramienta al abrir una barra de desplazamiento horizontal sin dividir el
etiqueta de usuario de su contenido. El selector se amplió para
Los nombres de especialistas de varias palabras no se recortan verticalmente. La instalación
El especialista también tiene una ruta de búsqueda determinista en el catálogo en caché para
preguntas sobre disponibilidad de paquetes; permanece como de solo lectura y no vuelve a
Herramientas de App Server, shell, red o mutación de paquetes.
