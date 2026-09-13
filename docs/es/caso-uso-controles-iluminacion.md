# Caso de uso preparado: brillo de la pantalla e iluminación del teclado

## Informe de usuario

> El brillo de la pantalla y la iluminación del teclado parecen dejar de funcionar cuando el
> La GPU NVIDIA está apagada según la configuración actual de bajo consumo.

Esta afirmación es un informe de síntomas y una hipótesis causal, no un hecho verificado.
El diseño de diagnóstico preserva ambos mientras prueba la relación.

## Puntos de entrada admitidos

El mismo caso puede comenzar a través de cualquiera de las interfaces:

- lenguaje natural, incluidas frases como "el brillo dejó de funcionar"
  "las teclas de luz del teclado no hacen nada" o "esto sucede cuando NVIDIA está en modo de suspensión";
- la acción de catálogo `health.lighting.diagnose@1.0.0` y su forma mecanografiada.

Ambos crean el mismo tipo de tarea y utilizan el mismo procedimiento. El formulario del catálogo.
captura los controles afectados, la fuerza de la correlación de NVIDIA informada,
inicio, desencadenante, comportamiento de visualización externa y notas.

## Viaje del usuario preparado

1. Seleccione **Diagnosticar iluminación de pantalla y teclado** o describa el problema.
2. Revise el síntoma capturado y confirme que no se haya ejecutado ningún comando.
3. Revise la vista previa exacta del adaptador de nivel 0 delimitado; solo lee en lista permitida
   metadatos sysfs/proc y no activa intencionalmente los dispositivos.
4. Ejecute la observación de Nivel 0 registrada una vez, seguida sólo cuando lo justifique
   el observador pasivo de plataforma/proveedor de nivel 1. Registros protegidos, bus de sesión
   La activación o un monitor de teclas de acceso rápido interactivo reciben puertas separadas.
5. Revisar la evidencia por capa y las hipótesis clasificadas.
6. Si las pruebas son insuficientes, aprobar sólo el siguiente control discriminatorio.
7. Seleccione **Preparar una reparación de iluminación** después de revisar un diagnóstico.
8. Revisar una intervención exacta, su estado previo, validación, recuperación y
   revisión independiente.
9. En una futura versión de etapa 4, apruebe un comando exacto de cambio de estado.
10. Valide el brillo de la pantalla, la iluminación del teclado, las teclas de acceso rápido, el estado de la sesión,
    suspender/reanudar, disponibilidad de GPU y objetivo de bajo consumo.

El paso 3 y las partes de Nivel 0 y de nivel 1 de plataforma/proveedor pasivo del paso 4 son
ejecutable en la estación de trabajo registrada bajo H1 activo de solo lectura limitado
autoridad. Integración de sesiones, evidencia protegida, observación interactiva,
comparación de estados, y cada reparación permanece separada, no implementada, protegida,
o controlado por aprobación como se describe a continuación.

## Separación diagnóstica

| Capa | Evidencia para comparar | Conclusión que puede respaldar |
|---|---|---|
| Retroiluminación de la pantalla | Conjunto de proveedores, brillo solicitado/real/máximo, tipo, potencia | Presencia y comportamiento del control de visualización del kernel |
| Iluminación del teclado | Proveedores de LED, brillo/máx., exposición a UPower | Presencia de control de teclado en el kernel y el espacio de usuario |
| Teclas de acceso rápido | Pulsación de tecla por parte del usuario, evento de entrada, cambio de firmware, indicación de escritorio | Dónde se detiene el evento de control |
| Integración de escritorio | GNOME, UPower, perfil de energía, exposición al servicio | Si el control de sesión/UI difiere del estado del kernel |
| Topología de gráficos | Adaptadores, controladores, conectores y enrutamiento integrados/discretos | Si el panel interno puede depender de una GPU alimentada |
| Potencia en tiempo de ejecución | Estado de tiempo de ejecución de la GPU con marca de tiempo | Correlación con cambios de proveedor/enrutamiento |
| Historial de versiones/cambios | Kernel, controlador, paquetes, parámetros de arranque, advertencias de arranque actual | Hipótesis de regresión o configuración |

La iluminación de la pantalla y el teclado comparten un informe, pero no necesariamente un controlador o
camino de control. Un solo fallo puede afectar a ambos a través del firmware o de la política energética;
También son posibles dos fallos simultáneos.

## Hipótesis que el agente debe distinguir- Un proveedor de retroiluminación o LED del teclado desaparece cuando un dispositivo/estado de tiempo de ejecución
  cambios.
