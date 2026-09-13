# Runbook de instalación y operaciones

Este repositorio sigue siendo un paquete revisable en lugar de un repositorio activo sin restricciones.
agente. La única estación de trabajo Fedora está inscrita para lectura limitada.
observación y existe un artefacto de recuperación de R2 externo verificado. ningún general
Se ha activado el privilegio de ejecutor de host o autónomo. el por separado
implementado, el asistente de paquete mediado por Polkit puede aplicar sólo la información exacta,
transacciones de paquetes vinculados a un resumen preparados por la TUI; ver
[`current-product-state.md`](estado-actual-producto.md).

## Revisión

1. Lea `AGENTS.md` y `docs/shared-contract.md`.
2. Inspeccione el agente TOML, todas las habilidades, ganchos y scripts seleccionados.
3. Ejecute `scripts/validate-bundle.sh`.
4. Revisar `vm-lab/README.md` y sus vacíos físicos explícitos.
5. Revisar `vm-lab/controller/README.md` y la inscripción no aprobada
   propuesta antes de diseñar cualquier coleccionista.
6. Revise `docs/phase-4-l2-full-vm-blueprint.md`, el plan de preparación L2 exacto,
   y las ocho puertas de aprovisionamiento antes de considerar el trabajo de virtualización.
7. Revise `docs/direct-host-deployment-and-recovery.md`,
   `docs/r2-system-recovery-set.md`, y
   `deployment/host/policy.json` antes de registrar la estación de trabajo.
8. Ejecute pruebas en `tests/`; no comience con un anfitrión privilegiado en vivo.

## Activación

Copie los archivos seleccionados en `.codex/` de un repositorio confiable solo después de revisarlos.
No fusionar ciegamente `codex/jarvis.config.example.toml`; reconciliarlo con
configuración existente.
Comience solo con `deep-research`, `system-inventory`, `system-health`,
`system-state` y `system-knowledge`. Mantenga las habilidades de mutación desinstaladas hasta
su evaluación pasa.

## Primera operación en vivo

Solicite un inventario de solo lectura. Revisar cada recopilador propuesto y aprobar únicamente
acceso de lectura adicional que esté justificado. Inspeccionar la redacción y el estado almacenado.
Luego establezca líneas de base de salud. Habilite un flujo de trabajo mutante a la vez.

Inicialice el almacén de conocimientos y los registros de fuentes/comandos en un tiempo de ejecución privado
directorio:```bash
python3 plugins/jarvis-system-admin/scripts/knowledge_store.py \
  --db runtime/knowledge/knowledge.db init
python3 plugins/jarvis-system-admin/scripts/knowledge_store.py \
  --db runtime/knowledge/knowledge.db seed-sources
python3 plugins/jarvis-system-admin/scripts/knowledge_store.py \
  --db runtime/knowledge/knowledge.db seed-catalog
```Indexe la documentación instalada en la lista permitida sin acceso a la red:```bash
python3 plugins/jarvis-system-admin/scripts/index_local_docs.py \
  --output runtime/documentation/local.jsonl
python3 plugins/jarvis-system-admin/scripts/knowledge_store.py \
  --db runtime/knowledge/knowledge.db import-docs \
  runtime/documentation/local.jsonl
```Obtenga una vista previa del recopilador de Fedora antes de la versión de solo lectura en vivo autorizada por separado
inventario:```bash
python3 plugins/jarvis-system-admin/scripts/collect_fedora_inventory.py \
--output runtime/state/snapshots/fedora-inventory.json --preview
```Estos comandos se escriben solo dentro del tiempo de ejecución del proyecto. El coleccionista nunca usa
privilegios, reintentos, acceso a la red o comandos de cambio de estado.

## Perfil de solo lectura aislado separado

Este paquete incluye un perfil activado que contiene solo investigación profunda, sistema
inventario, estado del sistema y estado del sistema. Ejecútelo desde el espacio de trabajo de destino:```bash
/home/tipexxx/Escritorio/Proyecto/codex-agent-system/scripts/run-readonly.sh
```Este iniciador es un perfil de diagnóstico deliberadamente separado, no el TUI
política de ejecución. Fija `CODEX_HOME`, análisis de configuración estricto, un
sandbox de solo lectura y aprobaciones bajo solicitud. No otorga privilegios ni
instalar habilidades de mutación. La ruta de ejecución de TUI utiliza en su lugar una verificación previa escrita
seguido de giros explícitos `dangerFullAccess`/`untrusted`.

## Parada de emergencia

Interrumpir la ejecución activa, negar aprobaciones adicionales, desactivar la habilidad implicada
o servidor MCP, preservar registros, capturar evidencia de solo lectura y recuperar a través de un
canal de confianza independiente. No permitir que el agente afectado borre sus registros o
declararse reparado.

