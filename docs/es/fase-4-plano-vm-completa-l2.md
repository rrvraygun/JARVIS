# Punto de control estructural de la Fase 4 L2: VM de estación de trabajo Fedora completa

## Resultado

El modelo no operativo para un sistema gemelo completo de Fedora Workstation es
preparado y validado por accesorios. Mantiene una instalación completa de la estación de trabajo.
y define dos perfiles de arranque sobre la misma línea base bloqueada:

- `headless_system_validation` para sistema, servicio, almacenamiento, seguridad, registro,
  pruebas de estado de paquete, contenedor y orientadas a Bash;
- `graphical_workstation_validation` para GDM, GNOME Shell, Wayland, escritorio
  portales, UPower, perfiles de energía, PipeWire/WirePlumber y virtuales
  comportamiento de visualización/entrada/audio.

El perfil sin cabeza no es un servidor Fedora ni un sustituto de contenedor mínimo.
Ambos perfiles conservan la carga útil completa de la estación de trabajo. Esto impide una prueba rápida.
ruta para evitar perder silenciosamente los paquetes, políticas, servicios o
puntos de integración que los casos gráficos posteriores necesitan.

Sin observación de preparación del host, consulta de paquete, instalación, cambio de servicio,
carga del módulo, acceso a la red, selección o descarga de imágenes de Fedora, almacenamiento
asignación, conexión de hipervisor, definición de VM, inicio de VM, instalación de invitados,
instantánea, transferencia, punto de referencia, diagnóstico de iluminación o mutación de estación de trabajo
ocurrió.

## Requisito previo de observación únicamente del accesorio

Ahora se han registrado cuatro adaptadores de analizador de nivel 0 vinculados al origen para:

1. Fedora `/etc/os-release` identidad;
2. versión del kernel y arquitectura del sistema;
3. Arquitectura de CPU, familia de proveedores/modelos, número de núcleos/hilos y virtualización
   clase de extensión;
4. memoria total y recuento de nodos NUMA.

Analizan sólo el conjunto de dispositivos sintéticos registrados. No exponen en vivo
recopilador, comando, referencia de archivo arbitrario, shell, red, privilegio,
dispositivo, persistencia, reintento o ruta de promoción de hechos del host. Su petición vincula
el registro de adaptadores, la política de intermediario, el catálogo de fuentes y la propuesta de inscripción mediante
SHA-256. Sus catorce resultados utilizan los ID de hechos exactos y los enlaces de origen de
la propuesta de inscripción y están etiquetados como datos sintéticos del candidato, nunca albergan
hechos.

Los analizadores rechazan campos duplicados, valores numéricos mal formados, inconsistentes.
Topología de CPU, arquitectura no compatible, datos no UTF-8, NUL/DEL/escape de terminal
controles, sintaxis de shell activa, campos de objetos inesperados, parámetros arbitrarios,
adaptadores desconocidos, deriva de resumen, adaptadores duplicados y solicitud en proceso
reproducir. Un intento es el límite estricto.

## Arquitectura de máquina virtual

El plano requiere:

- un artefacto oficial compatible con Fedora Workstation con firma verificada
  suma de comprobación y resumen de imagen bloqueada;
- Firmware preferido por UEFI, almacenamiento VirtIO, gráficos virtuales y sin formato físico
  paso a través;
- una base dorada de sólo lectura, limpiamente apagada;
- una nueva superposición externa por escenario y no se puede reutilizar después de ningún resultado;
- sin red en tiempo de ejecución, sistema de archivos compartido, portapapeles, arrastrar/soltar, USB host,
  Transferencia de GPU, credenciales o montaje de conocimiento/auditoría de producción;
- una ventana de aprovisionamiento de la red sólo a través de un punto de control visible separado,
  eliminado antes de la certificación inicial;
- operaciones y escenarios registrados, un intento, tiempos de espera fijos y salida
  límites, rechazo de seguridad del terminal, redacción, validación de invitados externos y
  registros de ejecución inmutables;
- selección de recursos únicamente a partir de evidencia de preparación revisada recientemente. el diseño
  se detiene en lugar de reducir silenciosamente al huésped cuando la seguridad de la estación de trabajo completa
  no se puede alcanzar el piso.

El futuro canal de control/visualización local es una identidad de diseño, no un punto final.
No se agregó ninguna autoridad de socket, servicio, transporte, agente invitado o controlador.

## CLI/sin cabeza versus evidencia gráfica

El perfil sin cabeza es preferible para pruebas de sistemas deterministas porque
utiliza menos partes móviles y no requiere una sesión gráfica en ejecución. eso
puede validar los servicios de systemd, el kernel, SELinux, el almacenamiento, el estado del paquete,
registros y procedimientos de terminal.No puede validar el inicio de sesión de GDM, el comportamiento de la sesión de GNOME/Wayland, los portales de escritorio,
exposición de la configuración gráfica, integración de energía del escritorio, entrada gráfica o
comportamiento de audio/visualización virtual. Esos requieren el perfil gráfico.