- Los proveedores permanecen presentes pero los valores solicitados no llegan al hardware.
- Los proveedores de kernel funcionan mientras que la integración de UPower o GNOME no.
- El firmware maneja las teclas de acceso rápido de manera incorrecta o no emite un evento.
- Un perfil de energía o una política de escritorio atenúa/deshabilita un control según lo diseñado.
- El enrutamiento del panel interno en realidad depende de la GPU discreta en esta topología.
- El estado de NVIDIA simplemente se correlaciona con una transición de bajo consumo diferente.
- Una actualización del kernel, controlador de gráficos, escritorio, firmware o configuración causó
  una regresión.

No se selecciona ninguna hipótesis antes de que exista evidencia real.

## Artefactos preparados

- Catálogo: `plugins/jarvis-system-admin/registry/actions.json`
- Procedimiento de diagnóstico:
  `plugins/jarvis-system-admin/registry/procedures/lighting-diagnose.json`
- Procedimiento de reparación:
  `plugins/jarvis-system-admin/registry/procedures/lighting-repair.json`
- Mapa de evidencias no ejecutables:
  `plugins/jarvis-system-admin/registry/collector-plans/lighting-controls.json`
- Política de recopilador de nivel 0 ejecutable:
  `plugins/jarvis-system-admin/registry/collectors/lighting-tier0.json`
- Adaptador de sistema de archivos fijo Tier-0:
  `plugins/jarvis-system-admin/scripts/collect_lighting_tier0.py`
- Política de recopilador pasivo de nivel 1 ejecutable:
  `plugins/jarvis-system-admin/registry/collectors/lighting-tier1-platform.json`
- Adaptador de plataforma/proveedor pasivo fijo de nivel 1:
  `plugins/jarvis-system-admin/scripts/collect_lighting_tier1_platform.py`
- Política de recopilador de enlace WMI pasivo ejecutable de nivel 2:
  `plugins/jarvis-system-admin/registry/collectors/lighting-tier2-wmi-binding.json`
- Adaptador de enlace WMI pasivo fijo de nivel 2:
  `plugins/jarvis-system-admin/scripts/collect_lighting_tier2_wmi_binding.py`
- Política de asociación de proveedores/conectores de nivel 3 aprobada:
  `plugins/jarvis-system-admin/registry/collectors/lighting-tier3-connector-association.json`
- Adaptador de asociación eDP de nivel 3 fijo:
  `plugins/jarvis-system-admin/scripts/collect_lighting_tier3_connector_association.py`
- Referencia de habilidades de diagnóstico:
  `codex/skills/system-health/references/lighting-controls.md`
- Referencia de habilidad de reparación:
  `codex/skills/system-repair/references/lighting-repair.md`

## Estado de seguridad actual

- La acción de diagnóstico está preparada y no mutante. Su primera observación
  La capa se implementa mediante un adaptador de nivel 0 fijo y sin privilegios con un solo intento.
  comportamiento y salida acotada.
- El mapa de coleccionista más amplio conserva `execution_enabled: false`: es un diseño
  mapa para capas protegidas/de sesión posteriores y no contiene ningún comando ejecutable
  matrices. Esto no deshabilita el adaptador de nivel 0 registrado por separado.
- El nivel 0 lee directamente solo los valores de proveedores incluidos en la lista permitida, los metadatos del adaptador,
  nombres de conectores (nunca estado del conector) y gráficos/luz de fondo filtrados
  contexto del núcleo. No inicia ningún subproceso, no realiza ninguna llamada de red/D-Bus y
  no realiza ninguna escritura en dispositivo o sysfs.
- El nivel 1 pasivo lee solo campos de identidad DMI no secretos, incluidos en la lista permitida
  nombres de plataforma/módulo, topología de bus/controlador de retroiluminación, nombres de LED candidatos,
  e identidad del dispositivo de entrada candidato. Excluye explícitamente números de serie, UUID,
  eventos de entrada, campos de entrada físicos/únicos, D-Bus, registros, subprocesos,
  estado del conector y todas las escrituras.
- El nivel 2 pasivo está limitado a la instancia GUID WMI de brillo fijo de NVIDIA
  nombres, sus nombres de enlace del controlador, el valor del módulo de solo lectura `force` y
  nombres/tipos de proveedores de retroiluminación registrados. Nunca evalúa un método WMI,
  vincula un controlador o escribe un parámetro de módulo.
- El adaptador de asociación de nivel 3 aprobado solo lee la identidad de la tarjeta DRM,
  estado del conector eDP interno y objetivos de enlace simbólico del proveedor de retroiluminación fijos.
  Las lecturas del estado del conector pueden activar el hardware de la pantalla; este efecto se revela
  y aprobado por separado. No realiza escrituras, llamadas WMI/ACPI, llamadas D-Bus,
  subprocesos, lecturas de registros o lecturas de eventos de entrada.
