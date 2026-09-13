# Puntos de control de conversación — 2026-08-30

Se implementaron puntos de control continuos por conversación para los cinco usuarios más nuevos.
mensajes. Se captura un punto de control cuando se envía un mensaje de usuario, persiste
atómicamente en un directorio privado `checkpoints` y representado como un control `↶`
en una columna estrecha separada al lado de ese mensaje de usuario. El control se abre compacto.
Opciones de chat/contexto y restauración completa, cada una seguida de una confirmación de un solo uso.

La superficie de conversación utiliza bloques de mensajes de ancho completo que se pueden montar y mantiene
controles de punto de control fuera de los cuadros de mensaje. Los bloques de usuario permanecen grises y
bloques de respuesta negros. Cada cuadro de mensaje tiene un separador superior e inferior explícito
filas en su propio color de rol. Los roles de mensajes internos no cambian.

El flujo de conversación principal no retiene ni hace transitorios deliberadamente
Tarjetas de actividades del Codex/Jarvis. Los detalles del ciclo de vida operativo permanecen en vivo
Ruta del servidor de aplicaciones y metadatos de auditoría/cronograma delimitados; solo resultados de cara al usuario,
aprobaciones y fracasos entran en la proyección de la conversación.

La restauración de contexto guarda la conversación activa como una rama separada antes
restaurar la conversación antes del mensaje del usuario seleccionado. El seleccionado
El mensaje se elimina de la conversación visible y se coloca su texto exacto.
de nuevo en el compositor para editarlo. Un aviso transitorio explica el resultado. completo
restaurar bloques mientras el trabajo activo no está resuelto y falla cuando se cierra más tarde
las mutaciones registradas no tienen una ruta de recuperación exacta; no se repite ninguna acción.

Validación: pruebas de punto de control, administrador de conversación y textos enfocados aprobadas;
Se realizaron comprobaciones de fallos, compilación, documentación, inventario y manifiesto de liberación.
ejecutar después de la implementación. No se ejecutó ninguna acción del host.
