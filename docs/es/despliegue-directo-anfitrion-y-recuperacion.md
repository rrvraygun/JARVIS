# Arquitectura de implementación y recuperación directa de Fedora

## Decisión

La única estación de trabajo Fedora inscrita es el entorno principal del producto.
Jarvis se desarrollará para su lanzamiento real, sistemas de archivos, diseño de arranque,
hardware, controladores, pila de escritorio y herramientas instaladas. Generalización a otros
Las máquinas llegan más tarde a través de nuevas revisiones de adaptadores y de inscripción.

Una máquina virtual Fedora completa es una herramienta secundaria opcional para procedimientos exclusivos de software,
Fallos del analizador, decisiones políticas y comportamiento de reinicio cuando es representativo.
y vale la pena el costo de instalación. No es un requisito previo para el desarrollo vivo en el
estación de trabajo registrada y no puede reemplazar la evidencia física de la potencia de NVIDIA,
enrutamiento del panel, brillo, iluminación del teclado, ACPI/EC, teclas de acceso rápido del firmware,
batería o térmicas.

No se permite ninguna afirmación de "reversión perfecta". Una garantía de recuperación sólo es válida
para los límites realmente capturados y restaurados en una prueba.

## Por qué una instantánea es insuficiente

Una estación de trabajo Fedora instalada con los valores predeterminados comúnmente tiene raíz Btrfs y
subvolúmenes de origen, pero el proyecto debe inspeccionar esto en lugar de asumirlo. Actualizado
o las instalaciones personalizadas pueden utilizar otro diseño. Las instantáneas Btrfs funcionan a un
límite del subvolumen y no captura recursivamente subvolúmenes anidados. un local
La instantánea también reside en el mismo dispositivo de almacenamiento, por lo que se pierde con ese
dispositivo.

`/boot` y la partición del sistema EFI son comúnmente sistemas de archivos separados y están
por lo tanto, fuera de una instantánea raíz de Btrfs. Una instantánea raíz tampoco puede revertir una
tabla de particiones, diseño de cifrado de disco, firmware flash, variable UEFI NVRAM,
o falla del dispositivo físico. El historial del administrador de paquetes puede revertirse
transacciones de paquetes cuando el estado del paquete requerido está disponible, pero no
No restaurar archivos arbitrarios, particiones de arranque, firmware o datos de usuario.

Por lo tanto, el producto de host directo necesita cuatro niveles de recuperación en lugar de uno.
indicador de instantánea genérico.

## Niveles de recuperación

### R0 — copia de registro y proyecto

Úselo para trabajos de solo lectura y desarrollo de proyectos de alcance limitado. Registre el
estado previo, delta propuesto, resultado y una copia independiente verificada del estado afectado
Archivos del proyecto Jarvis. Esto no es protección del sistema operativo.

### R1: instantánea del sistema de archivos local

Utilice un backend seleccionado del diseño observado: por ejemplo, Btrfs de solo lectura
instantáneas de cada subvolumen relevante o una instantánea LVM apropiada. Registro
el gráfico de montaje/subvolumen completo y las exclusiones explícitas. Reserva espacio libre
y detenerse si el crecimiento de la instantánea podría presionar el sistema de archivos activo.

R1 es adecuado para cambios de configuración y paquetes ordinarios solo cuando cada
La lima tocada está cubierta. No protege contra la pérdida del dispositivo de almacenamiento.

### R2: copia de seguridad externa del sistema cifrado

Replica instantáneas de solo lectura en un almacenamiento cifrado independiente o utiliza un
revisó la copia de seguridad compatible con el sistema de archivos. Captura raíz, inicio y cualquier otro elemento relevante
subvolumen de forma independiente. Capture sistemas de archivos EFI y de arranque separados a través de un
método apropiado para su sistema de archivos observado y verificar la integridad.