## Perfil de desarrollo de plataforma

El plano de control orientado a la producción vive en
`plugins/jarvis-system-admin/`. Validarlo con el validador de paquetes antes
instalándolo. El servidor MCP del complemento expone únicamente operaciones de auditoría y políticas;
no expone ningún shell ni herramienta de administración de host.

Utilice `codex/jarvis.config.example.toml` como fuente de fusión revisada, no como fuente ciega
reemplazo. Para implementaciones administradas, adapte `codex/requirements.example.toml`
y fije la identidad del comando MCP del complemento. Revise los enlaces del complemento a través de `/hooks` y
confíe en el hash exacto sólo después de la inspección.

No avanzar una capacidad más allá de su etapa de madurez en
`docs/capability-maturity.md`. El inventario en vivo y la administración están en implementación
actividades que no forman parte de la construcción o validación de la plataforma.

La estructura de VM-lab no autoriza la inscripción ni la preparación de la estación de trabajo.
comprobaciones, instalación de virtualización, adquisición de imágenes, creación de invitados o
ejecución del escenario. Cada uno es un punto de control explícito posterior. Validación de accesorios
prueba únicamente los contratos del proyecto.
El registro del controlador es un espacio de nombres y un contrato estatal, no un instalado
servicio. La propuesta de inscripción no es un consentimiento del usuario y no debe interpretarse.
como permiso para observar la estación de trabajo.
El simulador Tier-0 original todavía lee únicamente accesorios sintéticos registrados;
sus datos candidatos no describen la estación de trabajo. Un fijo separado
El adaptador `lighting-tier0-readonly` está habilitado en H1 para el Fedora registrado
estación de trabajo. Obtenga una vista previa antes de usarlo, ejecútelo una vez sin privilegios y mantenga su
salida en `runtime/state/snapshots/`. Sólo podrá leer sus datos registrados.
campos sysfs/proc y no debe leer el estado del conector, iniciar un cliente GPU, llamar
D-Bus o la red, inspeccionar registros protegidos o realizar cualquier escritura. La máquina virtual completa
el anteproyecto y el plan de preparación L2 siguen siendo contratos estáticos; tampoco lo es el permiso
para consultar paquetes, servicios, KVM, libvirt, firmware, recursos o almacenamiento.

El adaptador separado `lighting-tier1-platform-readonly` también es elegible bajo
H1 después de su vista previa y validación del paquete. Está limitado a DMI no secreto.
campos de modelo, nombres de plataformas/módulos/dispositivos permitidos, retroiluminación pasiva
topología, nombres de LED candidatos e identidad de entrada candidata. Serie/UUID
campos, eventos sin procesar, activación de servicio/D-Bus, registros, subprocesos, red,
El estado del conector y las escrituras permanecen prohibidas. Una plataforma de nivel 1 exitosa
ejecutar no es un permiso para el escritorio/sesión posterior o las capas interactivas.

El discriminador `lighting-tier2-wmi-binding-readonly` puede usarse sólo después de
El nivel 1 establece que el módulo de retroiluminación NVIDIA WMI EC es relevante. eso
lee los nombres de instancia GUID de brillo fijo, los nombres de enlace, el de solo lectura
parámetro del módulo `force` y nombres/tipos de proveedores. Nunca debe evaluar un
método WMI, vincular/desvincular un dispositivo, escribir un parámetro o ampliar a arbitrario
Inspección del espacio de nombres WMI.

El observador `lighting-tier3-connector-association-readonly` requiere un
puerta explícita porque la lectura del estado del conector eDP interno puede activar la pantalla
hardware. Se limita a la identidad de la tarjeta DRM, al estado interno del eDP y a los datos fijos.
Asociación de enlace simbólico de retroiluminación a PCI. No puede escribir sysfs, llamar a WMI/ACPI,
leer eventos de entrada o registros, llamar a D-Bus, iniciar clientes GPU o acceder a
red. La aprobación actual es de un solo uso para la investigación de iluminación.La política de host directo convierte a la estación de trabajo inscrita en la implementación principal.
objetivo. La autoridad de solo lectura limitada H1 está activa; el juego R2 específico de la máquina
ha sido capturado, verificado externamente, completamente restaurado a un objetivo aislado,
comparado de forma independiente y retenido como de solo lectura. Esto no activa general
ejecución del host. Cada mutación todavía requiere una recuperación de acción específica,
revisión independiente y aprobación exacta del comando. Una máquina virtual sigue siendo opcional para
Ensayo representativo solo de software y nunca sustituto del host físico.
evidencia.
