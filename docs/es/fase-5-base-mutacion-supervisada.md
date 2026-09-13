# Fase 5: base de mutación supervisada

## Estado de la construcción

El contrato de admisión se implementa en
`vm-lab/scripts/phase5_executor.py`. Vincula una ID/revisión de operación,
parámetros, objetivo, resumen de políticas, vencimiento, clave de idempotencia y de un solo uso
aprobación. La admisión deriva el resumen del objetivo a partir del objetivo resuelto y
requiere un resumen exacto de la política activa. Cualquier ruta futura habilitada debe atómicamente
consumir la aprobación a través del libro de autoridad confiable antes de que un adaptador pueda
tener un efecto; el libro mayor en memoria en las pruebas no es una autorización de producción.
El ejecutor está intencionalmente deshabilitado y no tiene subproceso, shell,
implementación de privilegios, redes, dispositivos o mutaciones del sistema de archivos.

La fase 4 sigue limitada al alcance de observación H1 Tier-0 registrado. la tui
puede presentar y luego enviar solicitudes mecanografiadas, pero no recibe información arbitraria
autoridad de mando. La persistencia de hechos permanece deshabilitada hasta que se cifra
El backend está vinculado explícitamente y se revisa por separado.

Se implementa el candidato `jarvis.rehearsal.marker@1.0.0` solo desechable,
aprobado de forma independiente y ha pasado un examen desechable autorizado por el usuario.
presente→ausente ensayo. Sigue sin estar registrado y deshabilitado; el ensayo
no ejecutó ni habilitó al ejecutor.

## Puertas de promoción requeridas

Antes de habilitar cualquier adaptador real:

1. elegir una operación reversible exacta y una clase objetivo;
2. implementar el adaptador sin comando arbitrario o expansión de parámetros;
3. ensayar el éxito, la interrupción, la reversión, el estado obsoleto y la validación en un
   ambiente desechable;
4. vincular el límite de autorización del sistema operativo y la evidencia de recuperación;
5. obtener una nueva revisión independiente y la aprobación explícita del usuario;
6. ejecutar un intento supervisado y verificar de forma independiente la poscondición.

Ninguna característica de TUI, respuesta del modelo o aprobación simulada puede pasar por alto estas puertas.
