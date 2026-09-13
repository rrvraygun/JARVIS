# Registro de decisión de requisitos de Fedora Jarvis

Estado: línea base de diseño aceptada. Los cambios requieren una nueva revisión y explícita
decisión del usuario; no alteran silenciosamente el registro original.

## Autoridad

- Permitir automáticamente comandos de solo lectura limitados, incluidos en la lista de permitidos y sin privilegios.
- Requerir la nueva aprobación del usuario para cada comando de cambio de estado.
- Definir alcances de comando, procedimiento y aprobación de transacciones. Habilitar comando
  alcance solamente; conservar los otros ámbitos como extensiones futuras deshabilitadas.
- Defina una lista segura preautorizada pero manténgala deshabilitada.
- Requerir nueva aprobación para cada comando privilegiado. `sudo`, `su`, `doas` y
  `pkexec` nunca son autónomos.
- Negar permanentemente acciones cuyo objeto o efecto probable sea únicamente perjudicial:
  destruir o falsificar pruebas de auditoría/recuperación, eludir políticas, borrar discos,
  capturar credenciales, instalar persistencia encubierta, ocultar errores,
  falsificar la verificación, ejecutar contenido remoto no confiable, inseguro
  automodificación, destrucción de objetivos no resueltos o sobrescritura de datos de usuario,
  copias de seguridad, políticas, historial de auditoría o contenido desconocido.

## Alcance del sistema

- Inscriba solo una estación de trabajo Fedora.
- Portada de gráficos, herramientas de desarrollo, virtualización, contenedores, audio,
  servidores/bases de datos, copias de seguridad, seguridad, almacenamiento, salud, actualizaciones, instalación,
  remoción, mantenimiento, reparación y análisis de desempeño.
- Excluir la optimización de juegos y la administración de VPN de usuario. Plataforma de red
  Los hechos aún pueden inspeccionarse cuando sea necesario para la corrección o seguridad del sistema.
- Detectar RPM/DNF, Flatpak, rpm-ostree, almacenamiento, cifrado, arranque, instantánea y
  características de virtualización a través de un inventario aprobado de solo lectura.
- Etiquetar los hechos modificados u ocultos por el entorno limitado del Codex como considerados por el observador en lugar de
  en lugar de afirmar que describen al anfitrión.

## Pruebas y documentación

- Prefiere páginas de manual/ayuda locales de la versión instalada, fuentes primarias de Fedora y
  documentación previa coincidente.
- Utilice fuentes comunitarias y seleccionadas solo cuando las fuentes primarias sean insuficientes.
  La evidencia comunitaria requiere la confirmación del usuario antes de influir en una acción.
- Mantener un índice de versión y caché de documentación local fuera de línea completo.
- Primero apoye a Bash. Hombre de portada/ayuda, códigos de salida, entorno, análisis, cotización,
  tuberías, redirección, SELinux, systemd, DNF/RPM, Flatpak, contenedores,
  NetworkManager, firewalld, Btrfs/LVM, registros, kernel, firmware, controladores,
  virtualización, audio, copias de seguridad y recuperación.
- Mantener autorizada la documentación de la versión instalada; indexar información más reciente
  por separado.

## Intentos, errores y lecciones

- No reintentar automáticamente. Permita un solo intento.
- Registrar fallas y resultados inesperados como observaciones.
- Promocionar solo lecciones revisadas respaldadas por una solución funcional y verificada.
- La automatización puede nominar una lección después de repetidos éxitos verificados;
  sólo el usuario puede activarlo.
- Preservar la historia inmutable. Prefieren globalmente una lección activa para los matriculados.
  estación de trabajo sólo mientras los requisitos previos coincidan. Suspenderlo después de un cambio de versión,
  conflicto, efecto inesperado o error de validación.
- Registre los éxitos verificados, el tiempo, las limitaciones de la versión, los efectos secundarios,
  requisitos previos y resultados de validación bajo los mismos controles de promoción.
- Consista en resúmenes de decisiones concisos, nunca en cadenas de pensamiento privadas.

## Datos y privacidad- Combine el estado estructurado de SQLite, las declaraciones revisadas administradas por Git y
  eventos de auditoría JSONL encadenados mediante hash.
- Planificar un receptor de copia de seguridad/integridad remota de solo anexos cifrados. No esta habilitado
  hasta que el usuario proporcione y apruebe un mecanismo de destino y credencial.
- Mantener la producción bruta brevemente según el tamaño y el valor de diagnóstico; retener hashes,
  eventos de auditoría y lecciones confirmadas por más tiempo.
- El cifrado es obligatorio antes de la liberación definitiva. Hasta que haya un almacén cifrado
  configurado y desbloqueado explícitamente, no persiste datos restringidos o secretos.
- Redactar credenciales, tokens, claves, cookies, valores de autorización, nombres de usuario,
  nombres de host, rutas personales, direcciones locales, números de serie e identificadores de máquina.
- Proporcionar historial legible por humanos, exportación y borrado completo aprobado por el usuario.

## Seguridad y verificación

- Requerir reversión para cada mutación en riesgo con una puntuación de 0 o mayor de forma predeterminada.
  El umbral es una política versionada y solo se puede cambiar explícitamente.