Para Btrfs, se requieren instantáneas de solo lectura para un envío/recepción confiable. un completo
enviar establece la base externa; futuros envíos incrementales requieren la
instantánea principal sin cambios en ambos lados. La copia externa debe ser probada por
recibirlo/restaurarlo en un objetivo de no producción antes de que se convierta en un
requisito previo de recuperación.

R2 es el piso para el kernel, el controlador NVIDIA, initramfs, argumento de arranque y pantalla.
administrador o cambios en la pila de gráficos. Preservar un kernel funcional conocido y verificar
que la ruta de selección/recuperación de inicio se pueda utilizar antes del cambio.

### R3: recuperación completa del dispositivo sin conexiónAntes de trabajar con la partición, el diseño del sistema de archivos, el gestor de arranque o el diseño de cifrado,
crear y verificar la integridad de una imagen de recuperación de todo el dispositivo sin conexión en un
destino independiente. Mantener medios de rescate de arranque de Fedora. Validar objetivo
Restauración de identidad y ensayo en un dispositivo que no sea de producción o equivalente.
ambiente controlado.

Incluso R3 no puede prometer recuperación tras la actualización del firmware o hardware no relacionado.
fracaso. Los cambios de firmware siguen siendo un flujo de trabajo excepcional independiente.

## Modos de funcionamiento del anfitrión directo

1. **Dispositivo:** modo actual. No hay lecturas ni cambios de host.
2. **Sombra:** observaciones, diagnósticos, planos y vistas previas aprobados acotados;
   sin cambios de estado.
3. **Supervisado:** un intento de cambio de estado aprobado exactamente después de su recuperación
Se verifican los requisitos previos.
4. **Lista segura obtenida:** deshabilitado inicialmente. Una revisión exacta del procedimiento puede
   convertirse en candidato a ascenso sólo después de repetidos éxitos revisados, y el
El propietario debe aprobar el cambio de política.

El modelo nunca recibe una concha de raíz arbitraria. Un futuro ayudante privilegiado
debe exponer solo operaciones registradas con objetivos y parámetros exactos. el
política, aprobación, identidad instantánea, resumen previo al estado y evidencia de recuperación
debe aplicarse fuera del modelo.

## Secuencia de transacción

Cada cambio supervisado sigue una secuencia cerrada:

1. obtener un estado nuevo y resolver un objetivo exacto;
2. clasificar cada efecto esperado, incluido el arranque, el servicio, la activación del dispositivo,
implicaciones de red y almacenamiento;
3. determinar el nivel mínimo de recuperación que cubra cada límite tocado;
4. crear y verificar el artefacto de recuperación antes de solicitar la aprobación de la mutación;
Cinco, vincular la identidad del artefacto, el estado previo, la revisión del procedimiento, el objetivo y el exacto.
   acción para la aprobación;
6. ejecutar un intento; nunca volver a intentarlo automáticamente;
7. realizar una validación independiente posterior al cambio;
8. detenerse ante un resultado/efecto inesperado o una validación fallida;
9. diagnosticar antes de decidir si la restauración es más segura que una solución directa;
10. requerir una aprobación separada para la restauración porque la restauración también es destructiva;
11. finalizar el registro de auditoría inmutable.

La reversión automática está deshabilitada deliberadamente. Un retroceso a ciegas tras un cambio parcial de
El cambio de arranque, paquete o almacenamiento puede destruir datos de nuevos usuarios o agravar la situación.
fracaso. Jarvis debe presentar qué cambió, qué cubre el artefacto de recuperación,
y las consecuencias exactas de la restauración.

## Puertas de implementación específicas de la máquina

### H1: inscripción de solo lectura limitada

La primera operación real descubre sólo lo que se necesita para elegir la recuperación.
y diseño de implementación:

