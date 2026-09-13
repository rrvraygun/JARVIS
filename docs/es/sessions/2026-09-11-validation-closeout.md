# Correcciones de cierre — 11 de septiembre de 2026

Trabajo en el candidato aislado. La versión activa y los helpers instalados
no se han sustituido durante estas correcciones.

## Diagnóstico corregido

El registro `/tmp/jarvis-headless-final.log` terminó con 36 pruebas aprobadas en
109,777 segundos. Las afirmaciones anteriores de bloqueo del driver no estaban
justificadas: varias ejecuciones se interrumpieron antes de ese tiempo. Se
retiró la cancelación global añadida sin evidencia a `on_unmount`; Textual conserva
su gestión de cierre normal. La nueva validación espera la finalización real.

## Terminal normal

Se corrigió la llamada incompatible a `run_blocking_once` y se trasladó
`App.suspend()` al hilo de la interfaz. El modo normal tiene una propuesta,
digest y aprobación distintos del modo aislado. Se reserva la operación antes
de ejecutar y se conserva un recibo durable. El entorno heredado se vincula
mediante HMAC con clave efímera; no se persisten sus valores. Se revalida después
de adquirir el bloqueo y se descarta al rechazar la revisión. La ruta normal no
se admite si JARVIS se ejecuta como root.

La prueba del botón de revisión aprobó en 2,726 segundos. La prueba real con
PTY y controlador Textual visible ejecutó exactamente un printf, produjo
`JARVIS_NORMAL_TERMINAL_OK`, terminó con código 0 y generó capturas de la revisión
y del resultado. El App Server de esa prueba era una fixture, sin cuenta ni
modelo real. Esa distinción se conserva en la guía.

## Helpers privilegiados

La revisión independiente detectó rutas no validadas, escrituras sin reserva
atómica, recuperación basada en valores del solicitante y una selección de
kernel persistente distinta del próximo arranque pedido. Se sustituyeron esos
prototipos por entradas que cargan un ejecutor instalado bajo control de root.

El ejecutor exige una revisión independiente, propiedad de root, por UID e ID,
con digest de la solicitud, caducidad y evidencia R2 ligada al preestado. No
crea esa aprobación ni la deduce de booleanos del modelo. Reserva y resultado
son registros distintos y no se sobrescriben. Un resultado pendiente bloquea
otra operación. Las políticas preparadas usan auth_admin, sin autorización
persistente; el cliente comprueba también sus hashes antes de invocar.

La selección usa grub2-reboot para un único arranque. La reparación genera una
imagen nueva; publicarla es otra operación revisada, con copia previa e
intercambio atómico que conserva el inode desplazado. La revisión se repite
antes de reservar y antes del efecto.

Las actualizaciones reproducen un árbol DNF5 --store, sin ignore/skip ni nueva
resolución libre. Se validan rutas relativas internas, firmas y NEVRA de los
RPM referenciados. El conjunto instalado final se compara con el esperado a
partir de las acciones aprobadas, incluidos los paquetes no afectados. Las
pruebas son fixtures; no se ha ejecutado una actualización o cambio de arranque.

Base del formato: https://dnf5.readthedocs.io/en/latest/commands/replay.8.html
y el serializador público libdnf5/transaction/transaction_sr.cpp del proyecto DNF5.

## Recuperación: límite de la evidencia anterior

La salida del usuario demuestra una comprobación íntegra del repositorio y una
restauración realizada. El comparador reportó seis diferencias en boot/EFI
contra el estado vivo. Los rsync posteriores usaron -naiHAX, sin -c: su salida
vacía no equivale a una comparación independiente del contenido por checksum.
Comparar dos restauraciones del mismo snapshot tampoco aporta una fuente
original distinta. La causa temporal es plausible, no una certificación.
La prueba sparse quedó sin testigo. No se convierte esta evidencia en una
aprobación R2 vigente para un cambio crítico futuro.

## Evidencia final

Los resultados completos y la copia del candidato se publican junto al
manifiesto en el directorio de entrega. No se confunden fixtures, un PTY real,
un turno autenticado y pruebas privilegiadas sobre el equipo.

La ejecución restringida final de interfaz, terminal, helpers y planificación
completó 61 pruebas en 113,673 segundos, salida 0. El validador del bundle sin
repetir TUI también pasó. Una solicitud de validación fuera del sandbox fue
rechazada antes de ejecutar por cuota de la revisión automática de permisos;
no fue una prohibición del usuario. La primera pasada del gate completo dentro
del sandbox detectó inventario desactualizado tras añadir una protección al
fixture; se regeneró antes de la siguiente validación, sin omitir comprobaciones.

La pasada completa restringida ejecutó 352 pruebas: detectó un fallo real en el
registro de Recovery Specialist (faltaba admitir recovery_plan) y una restricción
de socket Unix del sandbox. Se corrigió el registro, cuyas cinco pruebas pasaron.
La nueva solicitud limitada de las dos pruebas jarvisd fuera del sandbox fue
autorizada y ambas pasaron. No se atribuyen esos fallos a Textual ni se ocultan
mediante exclusiones del quality gate.