- La acción de planificación de reparación puede representar un plan futuro pero no puede cambiar el
  anfitrión.
- La acción de ejecución de reparación es visible y no está disponible.
- Sin alternancia de GPU, escritura sysfs, operación de módulo, cambio de servicio, cambio de paquete,
  Hay un cambio de parámetro de arranque o un comando privilegiado.

## Diagnóstico actual del huésped inscrito (2026-08-06)El síntoma confirmado por el usuario se registra por separado de la evidencia de la máquina: GNOME
muestra la respuesta del atajo, pero ni el brillo físico de la pantalla ni
La iluminación del teclado cambia. La observación pasiva de Nivel 2 encontró entonces la
Instancia GUID WMI de brillo de NVIDIA presente, el directorio del controlador correspondiente
presente, sin instancia GUID vinculada, `force=false`, y solo el archivo sin formato
Proveedores de `intel_backlight` y `nvidia_0`. Combinado con el filtrado anterior.
`acpi_backlight=native` parámetro de arranque, esto genera una discrepancia en la selección del proveedor
La hipótesis de la demostración de alta confianza. Upstream Linux da una explicación explícita
`acpi_backlight` Prioridad de configuración de la línea de comandos y controlador NVIDIA WMI EC
normalmente espera la selección `nvidia_wmi_ec`.

La conclusión del teclado sigue siendo separada y de menor confianza: no hay estándar
`kbd_backlight`/`kbd_zoned_backlight` Proveedor de LED o LED de teclado candidato fue
observado. El `acer-wmi` actual ascendente reconoce el AN515-58 y maneja un
evento automático de tecla de luz de fondo del teclado, pero esto no establece un
Backend LED de teclado estándar en el kernel instalado. El apagado de NVIDIA
La correlación aún no está probada porque no se realizó ninguna comparación controlada de estado de potencia.
realizado.

El registro completo respaldado por evidencia es
`runtime/reports/2026-08-06-recovery-bootstrap/diagnosis-lighting-controls-tier2-correlated.json`.
Las próximas puertas seguras son una observación pasiva de la transición de brillo, una
verificación de exposición de sesión/UPower de solo lectura controlada por separado para el teclado, y,
Sólo si es necesario, se elimina una comparación de arranque única con `acpi_backlight=native`.
Este diagnóstico no aprueba ninguna reparación.

## Resultado de la asociación del conector de nivel 3 (2026-08-06)

El conector limitado aprobado por separado leído encontrado `card1-eDP-1` conectado
en Intel `i915` (`0000:00:02.0`). Los candidatos a proveedores de firmware relevantes son
`acpi_video1` y `acpi_video2`; `acpi_video0` pertenece a los desconectados
Conector NVIDIA `card0-eDP-2`. Esto hace que la ruta del proveedor integrado sea la
objetivo de alta confianza para una futura prueba de visualización, aunque aún no se demuestra que
cualquiera de los proveedores aplica luminancia física.

El resultado se registra en
`runtime/state/snapshots/2026-08-06-lighting-tier3-connector-association-live.json`
y diagnosticado en
`runtime/reports/2026-08-06-recovery-bootstrap/diagnosis-lighting-controls-tier3-connector-association-revision-1.json`.

Ahora están preparadas dos puertas distintas:

1. `prepared-display-provider-write-test-v1.json` define uno reversible,
   escritura limitada a exactamente un proveedor integrado recién seleccionado. eso
   requiere captura del estado actual, una aprobación de comando exacta, inmediata
   relectura, confirmación del usuario del efecto físico y reversión.
2. `prepared-keyboard-upower-observation-gate-v1.json` define un separado
   consulta de sesión/UPower de solo lectura. Requiere aprobación separada porque D-Bus
   puede ocurrir la activación del servicio. Prohíbe todos los métodos y firmware de mutación.
   llamadas.

Ninguna puerta se ha ejecutado. La escritura en pantalla permanece no disponible hasta que
el usuario aprueba el objetivo y el comando exactos; la observación del teclado permanece
cerrado por separado.

## Resultado de escritura de proveedor limitado (2026-08-06)

La prueba aprobada por el usuario cambió `acpi_video1` de 96 a 86 y luego se restableció
96. El usuario confirma que el panel cambió visiblemente, pero sólo mínimamente. esto
acredita que el proveedor integrado llega al hardware físico; no lo hace
demuestre que el rango de 0 a 100 del proveedor es un rango de luminancia efectivo. el
La hipótesis principal actual es la curva de transferencia o escalado de firmware/proveedor.
comportamiento, con `acpi_video2` y la ruta nativa de Intel aún sin probar en
aprobación separada.

