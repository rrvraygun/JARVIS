# Destino de copia de seguridad externa: 2026-09-08

## Decisión del usuario

El usuario conectó su disco externo para identificación y eligió controlado
copias de seguridad del sistema como método de recuperación ante desastres. Un disco completo sin comprimir
La imagen no es necesaria para este objetivo principal. Reutilización del Restic existente
el repositorio es el enfoque candidato; no se ha realizado ninguna copia de seguridad ni desbloqueo del repositorio
realizado en esta sesión.

## Observado hoy

Las lecturas de metadatos del host identificaron un USB Fujitsu MJA2500BH G2:

- nombre del dispositivo observado: `/dev/sda` (no es una identidad permanente);
- capacidad del dispositivo: 500.107.862.016 bytes;
- partición: `/dev/sda1`, NTFS, ya montada como
  `/run/media/tipexxx/LG_EXT_HDD` cuando sea inspeccionado;
- espacio disponible: 404.781.572.096 bytes;
- espacio utilizado existente: 95.323.643.904 bytes; se deben preservar los datos existentes;
- existe el directorio conocido `JARVIS_BACKUP/restic-repository`, incluido un
  archivo normal de 155 bytes `config`. La presencia no es prueba de integridad actual o
  identidad del repositorio descifrado.

El entorno restringido expuso los metadatos de sysfs pero no el nodo `/dev/sda`.
Las consultas de host de solo lectura fuera de ese aislamiento proporcionaron datos de partición/montaje.
No se ejecutó ningún comando de formato, montaje, reparación, partición, copia de seguridad o restauración.

Fedora `/` y `/home` son Btrfs y comparten un sistema de archivos. `df` reportado
88.891.998.208 bytes utilizados para ese sistema de archivos compartido; esas dos filas no deben ser
sumados juntos. `/boot` es ext4 separado y EFI es vfat separado. Sistema de archivos
El espacio utilizado es una estimación para la planificación, no un límite al tamaño de la copia de seguridad lógica.

## Evidencia histórica, no revalidada hoy

`deployment/host/recovery-set-plan.json` nombra un repositorio Restic respaldado por NTFS
con prefijo de identidad `e372e10c`, formato 2 y compresión automática. El runbook fuente
registra una copia de seguridad cifrada de cinco límites anterior y una comparación de restauración.
El informe de ejecución original con fecha del 7 de agosto de 2026 registra el prefijo de instantánea `0b203a54`
y evidencia del terminal de usuario. Ninguno de esos registros prueba el repositorio de hoy.
integridad, actualización de la instantánea o capacidad de arranque.

## Plan de recuperación controlada

Utilice el repositorio Restic cifrado existente si el usuario puede desbloquearlo y verificarlo.
eso. Conservar la contraseña exclusivamente en el terminal interactivo del usuario, siguiendo
`../r2-system-recovery-set.md`; nunca lo pases por chat, discusiones, ambiente
variables, archivos de proyecto o registros.

Vuelva a resolver todos los subvolúmenes de origen, incluidos los anidados declarados históricamente
Límite de máquinas systemd. Prepare cada instantánea de origen de solo lectura con un archivo separado
aprobación exacta. Incluya arranque y EFI con comprobaciones de conflicto/quiescencia. Realizar un
Nueva copia de seguridad controlada, verificación completa de los datos del paquete y restauración aislada con
el comparador independiente existente. Exclusiones de registros y la diferencia entre
restauración de archivos y un procedimiento de arranque/reconstrucción probado. Las instantáneas de origen no son
atómico a través de fronteras; preservar el límite de inclinación existente y las condiciones de parada.

Sin resolver: identidad/integridad del repositorio actual después del desbloqueo, instantánea actual
conjunto, gráfico de subvolumen completo, destino exacto de prueba de restauración y arranque/reconstrucción
procedimiento. No se podrán reemplazar datos existentes en el disco externo para resolverlos.

## Listado de repositorios informado por el usuario - 2026-09-09

La lista pegada contiene cuatro instantáneas únicas (se pegó dos veces): 00dfdb85, 06bae9b3, d28c9d2e y 0b203a54. Último: 2026-08-07 12:41:37 local, 20.035 GiB, cinco límites declarados. Esto establece metadatos de instantáneas legibles informados por el usuario, no una nueva integridad o prueba de restauración. El resultado de `restic --no-cache check --read-data` permanece pendiente. No se compartió ni almacenó ninguna contraseña.
