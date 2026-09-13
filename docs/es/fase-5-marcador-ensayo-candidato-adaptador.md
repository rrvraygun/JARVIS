# Candidato a adaptador de fase 5: marcador de ensayo desechable

## Propósito

Este es el primer candidato para ejercer la aprobación y reversión de la Fase 5
plomería sin tocar la estación de trabajo. La implementación está en
`vm-lab/scripts/phase5_rehearsal_marker.py` y sus pruebas enfocadas están en
`vm-lab/tests/test_phase5_rehearsal_marker.py`. es un
operación de solo scratch desechable, no un adaptador de host ni una acción TUI.

## Operación exacta

- ID de operación: `jarvis.rehearsal.marker`
- revisión: `1.0.0`
- clase de destino: un directorio temporal abierto bajo un directorio de confianza independiente,
  raíz de ensayo desechable controlada por el propietario; su resumen está incluido en el
  aprobación
- parámetros: exactamente `{ "state": "present" }` o `{ "state": "absent" }`
- efecto: crea o borra solo el marcador propiedad del adaptador debajo de ese rasguño
  directorio; `absent` está representado por un marcador vacío verificado, por lo que no
  La eliminación basada en el nombre de ruta puede eliminar un inodo inesperado.
- rollback: ejecutar el estado opuesto con una nueva aprobación; sin reutilización in situ
  de una aprobación está permitido
- salida: objeto de estado limitado que contiene solo operación, resumen de destino y
  estado del marcador resultante

La implementación debe rechazar objetivos de enlace simbólico, recorrido de ruta y no propietarios.
directorios, archivos inesperados, parámetros adicionales y cualquier objetivo fuera del
raíz de ensayo desechable. No debe invocar un shell, subproceso, red,
servicio de sistema, dispositivo o ayudante privilegiado.

## Puertas de promoción

Este candidato permanece no registrado y deshabilitado hasta que se cumpla todo lo siguiente
completo:

1. implementar el adaptador únicamente contra una raíz de ensayo temporal;
2. prueba presente/ausente, marcador obsoleto, enlace simbólico, recorrido, propietario incorrecto, incorrecto
   casos de digestión, interrupción, repetición, caducidad y reversión;
3. vincularlo al libro de autoridad duradero y al límite de autorización del sistema operativo;
4. obtener una nueva revisión independiente del adaptador y la evidencia;
5. obtener la aprobación explícita del usuario para un intento de ensayo desechable.

## Resultado del ensayo

El ensayo desechable autorizado por el usuario pasó el 2026-08-07 a las
`2026-08-07T17:24:01Z`: `present` luego `absent`, resumen de destino idéntico,
marcador final vacío y limpieza temporal de raíces. La evidencia se registra en
`runtime/reports/2026-08-07-phase5-rehearsal-marker.json`. Esto no permite
el ejecutor o autorizar un adaptador de host.

El candidato no autoriza la ejecución del host, la persistencia de hechos ni la política.
mutación o cualquier derivación de TUI. Un adaptador de host independiente requeriría un nuevo
ID de operación, revisión, alcance, revisión y aprobación.
