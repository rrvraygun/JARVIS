# Correcciones de liquidación: 11 de septiembre de 2026

El trabajo se realizó en el candidato aislado. La versión activa e instalada.
Los ayudantes no fueron reemplazados durante estas correcciones.

## Diagnóstico corregido

`/tmp/jarvis-headless-final.log` finalizó con 36 pruebas superadas en 109,777 segundos.
Las afirmaciones anteriores de que el conductor estaba bloqueado no estaban respaldadas porque varias carreras
fueron interrumpidos antes de ese momento. La cancelación global no verificada se sumó a
`on_unmount` fue eliminado; Textual mantiene su manejo de apagado normal. el nuevo
la validación espera hasta que se complete realmente.

##Terminal normal

La llamada incompatible `run_blocking_once` fue corregida y `App.suspend()` fue
movido al hilo de la interfaz. El modo normal tiene propuesta, resumen y aprobación.
separada de la ejecución aislada. La operación está reservada antes del lanzamiento y un
Se conserva el recibo duradero. El entorno heredado está vinculado a HMAC con un
La clave efímera y sus valores no persisten. El estado se vuelve a comprobar después del bloqueo.
se adquiere, y la reserva se descarta cuando se rechaza la revisión. normales
La ejecución no se admite cuando JARVIS se ejecuta como root.

La prueba del botón de revisión pasó en 2,726 segundos. Se ejecutó la prueba PTY/Textual visible
exactamente un `printf`, produjo `JARVIS_NORMAL_TERMINAL_OK`, salió de 0 y creó
revisión y capturas de resultados. Su App Server era un elemento fijo sin cuenta real ni
modelo. La guía conserva esa distinción.

## Ayudantes privilegiados

La revisión independiente encontró caminos no validados, escribe sin reservas atómicas,
valores de recuperación controlados por el solicitante y una selección persistente del kernel que no
no coincide con el siguiente arranque solicitado. Esos prototipos fueron reemplazados con entradas.
que cargan un ejecutor instalado propiedad de root.

El ejecutor requiere una revisión independiente de propiedad raíz vinculada a UID e ID, con
Solicite resumen, vencimiento y evidencia R2 vinculada al estado previo. No puede crear o
inferir esa aprobación a partir de los valores booleanos del modelo. La reserva y el resultado son separados.
registros y nunca se sobrescriben. Un resultado pendiente bloquea otra operación.
Las políticas preparadas utilizan `auth_admin` sin autorización persistente; el cliente
también verifica sus hashes antes de la invocación.

La selección utiliza `grub2-reboot` para un arranque. La reparación genera una nueva imagen;
publicarlo es otra operación revisada con copia previa e intercambio atómico
que preserva el inodo desplazado. La revisión se repite antes de la reserva y
antes del efecto.

Las actualizaciones reproducen un árbol DNF5 `--store` sin `ignore`/`skip` o nuevo gratis
resolución. Rutas relativas internas, firmas y NEVRA de los RPM referenciados
están validados. El conjunto instalado final se compara con el conjunto esperado derivado
de acciones aprobadas, incluidos los paquetes no afectados. Las pruebas utilizan accesorios; no
Se ejecutó la actualización o el cambio de arranque.

Base del formato: <https://dnf5.readthedocs.io/en/latest/commands/replay.8.html> y
el serializador público `libdnf5/transaction/transaction_sr.cpp` en DNF5.

## Recuperación: límite de pruebas anteriores

La salida del usuario demuestra una verificación de integridad del repositorio y una restauración.
El comparador informó seis diferencias de arranque/EFI frente al estado activo. Más tarde
`rsync` ejecuciones utilizadas `-naiHAX` sin `-c`; la salida vacía no es independiente
comparación de suma de comprobación. Comparar dos restauraciones de la misma instantánea no agrega
fuente original. Una causa temporal es plausible, no certificada. La prueba escasa
no tiene testigo. Esta evidencia no se promueve a una aprobación R2 actual para un
futuro cambio crítico.

## Evidencia final

Los resultados completos y la copia del candidato se publican con el manifiesto en el
directorio de entrega. Accesorios, un PTY real, un turno autenticado y privilegiado.
Las pruebas de las estaciones de trabajo se mantienen distintas.Se completó la última ejecución restringida de interfaz, terminal, ayudantes y planificación.
61 pruebas en 113,673 segundos con código de salida 0. La validación del paquete también pasó
sin volver a ejecutar la TUI. Se rechazó una solicitud de validación fuera del entorno de pruebas.
antes de la ejecución debido a la cuota de revisión automática de permisos; no fue un
prohibición de uso. La primera ejecución del control de calidad del sandbox encontró un inventario obsoleto después
se añadió una protección fija; El inventario se regeneró antes de la siguiente validación.
sin saltarse los controles.

La ejecución completa restringida alcanzó 352 pruebas, según un verdadero especialista en recuperación
defecto de registro (falta `recovery_plan`), y acceda al socket Unix sandbox
restricción. Se corrigió la matrícula y se superaron sus cinco pruebas. un nuevo
Se autorizó una solicitud limitada para las dos pruebas `jarvisd` fuera del sandbox y
ambos pasaron. Estas fallas no se atribuyen a Textual ni se ocultan por calidad-
exclusiones de puertas.
