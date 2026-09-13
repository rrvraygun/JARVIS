# Expansión de expertos en energía

**Estado:** implementación activa
**Actualizado:** 2026-08-30

## Alcance

Power Expert es seleccionable por el usuario y recibe energía de hardware/software desinfectada
evidencia, estado del proveedor, evidencia del paquete y telemetría limitada. Es compatible
diseño manual de perfiles para objetivos de usuario (`battery`, `performance`, `quiet`,
`thermal` y `balanced`) con variantes de CA y batería emparejadas.

La pestaña Energía sigue siendo el panel en vivo. La conversación es la entrada dirigida por el agente.
punto. El especialista seleccionado por el usuario tiene autoridad; Power Expert no
cambiar de especialista automáticamente.

## Inventario y telemetría

El inventario de solo lectura informa la topología de CPU/GPU, batería/suministros de CA,
proveedores, herramientas de software, datos de clase de modelo de firmware, configuraciones admitidas,
conflictos y limitaciones del proveedor. Identificadores únicos como números de serie y
Los UUID no están expuestos. La telemetría en vivo lee la capacidad/estado/velocidad de la batería,
Estado de CA, valores térmicos pasivos y perfil de escritorio activo. La encuesta es
limitado y solo se ejecuta mientras la pestaña Energía está activa.

La detección de proveedores incluye las rutas actuales TuneD/tuned-ppd y kernel más
descubrimiento de solo lectura de TLP y auto-cpufreq. Múltiples proveedores de pólizas están
reportados como conflictos y bloquear escrituras de perfil hasta que se resuelva la propiedad.

## Perfil y contrato de mutación

Los perfiles son documentos JSON versionados solo para propietarios con variantes de CA/batería,
objetivos, controles seleccionados en la lista permitida y un resumen estable. El determinista
El planificador utiliza solo controles expuestos por adaptadores y listas revisados actualmente.
valores no admitidos explícitamente.

Cada transacción también persiste en un `PowerProfileApplicationRecord` versionado
al lado del perfil. Vincula el resumen del perfil y registra el AC o
variante de batería, estado previo exacto, valores solicitados, valores resultantes verificados,
comparaciones de tres vías con controles modificados, controles sin cambios, motivos omitidos,
estado, marca de tiempo y metadatos de recuperación. Sólo una respuesta de ayuda exacta cuya
post-estado coincide con los controles solicitados es `applied`; fallido o interrumpido
las transacciones permanecen `failed`/`indeterminate` y nunca se procesan como exitosas.
Los registros no válidos o que no coinciden con el resumen se ignoran al reiniciar.

El registro de capacidades está versionado en
`plugins/jarvis-power-expert/registry/power-capabilities.json`, y el perfil
El contrato por cable es `registry/power-profile.schema.json`.

Las transacciones del perfil actual admiten el perfil de energía revisado, CPU EPP,
CPU turbo y controles de política de tiempo de ejecución Intel/NVIDIA. El ayudante de propiedad raíz
captura el estado previo de cada control, escribe un registro de recuperación de perfil preparado,
aplica una transacción de control múltiple exacta y verifica todo el estado posterior. un
La aprobación única cubre el conjunto validado inmutable. Queda ejecución parcial
indeterminado y requiere una reversión previa al estado exacta aprobada por separado.

Los controles de frecuencia/térmicos y de nivel de proveedor se representan como capacidad
profundidades, pero se vuelven ejecutables solo a través de sus propios adaptadores fijos revisados.
No se aceptan escrituras sysfs genéricas ni comandos de proveedores arbitrarios.

## Recomendaciones de paquetes

Power Expert puede realizar búsquedas de paquetes Fedora en caché de sólo lectura y recomendar
Paquetes RPM o identificadores de grupo. Crea una tarjeta de traspaso pendiente visible;
el usuario debe seleccionar explícitamente Especialista en instalación antes de la vista previa del paquete,
aprobación o mutación. Power Expert no ejecuta cambios de paquetes en este
liberación. La actualización de la documentación requiere la aprobación explícita de la red.

## comportamiento de la TUI

La pestaña Energía muestra evidencia de proveedor/software/hardware, telemetría en vivo, información actual
configuración, redacción de perfiles, controles de guardado/vista previa/activación y estado de transferencia.
La conversación y el contexto Power Expert seleccionado reciben una confirmación duradera
que contiene configuraciones anteriores, solicitadas y resultantes más parámetros esperados deterministas.
impacto. Control único manual existente
Los controles Power Apply y Undo permanecen disponibles y continúan usando los mismos
límites de aprobación y recuperación.Power Expert utiliza las herramientas MCP Power registradas bajo un agente de solo lectura
caja de arena. El agente puede presentar una propuesta de activación, pero el corredor de TUI debe
consumir una nueva aprobación exacta antes de invocar al ayudante registrado; el ayudante
luego realiza la autorización de escritorio por separado y la verificación posterior al estado.

Las solicitudes de energía en lenguaje natural se enrutan a través del Power Expert seleccionado
agente. El agente posee aclaraciones, decisiones de perfil, recomendaciones y
explicaciones y utiliza herramientas Power MCP mecanografiadas para evidencia, redacción, validación,
puesta en escena de aprobación, verificación y recuperación. Quedan respuestas aclaratorias
Separe las entradas visibles y nunca caiga en un shell/búsqueda genérico.
aprobación del comando.

La pestaña etiqueta la variante seleccionada automáticamente (`Preview variant` mientras
redacción, `Applied variant` después de la verificación), mantiene el último resultado aplicado
separar del borrador actual y asignar inventario y configuraciones iguales
Regiones receptivas con desplazamiento independiente y ajuste acotado.