- Rechazar la ejecución reversible sin reversión. Si es verdaderamente irreversible, exigir
  una declaración específica y una aprobación elevada en lugar de reclamar una reversión.
- Requerir una revisión independiente para cada mutación.
- Requerir un ensayo o simulación siempre que sea compatible.
- Requerir validación posterior a la acción. En caso de falla, capture los resultados, diagnostique y pregunte
  para su aprobación antes de cualquier recuperación que cambie el estado.
- Preferir transacciones de mantenimiento atómico, aunque requiere aprobación por separado para
  cada comando de cambio de estado bajo la política inicial.

## Evolución de la interfaz

- Interfaz inicial: solicitud Codex en lenguaje natural más informes terminales.
- Inicialmente no hay supervisión desatendida.
- Interfaz futura: TUI dedicada que presenta hechos, pruebas, planes, aprobaciones,
  acciones, verificación, historia, lecciones y recuperación.
- Las interfaces de portabilidad pueden admitir otros sistemas Linux más adelante, pero Fedora
  El comportamiento de la estación de trabajo es el único objetivo inicial de implementación.
- Optimizar la seguridad primero, aumentando la autonomía solo para versiones específicas, versionadas,
  procedimientos verificados repetidamente.

## Aclaración sobre la implementación del host directo

- Trate la estación de trabajo Fedora inscrita como el producto objetivo principal; el
  VM es un entorno de ensayo de software secundario.
- No trate una instantánea del mismo dispositivo, una reversión del historial de paquetes o una recuperación exitosa.
  Prueba de VM como recuperación completa de la estación de trabajo.
- Seleccione el backend de instantánea/copia de seguridad solo después del descubrimiento limitado de solo lectura de
  el sistema de archivos real, subvolumen/LVM, arranque, EFI, cifrado y almacenamiento
  diseño.
- Requerir cobertura de registro R0 para trabajo de solo lectura/proyecto, instantánea local R1
  Cobertura para cambios ordinarios de paquete/configuración, cifrado externo R2.
  copia de seguridad del sistema para cambios de kernel/controlador/arranque/gráficos y R3 fuera de línea
  recuperación completa del dispositivo para cambios de almacenamiento/cifrado/diseño del cargador de arranque. antes
  cada mutación A3, verifique por separado un núcleo que funcione correctamente y el real
  ruta de selección de arranque de recuperación; esta puerta de arranque de acción específica no es una VM
  requisito y no es una afirmación de que R2 proporcione reconstrucción completa.
- Comience el desarrollo en vivo en modo sombra. La mutación supervisada sigue bloqueada
  hasta que se verifiquen el artefacto de recuperación requerido y un ensayo de restauración.

## Revisión de integración de mutaciones TUI aceptada - 2026-08-27

Esta revisión registra la decisión explícita del usuario sobre el producto sin reescribir
la línea de base anterior:- las lecturas exactas deterministas siguen siendo automáticas y sin aprobación;
- cada mutación de paquete o sistema de archivos requiere un nuevo gráfico de un solo uso
  confirmación;
- Los objetivos exactos del sistema de archivos no protegidos y que pueden ser escritos por el usuario actual no están limitados
  a la sucursal del proyecto;
- la eliminación significa un movimiento limitado a la Papelera del usuario actual, nunca permanente
  desvincular;
- La instalación/eliminación de paquetes privilegiados utiliza sólo el Polkit registrado como propietario de root
  auxiliar, una vista previa exacta de DNF solo en caché, estado previo duradero y por separado
  Deshacer aprobado; y
- Los turnos de modelo pueden proponer un trabajo más amplio para los usuarios actuales, pero las subvenciones de admisión escritas
  no hay mutación por sí misma y cada límite de comando/archivo permanece `untrusted`.

## 2026-09-08 — copias de seguridad controladas de recuperación ante desastres

El usuario seleccionó su disco externo existente y aclaró que controlaba
las copias de seguridad del sistema son suficientes para el objetivo principal de recuperación ante desastres; un completo
La imagen sin comprimir no es obligatoria. El candidato actual utiliza el anteriormente
Enfoque Restic cifrado registrado, que conserva los datos existentes del disco externo y
requiriendo evidencia nueva de integridad y restauración. Ver
[specific target observations](sesiones/2026-09-08-destino-copia-externa.md).
Las operaciones de partición/firmware conservan su aprobación y recuperación exactas por separado.
requisitos. Un informe histórico de restauración de archivos no es una prueba de arranque actual.

## Cuestionario de finalización aceptado — 2026-09-09

El usuario respondió las 15 preguntas sobre el alcance. Las decisiones exactas autorizadas se registran en `sessions/2026-09-09-questionnaire-decisions.md`. Amplían los comandos generales revisados, la aplicación de dependencia del proyecto original, las descargas de dependencia aprobadas, las transcripciones de siete días, todas las actualizaciones necesarias, dos operaciones de arranque explícitas, la copia de seguridad completa del sistema/hogar y la instalación en esta estación de trabajo. Estas son decisiones de alcance, no aprobaciones de ejecución de acciones específicas. Todavía faltan pruebas de verificación completa de Restic. La restauración completa del punto de control sigue limitada a una operación recuperable.
