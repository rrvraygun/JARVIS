# Runbook del conjunto de recuperación del sistema R2

## Reclamo actual

La línea de base inmutable del plan preparado todavía describe el estado antes del sistema.
captura. La evidencia de ejecución registrada el 6 de agosto de 2026 establece un cifrado
instantánea de Restic de cinco límites, una verificación completa de los datos del paquete sin errores reportados,
y una restauración completa en un objetivo Btrfs aislado. Ristic restaurado 281.428
archivos/directorios y verificó 179,720 archivos regulares sin un informe
fallo de verificación. El comparador independiente cubrió entonces 281.425 entradas,
incluidos 221.842 archivos normales y 21.311.943.627 bytes lógicos. informó
cero discrepancias, manifiestos de origen/restaurado iguales, sin lagunas en las pruebas y aprobados
contenido, árbol, metadatos, enlace, xattr, ACL, etiqueta SELinux, archivo disperso, arranque, EFI,
y pruebas de separación de límites. El subvolumen exacto restaurado posteriormente.
informado `ro=true`.

El estado de ejecución actual es
`r2-verified-five-boundary-restore-compared-and-retained-read-only`.
Esto establece el artefacto de recuperación R2 a nivel de archivo externo definido por el
Arquitectura de host directo. No prueba la reconstrucción con metal desnudo o
capacidad de arranque, que son preocupaciones separadas de R3 y específicas de acción. R2 es un
prerrequisito de recuperación, no una autorización general: antes de cualquier kernel, NVIDIA,
initramfs, boot, display-manager o la mutación de la pila de gráficos, Jarvis aún debe
confirmar que el artefacto está actualizado para el estado afectado, preservar un conocimiento
kernel en funcionamiento, verifique la ruta de selección de inicio de recuperación real y obtenga la información exacta
aprobación del comando.

El comando de propiedad de solo lectura se ejecutó antes de su aprobación explícita
mensaje. El comando revisado exacto se ejecutó una vez y se obtuvo el resultado deseado.
validado, pero el mensaje posterior se registra solo como post-ejecución
reconocimiento; no se presenta como autorización retroactiva. esto
La excepción de gobernanza no cambia los datos del archivo verificados independientemente, pero
sigue siendo parte de la historia de recuperación inmutable.

El plan elaborado específicamente para la máquina es
`deployment/host/recovery-set-plan.json`. Es intencionalmente no ejecutable y
tiene estado `prepared_not_executed`.

## Límites de recuperación

El primer conjunto de sistemas tiene cinco fuentes declaradas de forma independiente:

1. una nueva instantánea de solo lectura del subvolumen raíz Btrfs;
2. una nueva instantánea de solo lectura del subvolumen Btrfs de inicio;
3. una nueva instantánea de solo lectura del subvolumen Btrfs de systemd-machines anidados;
4. el sistema de archivos de arranque ext4 independiente; y
5. la partición del sistema vfat EFI separada.

Una instantánea raíz no es recursiva. No puede sustituir a casa o
systemd-machines y no puede incluir arranque o EFI. Boot y EFI no tienen la
misma instantánea Btrfs primitiva, por lo que su captura es una lectura Restic en vivo limitada
después de verificar que no haya ningún paquete, kernel, initramfs, gestor de arranque o firmware
la transacción está activa.

Las tres instantáneas de Btrfs son consistentes individualmente en un momento determinado, pero no son
atómico como grupo. El plan limita el sesgo de creación a 120 segundos e invalida
el conjunto si se supera dicho presupuesto. Los datos de la aplicación son consistentes a menos que
Posteriormente se diseña y se realiza por separado una operación de inactividad específica de la aplicación.
aprobado.

## Secuencia de ejecución cerrada

Cada mutación recibe una nueva aprobación del comando. Una falla en la operación o
una advertencia inesperada detiene la secuencia; sin reintento, reversión, limpieza,
o se permite la eliminación de instantáneas.1. Vuelva a resolver el gráfico de montaje y subvolumen, margen de espacio libre, destino,
   identidad del repositorio, estado de bloqueo y ausencia de transacciones conflictivas.
2. Cree un directorio de conjunto de instantáneas de propiedad raíz con un nombre exclusivo.
3. Cree y verifique la instantánea raíz de solo lectura.
4. Cree y verifique la instantánea de solo lectura de la casa.
5. Vuelva a resolver y tome una instantánea del límite de las máquinas systemd.
6. Confirme todas las identidades de instantáneas, propiedades de solo lectura, marcas de tiempo, sesgos y
   exclusiones explícitas.
7. Haga una copia de seguridad exactamente de las tres instantáneas más el arranque y EFI en un Restic cifrado
   instantánea, utilizando el host seudónimo y una etiqueta única establecida por el sistema.
8. Ejecute `restic check --read-data` y no requerirá advertencias ni errores.
9. Haga un inventario de la instantánea cifrada a través de Restic y verifique que los cinco
   Los alias de fuentes aprobadas están presentes sin una sexta fuente.
10. Restaure el conjunto completo en un objetivo de scratch aislado aprobado por separado.
    y comparar contenidos y metadatos de forma independiente.
11. Congele el destino temporal validado como de solo lectura y finalice el de solo agregar
    manifiesto de auditoría y recuperación versionado.
12. Conserve todas las instantáneas hasta que se apruebe una acción de retención revisada por separado.
13. Tratar imágenes de todo el dispositivo, recreación de particiones/sistemas de archivos y cifrado.
    recuperación y reconstrucción completa fuera de línea como R3. Una máquina virtual desechable o
    El dispositivo de repuesto puede opcionalmente ensayar esas mecánicas, pero no es un R2 o
    prerrequisito de desarrollo de host directo.