- Versión, kernel, arquitectura y modo de inicio de Fedora;
- clases de sistema de archivos y montaje root/home/var/boot/EFI;
- Subvolumen Btrfs o topología LVM sin contenido de archivos personales;
- clase de cifrado sin claves ni identificadores únicos;
- clases de espacio libre acotadas;
- versiones instaladas de herramientas de instantánea, copia de seguridad, rescate, DNF y virtualización;
- kernels instalados y capacidad de recuperación de arranque sin cambiar los valores predeterminados;
- topología del proveedor de gráficos e iluminación para el primer incidente, utilizando el
  reglas de parada de activación del dispositivo previamente definidas.

Sin actualización del repositorio, evaluación comparativa, instalación de paquetes, instantánea, montaje,
inicio del servicio, carga del módulo, activación de la GPU, cambio de configuración o persistencia de
La salida sin editar sin editar pertenece al H1.

### H2 — diseño de recuperación

Producir un informe de brechas que elija los backends R1/R2/R3 a partir de evidencia real.
identifica los límites excluidos, calcula los requisitos de espacio y define el
restaurar la prueba. Lo desconocido sigue siendo desconocido. Si no existe almacenamiento independiente, R2 y
R3 sigue sin estar disponible y el trabajo de alto riesgo permanece bloqueado.

### H3/H4: establecer y probar la recuperación

Creación de instantáneas, instalación de copias de seguridad, formateo de medios externos, medios de rescate
Los ensayos de creación y restauración son operaciones manuales/de cambio de estado. Cada uno es
planificado y aprobado por separado. Ninguna acción posterior podrá utilizar un artefacto no probado como
su afirmación de seguridad.### H5: implementar el modo sombra

Ejecute Jarvis sin privilegios, mantenga el proyecto en control de versiones, use un archivo aislado
entorno Python y no otorga al intermediario acceso a shell o sudo. Máquina de tienda
hechos y datos de auditoría localmente con la redacción/cifrado ya diseñado
límites. Observe y planifique antes de agregar cualquier ejecutor.

### H6 — primer caso de iluminación

El primer flujo de trabajo físico sigue siendo el diagnóstico de brillo y luz del teclado.
bajo la hipótesis de bajo consumo de NVIDIA. La primera capa operativa es la fija.
adaptador `lighting-tier0-readonly` sin privilegios: lee solo los existentes delimitados
proveedor, adaptador, nombre del conector y metadatos del kernel filtrados. Diagnóstico
entonces puede utilizar el adaptador pasivo `lighting-tier1-platform-readonly` para
identidad de máquina no secreta, interfaces de plataforma relevantes, topología de retroiluminación,
y la identidad del dispositivo de teclas de acceso rápido candidato. El diagnóstico se detiene si una observación puede requerir
hardware de activación; sondeo de estado, clientes GPU de proveedores, registros protegidos,
Las llamadas de escritorio/sesión y el monitoreo interactivo de eventos no son parte de estos
capas. Una reparación es una nueva transacción clasificada por su valor real.
efectos (paquete, servicio, controlador, initramfs, arranque, escritorio o dispositivo) y no
ejecutar hasta verificar el nivel de recuperación correspondiente.

## Límite actual

El sistema de archivos de usuario actual controlado por aprobación de la TUI y la transacción exacta del paquete
las rutas se definen en `tui-mutation-executor.md`. Su recuperación de Papelera a nivel de operación
o la recuperación por DNF no es equivalente a la cobertura de recuperación R1-R3 a continuación. un
La confirmación gráfica de un solo uso no renuncia a una puerta de recuperación requerida por el
radio de explosión real del cambio.

La única estación de trabajo Fedora tiene una base de recuperación R2 establecida: su
Límites de Btrfs root, home y systemd-machines más arranque y EFI separados
Los sistemas de archivos se capturaron en una instantánea Restic externa cifrada. Repositorio
los datos pasaron una verificación de lectura completa y se restauró el conjunto completo de cinco límites
a un objetivo Btrfs local aislado y comparado de forma independiente con cero
desajustes y sin lagunas en las pruebas. El destino se conserva en modo de solo lectura. Esto establece
el artefacto técnico R2; no es la inscripción de Jarvis, una mutación general
aprobación, o un reclamo de dispositivo completo R3, partición, diseño de cifrado,
firmware o reconstrucción completa.