El resultado se registra en
`runtime/reports/2026-08-06-recovery-bootstrap/diagnosis-lighting-controls-provider-write-revision-2.json`.
Esta observación no autoriza más escrituras.

## Resultado de la reparación confirmado por el usuario (2026-08-06)

Esta es una confirmación del usuario, no una nueva observación de la máquina por parte de Jarvis.
adaptadores de solo lectura:

- El brillo de la pantalla ahora aumenta y disminuye correctamente después de que el usuario
  reparación de arranque/configuración.
- La iluminación del teclado y su método abreviado de teclado ahora funcionan.
- El usuario también confirmó que el menú interactivo de Acer RGB puede seleccionar colores
  y efectos de animación repetidamente.El resultado del teclado utiliza una configuración no oficial del controlador del kernel Acer RGB mantenida
fuera de este paquete. La integración de host informada incluye un `facer` firmado
módulo, `/opt/acer-predator-rgb`, el ayudante de configuración
`/usr/local/sbin/acer-rgb-setup`, y el habilitado
`acer-rgb-setup.service`. Estas rutas y el estado del servicio son hechos de implementación.
que deben volver a observarse en el host registrado antes de que Jarvis los presente como
actualmente activo. Sin embargo, el éxito visible para el usuario es suficiente para
cerrar el informe de síntomas manual original manteniendo el diagnóstico del adaptador
y puertas de ejecución de reparación sin cambios.

## Criterios de aceptación antes del primer uso en vivo de nivel 0

- Cada lectura de Nivel 0 se implementa en el adaptador revisado fijo con estrictas
  límites de campo y proveedor, redacción, resultado esperado, análisis cerrado por error,
  y comportamiento de un solo intento.
- Se excluyen las lecturas que se sabe o se sospecha que activan una GPU suspendida; conector
  El estado, los clientes de GPU del proveedor, las consultas de configuración de PCI, D-Bus y los registros son
  prohibido por el registro de nivel 0.
- La TUI distingue un plan de una observación en marcha.
- El usuario puede inspeccionar y cancelar cada observación no instantánea.
- Los registros protegidos y el monitoreo interactivo de eventos no pueden iniciarse automáticamente.
- Una comparación de estados no puede cambiar silenciosamente la GPU o el modo de energía.
- El laboratorio de accesorios cubre proveedores faltantes/múltiples/mal formados,
  denegación de permiso, resultados distintos de cero, tiempo de espera, salida de terminal hostil,
  efectos inesperados, conflictos de escritorio, conflictos de correlación de NVIDIA y
  contextos de visualización externa en todo el espacio de estado de iluminación fijado.
- El ejecutor de reparación permanece ausente hasta que una reparación diagnosticada tenga un tipo fijo
  adaptador, cobertura de accesorios adversarios, evidencia de recuperación de acciones específicas,
  aprobación de comando exacta y validación posterior a la condición independiente. Una máquina virtual Fedora
  Opcionalmente, puede ensayar un comportamiento representativo solo del software, pero no es
  requerido y no puede validar la iluminación física o la ruta de alimentación de la GPU.

Nivel 0, nivel 1 de plataforma/proveedor pasivo y nivel 2 de enlace WMI pasivo
Los adaptadores cumplen los criterios de primer uso en vivo sólo para sus capas estrechas.
Integración de escritorio/sesión, registros protegidos, monitoreo interactivo de teclas de acceso rápido,
y la comparación entre transiciones de energía requieren sus propios adaptadores y puertas.
El conector de nivel 3/adaptador de asociación de proveedores está aprobado solo para
única investigación actual y no debe generalizarse en una lista segura.

El límite del partido completado y las reclamaciones físicas que siguen siendo imposibles
para probar en una VM normal se registran en
`phase-4-vm-lab-prerequisite.md` y
`../vm-lab/coverage/physical-gaps.json`.

## Referencias técnicas primarias

- Soporte de retroiluminación de Linux: https://docs.kernel.org/gpu/backlight.html
- Nombres de luces de teclado y LED de Linux:
  https://www.kernel.org/doc/html/latest/leds/leds-class.html
- Gráficos híbridos de Linux: https://docs.kernel.org/next/gpu/vga-switcheroo.html
- Retroiluminación del teclado UPower:
  https://upower.freedesktop.org/docs/KbdBacklight.html
- Selección de retroiluminación ACPI de Linux:
  https://github.com/torvalds/linux/blob/master/drivers/acpi/video_detect.c
- Controlador de retroiluminación Linux NVIDIA WMI EC:
  https://github.com/torvalds/linux/blob/master/drivers/platform/x86/nvidia-wmi-ec-backlight.c
- Controlador WMI de Acer para Linux:
  https://github.com/torvalds/linux/blob/master/drivers/platform/x86/acer-wmi.c