## Requisitos de prueba

El ensayo de un archivo ya demuestra el cifrado de archivos normales, la integridad del paquete,
reconstrucción de directorio, hash de contenido, modo y tiempo de modificación de su
alcance mínimo. El alcance del sistema debe demostrar adicionalmente propietario/grupo, ACL, extensión
atributos, etiquetas SELinux o su limitación explícita de host deshabilitado,
enlaces simbólicos, enlaces físicos, archivos dispersos, contenido de arranque y EFI, subvolumen anidado
separación y restauración completa a un objetivo de no producción.

El documento de recuperación final debe distinguir la restauración de archivos de la del disco.
reconstrucción. R2 no incluye la tabla de particiones, el encabezado LUKS ni el sistema de archivos.
creación, entradas UEFI NVRAM, configuración de firmware o material de arranque seguro
archivos externos capturados. Estos siguen siendo R3 o flujos de trabajo excepcionales separados.

## Comparador independiente de cinco límites

`deployment/host/verify_restored_boundaries.py` es el segundo, independiente de Restic
capa de verificación. No tiene subproceso, red o escritura en el sistema de archivos.
primitivo. Los descriptores de directorio y archivo normal utilizan `O_NOATIME`; los enlaces simbólicos son
nunca seguido. El comparador verifica el árbol restaurado exacto con el
tres instantáneas de Btrfs retenidas más `/boot` y `/boot/efi` en vivo, con EFI
excluido del recorrido de arranque y verificado como su propio límite.

Compara la integridad del conjunto de rutas, el tipo de archivo, el modo, UID, GID, mtime de nanosegundos,
objetivos de enlaces simbólicos, relaciones de enlaces duros, identidades de dispositivos, todo accesible
nombres y valores de atributos extendidos (incluidas las ACL POSIX, etiquetas SELinux y
capacidades de archivos), preservación lógica de archivos dispersos y contenido SHA-256 para
cada archivo normal. También rechaza una inesperada sexta raíz de restauración de nivel superior.
El informe contiene recuentos agregados y hashes únicamente. Un desajuste incluye una
token de ruta unidireccional, nunca un nombre de archivo o contenido.

La comparación aplica tres semánticas explícitas de sistema de archivos/backend sin
debilitar las comprobaciones de ruta ordinaria:- Restic 0.19.1 ignora deliberadamente los sockets Unix. Son IPC efímeros
  puntos finales, contenido de archivo no recuperable, por lo que los sockets de origen están ausentes de un
  de lo contrario, los objetivos de restauración vacíos se cuentan como avisos en lugar de faltar
  datos de recuperación.
- Restic almacena el contenido del archivo lógico, no las ubicaciones originales de extensión dispersa.
  `restore --sparse` detecta carreras cero largas y puede crear agujeros en diferentes
  posiciones. Por lo tanto, la prueba escasa requiere contenido, tamaño lógico, mtime y
  al menos un testigo escaso real restaurado; informa pero no falla
  otras diferencias en el diseño de la asignación.
- `--one-file-system` excluye los subvolúmenes Btrfs anidados. Btrfs descendientes
  Las raíces del subvolumen (inodo 256) y los límites de la instantánea (inodo 2) todavía están disponibles.
  Se requiere que existan como directorios, pero su mtime de directorio de marcadores no es
  tratado como evidencia de restauración del directorio de producción. Su independencia
  El límite de recuperación declarado sigue siendo autoritario.

Cualquier otra ruta faltante, diferencia de tiempo, diferencia de tipo/metadatos, contenido
diferencia de hash, límite anidado no reconocido o entrada de restauración inesperada
Todavía falla cerrado.

La invocación específica de la máquina es:```bash
sudo python3 \
  /home/tipexxx/Escritorio/Proyecto/codex-agent-system/deployment/host/verify_restored_boundaries.py \
  --snapshot-set /var/lib/jarvis-r2-20260806T132342Z-v2 \
  --restore-target /var/lib/jarvis-r2-restore-06bae9b3-v1/data \
  --selinux-expectation disabled-reviewed
```Salir `0` significa que cada comparación coincidió y cada característica requerida tenía al menos
un testigo fuente real. Salir `2` significa que todos los datos comparados coinciden pero al menos
una característica requerida carecía de un testigo. Salir `3` significa una discrepancia. Salir `4`
significa que la inspección completa de solo lectura no pudo continuar de manera segura. el
`disabled-reviewed` La expectativa SELinux se puede usar solo después de una corriente separada
la evidencia del huésped confirma esa limitación; no es un recurso automático.

## Contraseña y límite de privacidad

La contraseña de Restic la ingresa únicamente el usuario en un terminal interactivo. eso
nunca debe pasarse en una variable de entorno, argumento de comando, proyecto
archivo, registro de auditoría, mensaje del agente o como única copia en el disco de respaldo.
La identidad de la máquina es seudónima en los registros persistentes. Inventarios de hosts sin procesar
permanecerá prohibido hasta que exista un almacenamiento local cifrado desbloqueado por el usuario.

## Condiciones de parada

Deténgase antes o durante la configuración del sistema si cambia alguna identidad de origen/destino,
el disco externo está ausente o no es seguro, el repositorio está bloqueado o no coincide,
Aparece un nuevo límite anidado, la inclinación de la instantánea excede el presupuesto, un conflicto
la transacción está activa, una fuente es ilegible o se omite, Restic informa cualquier
advertencia, la salida se expande más allá de las cinco fuentes, el espacio libre se vuelve inseguro o
el almacén de auditoría/conocimiento no supera la verificación de integridad.