La identidad R2 verificada actual es la instantánea de Restic `d28c9d2e`, etiqueta
`jarvis-r2-system-set-20260807T090408Z`, restaurado y comparado en
`/var/lib/jarvis-r2-restore-20260807T090408Z/data` el 2026-08-07. el
comparador independiente coincidió con 285.936 entradas, incluidas 226.042 regulares
archivos, con manifiestos SHA-256 iguales, cero discrepancias y sin lagunas en las pruebas.

La vía de host directo es primaria; El VM es un ensayo opcional y no es un
Requisito previo para el trabajo en estaciones de trabajo en modo sombra. Observación de Jarvis H1 todavía
requiere su revisión de propuesta exacta por separado, corredor mecanografiado, almacenamiento restringido
backend, enlace de auditoría y registro de activación de un solo uso. Cada reparación sigue siendo un
nueva transacción. El trabajo de configuración/paquete ordinario requiere cobertura R1 nueva
del estado tocado; El trabajo del kernel/controlador/arranque/gráficos A3 requiere una corriente
Artefacto R2 más un kernel verificado que funciona y un arranque de recuperación real
ruta de selección; El trabajo de almacenamiento/cifrado/diseño del cargador de arranque A4 permanece bloqueado
R3.

### Política de instantáneas locales

Las instantáneas locales de Btrfs sin cifrar se pueden utilizar como R1 para el desarrollo de rutina.
y trabajo de configuración/código reversible. No son un sustituto de R2: lo hacen
no protege contra fallas del disco, robo, ransomware o pérdida de todo el sistema de archivos.
Cuando se almacenan dentro del sistema de archivos existente respaldado por LUKS, heredan ese
protección en reposo; un destino externo de texto sin formato no lo hace.

El artefacto R2 cifrado verificado sigue siendo obligatorio antes del kernel, NVIDIA,
initramfs, argumento de arranque, pila de gráficos, almacenamiento, cifrado o gestor de arranque
cambios. Cada operación de R1 todavía necesita un objetivo explícito, un alcance de subvolumen,
regla de retención y consecuencia de reversión.El punto R1 actual es `/var/lib/jarvis-r1-20260807T085200Z`, cubriendo el
Los subvolúmenes `root`, `home` y `var/lib/machines` como instantáneas de solo lectura. el
La evidencia del terminal proporcionada por el usuario se registra en
`runtime/reports/2026-08-07-r1-local-snapshot.json`.

## Base técnica

- Fedora Workstation ha utilizado Btrfs de forma predeterminada para nuevas instalaciones de escritorio.
  desde Fedora 33, con subvolúmenes raíz y de inicio separados; personalizado y actualizado
  Los sistemas pueden diferir.
- Las instantáneas de Btrfs tienen un alcance de subvolumen y las instantáneas de solo lectura son la base
  para replicación de envío/recepción completa o incremental.
- DNF5 proporciona deshacer y revertir el historial de transacciones, pero este es un paquete
  mecanismo de transacción, no una copia de seguridad de todo el sistema.

Referencias primarias:

- https://docs.fedoraproject.org/en-US/fedora/f33/release-notes/sysadmin/Distribution/
- https://btrfs.readthedocs.io/en/latest/btrfs-subvolume.html
- https://btrfs.readthedocs.io/en/latest/btrfs-send.html
- https://btrfs.readthedocs.io/en/stable/Send-receive.html
- https://dnf5.readthedocs.io/en/latest/commands/history.8.html

Ejemplos de implementación de la comunidad de Fedora, tratados como guía secundaria:

- https://fedoramagazine.org/working-with-btrfs-snapshots/
- https://fedoramagazine.org/btrfs-snapshots-backup-incremental/
- https://fedoramagazine.org/make-use-of-btrfs-snapshots-to-upgrade-fedora-linux-with-easy-fallback/
