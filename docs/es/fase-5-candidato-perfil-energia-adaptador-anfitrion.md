# Candidato a adaptador de host de fase 5: selección de perfil de potencia

Este es un candidato de solo diseño para el primer adaptador de estación de trabajo real. es
no implementado, registrado o accesible desde la TUI.

El descubrimiento del proveedor no encontró ningún `powerprofilesctl` binario o independiente
demonio de perfiles de energía. TuneD y `tuned-ppd` ahora están activos y la configuración personalizada
El perfil `jarvis-balanced` se verifica correctamente. el estandar
`org.freedesktop.UPower.PowerProfiles` API informa `balanced` a través del
`balanced=jarvis-balanced` mapeo. La evidencia de la configuración se registra en
`runtime/reports/2026-08-07-power-profile-provider-activation.json`.
El adaptador de mutación Jarvis aún no está implementado, registrado ni accesible
de la TUI.

## Adaptador de estado de solo lectura

El primer paso de construcción se completa en
`vm-lab/scripts/power_profile_status.py`. Está vinculado al bus del sistema fijo.
nombre, ruta del objeto y llamada `org.freedesktop.DBus.Properties.GetAll`. eso
normaliza solo los tres nombres de perfil PPD y el controlador fijo `tuned`,
acepta sólo los valores de estado degradado definidos por TuneD, rechaza valores desconocidos o
respuestas del proveedor inconsistentes y emite un objeto de estado `read_only` redactado.
no tiene
`Set`, `HoldProfile`, `ReleaseProfile`, subproceso, escritura del sistema de archivos o TUI
camino de mutación. La cobertura enfocada está en
`vm-lab/tests/test_power_profile_status.py`. El adaptador no está registrado con
el corredor o albacea en vivo pendiente de revisión independiente.

## Ensayo de transición desechable

El simulador en memoria de
`vm-lab/scripts/phase5_power_profile_rehearsal.py` ejercicios
`balanced -> performance -> balanced` y `balanced -> power-saver -> balanced`
con controles exactos de poscondición y reversión. No tiene D-Bus, sistema de archivos,
ejecutor o ruta del host. El exitoso ensayo está grabado en
`runtime/reports/2026-08-07-power-profile-transition-rehearsal.json` y lo hace
no autorizar un cambio de perfil en vivo.

## Operación exacta

- ID de operación: `jarvis.powerprofile.select`
- revisión: `1.0.0`
- objetivo: solo el servicio de perfil de energía de la sesión del usuario local actual
- parámetros: exactamente una enumeración: `power-saver`, `balanced` o `performance`
- efecto: solicitar ese perfil a través del perfil de energía escrito en la plataforma
  interfaz; sin ejecutable arbitrario ni expansión de argumentos
- revertir: lea y registre el estado previo, luego solicite ese perfil exacto con
  una nueva aprobación si es necesario revertir
- validación: lea el perfil activo después de la operación y solicite información exacta
  igualdad con la enumeración aprobada

## Puertas requeridas antes de la implementación

1. observe el proveedor de perfil de energía instalado y la enumeración de perfiles admitidos
   sin cambiar de estado;
2. vincular el adaptador a una API de proveedor fija y al objetivo exacto de la sesión de usuario;
3. definir la autorización del sistema operativo/límite de Polkit y la evidencia de recuperación;
4. ensayar las transiciones de perfiles en un entorno desechable o documentado
   simulador de proveedores;
5. obtener una nueva revisión independiente y aprobación explícita para un perfil
   cambiar;
6. realizar un intento supervisado, verificar la poscondición y registrar el
   perfil anterior para revertir.

El candidato debe rechazar perfiles desconocidos, deriva de proveedores, deriva de objetivos,
estado previo obsoleto, reversión no admitida y cualquier solicitud que pueda activar dispositivos,
cambiar la configuración del kernel, alterar la persistencia o ampliar a comandos arbitrarios.

## Perfil TuneD compatible con el host

El perfil genérico `balanced` de Fedora está activo en este Acer Nitro 5, pero su
La verificación incluye interfaces de hardware que hace este host Intel P-state.
no exponer (el módulo gobernador conservador, impulso por CPU, plataforma ACPI
perfil y ALPM en cada host SCSI). El perfil de host reproducible en
`vm-lab/profiles/tuned/jarvis-balanced/tuned.conf` gestiona deliberadamente sólo
los controles observados aquí: el gobernador `powersave`, `balance_performance`
preferencia de rendimiento energético y tiempo de espera de audio. no se altera
Configuración de NVIDIA, ALPM de disco, política turbo, parámetros del kernel o externos
dispositivos. Debido a que la API PPD estándar expone el nombre `balanced`, su
El mapeo `[profiles]` debe apuntar a `balanced=jarvis-balanced`; de lo contrario PPD
informa correctamente el nombre personalizado de TuneD como `unknown`.

## Límite de autorización del sistema operativo definido

El límite aprobado se registra en
`vm-lab/controller/power-profile-authorization-policy.json` y validado por
`vm-lab/scripts/power_profile_authorization.py`:- la persona que llama debe ser la sesión de usuario activa actual y la TUI debe proporcionar
  una confirmación explícita; se utiliza el permiso Polkit del proveedor existente,
  sin necesidad de solicitar una contraseña por separado;
- se permiten los tres perfiles estándar, con exactamente una transición por
  Autorización de un solo uso de 60 segundos almacenada en la autoridad duradera existente
  libro mayor;
- la única mutación futura es la propiedad fija PPD `ActiveProfile` a través de
  `org.freedesktop.UPower.PowerProfiles`; sin sudo, shell, `tuned-adm`, directo
  sysfs, control NVIDIA, retenciones, conmutación automática o parámetros arbitrarios;
- los estados de batería, degradación térmica y degradación del proveedor generan
  notificaciones pero no bloquean la solicitud;
- una poscondición fallida se detiene y explica el problema. La reversión nunca es
  automático y requiere una nueva aprobación por separado.

Este es únicamente un contrato de admisión. La póliza y el validador no llaman.
D-Bus, Polkit, el libro mayor o el TUI, y el adaptador de mutación permanece
no registrado.

## Adaptador supervisado preparado

`vm-lab/scripts/power_profile_mutation.py` implementa el D-Bus fijo
`ActiveProfile` transición contra un transporte inyectado para pruebas y un
Transporte de sistema fijo-bus para un futuro despliegue. Lee y valida el
pre-estado, realiza una llamada de establecimiento exacta, valida el post-estado y envía
advertencias de solo notificación a través de una devolución de llamada de mejor esfuerzo antes del configurador para que
permanecen visibles incluso si la mutación o la poscondición falla. Notificación
La entrega en sí nunca bloquea la operación aprobada. El adaptador se detiene sin
reversión automática en caso de fallo del colocador o de la poscondición. No consume el libro de autoridad en sí;
el ejecutor debe consumir la aprobación duradera de un solo uso antes de cualquier futuro
registro. El adaptador no está registrado con el ejecutor, corredor,
servicio o TUI.