Ningún perfil puede demostrar la luminancia del panel físico, la salida del LED del teclado, real
Rieles de alimentación NVIDIA, cableado mux/pantalla, teclas de acceso rápido de firmware, controlador integrado
comportamiento, respuesta de la batería o térmicas reales. Esos siguen siendo estaciones de trabajo físicas.
lagunas que requieren una decisión de observación posterior y separada.

## Puertas de preparación y aprovisionamiento

El plan de preparación L2 define dieciocho hechos acotados y no mutantes que cubren
Compatibilidad con Fedora/arquitectura, extensiones de virtualización de CPU, memoria segura
capacidad, presencia/acceso KVM, soporte del kernel, QEMU/libvirt/virt-install y
disponibilidad de firmware, estado del servicio, administrador gráfico opcional, usuario actual
clase de acceso sin identidad, capacidad de almacenamiento/clase de sistema de archivos sin
rutas personales, SELinux, modo cgroup y clase de conflicto desinfectada.

Tres analizadores adicionales exclusivos de dispositivos ahora vinculan la pila de virtualización,
capacidad de almacenamiento/sistema de archivos y fuentes SELinux. Junto con los cuatro
Analizadores de nivel 0, cada una de las dieciocho comprobaciones de preparación tiene un adaptador exacto,
fuente, analizador, tipo de resultado, enlazado y resultado de prueba sintético. Sin backend en vivo
existe.

El plan excluye explícitamente la actualización del repositorio, las pruebas de conectividad, la instalación,
inicios de servicios, carga de módulos, cambios de permisos/grupos, sondas de paso,
puntos de referencia, nombres/definiciones de invitados, identificadores únicos, rutas personales,
secretos y contenidos. La aprobación es falsa, el backend en vivo no está resuelto y
`host_scan_performed` es falso.

La secuencia de aprovisionamiento está cerrada y ordenada:

1. P0: implemente y valide los adaptadores L2 exactos (completos para
   contratos de analizador; sin backend en vivo);
2. P1: obtenga una nueva confirmación del grupo para la preparación de solo lectura
   observación;
3. P2: si la evidencia muestra una brecha, aprobar por separado cada instalación principal o
   comando de configuración;
4. P3: aprobar la resolución oficial de metadatos y la adquisición de imágenes como distintas
   acciones de cambio de red/estado;
5. P4: aprobar el almacenamiento exacto y las acciones de creación de dominios bloqueados;
6. P5: aprobar el inicio de la VM y la instalación completa de la estación de trabajo, con
   participación del instalador si es necesario;
7. P6: sellar y certificar la línea de base apagada y ensayar el reinicio;
8. P7: ejecute solo escenarios registrados a través de superposiciones nuevas.

P1 ahora es el límite actual y está bloqueado con una nueva autorización de usuario más
una implementación, revisión y ensayo de VM de backend en vivo por separado. P2 a través
P7 permanece bloqueado. Los contratos no implican consentimiento para ninguna puerta posterior.

## Evidencia de validación

- Cuatro analizadores de dispositivos Tier-0 registrados emiten catorce datos sintéticos exactos.
- Pasan doce pruebas adversarias del analizador/corredor.
- Tres analizadores de dispositivos L2 vinculan las dieciocho comprobaciones de preparación, con doce
  pruebas contradictorias adicionales.
- El plano completo define dos perfiles de arranque completos de estaciones de trabajo.
- El plan L2 define dieciocho controles exactos de disponibilidad.
- Hay ocho puertas de aprovisionamiento ordenadas; P0 está completo, P1 está bloqueado
  en autorización, y P2-P7 están bloqueados.
- Diez pruebas adversas de planos rechazan invitados reducidos, recursos adivinados,
  paso a través, redes en tiempo de ejecución, recursos compartidos, acceso al shell de modelo arbitrario, falso
  reclamos de adaptador/escaneo y activación prematura de puerta.
- Las pruebas estáticas rechazan importaciones operativas y campos de interfaz ejecutables.

## Límite actual

El proyecto puede validar los contratos y las fijaciones sintéticas. todavía no puede
inspeccionar la estación de trabajo u operar un hipervisor. El trabajo del analizador de dispositivos P0 es
completo. Agregar cualquier backend de colección en vivo sigue siendo una revisión separada
límite bajo la instrucción existente de no escaneo.Aún no es necesaria la instalación de VM ni ninguna acción manual del instalador. El trabajo se detiene en el
Primer límite operativo visible para el usuario: si se debe autorizar la implementación.
y posterior ejecución de la observación exacta de preparación de solo lectura limitada. Sólo
Los resultados reales de P1 podrían mostrar si el trabajo de instalación o configuración de P2 es
necesario.
