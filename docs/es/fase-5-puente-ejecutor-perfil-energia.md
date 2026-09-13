# Fase 5 puente ejecutor de perfil de potencia preparado

El puente en `vm-lab/scripts/power_profile_executor_bridge.py` es el siguiente
paso de construcción después del adaptador de mutación PPD aprobado independientemente. es
deshabilitado y no registrado de forma predeterminada. No tiene D-Bus, shell, privilegios,
red, escritura del sistema de archivos, servicio o ruta TUI.

Antes de una futura llamada al adaptador, vincula:

- ID de operación y revisión `jarvis.powerprofile.select@1.0.0`;
- el perfil exacto solicitado/previo, las puertas de confirmación/sesión y la advertencia
  banderas a través de un resumen de parámetros canónicos;
- el objetivo fijo `tuned-ppd` D-Bus y la mutación a través de un objetivo exacto
  documentar y resumir;
- el resumen canónico de la política de autorización del perfil de energía registrado;
- una clave de aprobación e idempotencia vigente proporcionada por la autoridad duradera
  libro mayor.

El puente consume la aprobación duradera de un solo uso antes de invocar la revisión
adaptador. El backend preparado `PowerProfileAuthorityLedger` proporciona la
Implementación de SQLite controlada por el propietario y vinculada al descriptor con comprobaciones de integridad,
consumo atómico, rechazo de duplicados/idempotencia y resistencia a la repetición.
Si falla el consumo, no se llama al adaptador. Si el adaptador falla posteriormente,
la aprobación ya se ha consumido y la opción de no reversión/nueva aprobación del adaptador
se aplica la regla. El libro mayor no se abre mediante un servicio en el estado de envío y
no activa un proveedor; esos permanecen en implementación revisada por separado
decisiones.

Las pruebas de puente enfocadas utilizan objetos adaptadores y de libro mayor falsos en memoria; pruebas de libro mayor
Utilice bases de datos SQLite temporales desechables. El estado enviado permanece
`enabled=false`, sin registro en el corredor, servicio albacea o TUI.
