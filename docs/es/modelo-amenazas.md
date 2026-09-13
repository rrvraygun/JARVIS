# Modelo de amenaza

## Activos protegidos

Disponibilidad del sistema, datos de usuario, credenciales, integridad de la configuración, recuperación
capacidad, historial de auditoría, aprobaciones, política de agentes y fuentes de actualización confiables.

## Adversarios y fracasos

- Inyección rápida en páginas web, documentos, registros, metadatos de paquetes, nombres de archivos y MCP
  salida
- Repositorio de paquetes, complemento, habilidad, enlace, servidor MCP o dependencia comprometidos
- Aprobación humana demasiado amplia o obsoleta
- Alucinación del agente, confusión del objetivo, generalización insegura o prematura.
  finalización
- Escalada de privilegios y comportamiento de diputado confundido
- Agentes concurrentes que cambian recursos superpuestos.
- Ejecución parcial, pérdida de energía, agotamiento del disco, pérdida de red y reversión.
  fracaso
- Atacante local que altera archivos de estado o de auditoría
- El anfitrión comprometido está falsificando su propia evidencia de salud y recuperación.
- Fuga de datos confidenciales a través de indicaciones, transcripciones, registros, instantáneas o
  notificaciones
- Líneas base de VM contaminadas, imágenes doradas grabables, superposiciones obsoletas, falsificadas
  evidencia de invitados, fugas de host compartido, escape de transferencia y afirmaciones falsas que
  El hardware virtual representa la estación de trabajo física.

## Controles

Capacidades registradas, procedimientos versionados, denegación predeterminada, objetivos exactos,
controles de estado reciente, aprobaciones que expiran vinculadas al resumen, revisión independiente,
identidades de herramientas con privilegios mínimos, zona de pruebas, permisos del sistema operativo, listas de permitidos de MCP,
barandillas de gancho, redacción, auditoría en cadena hash, exportación de integridad externa,
Puesta en escena del árbol de trabajo, ensayo desechable, pruebas de recuperación y post-cambio.
validación.
El laboratorio de VM también requiere un bloqueo de imagen oficial firmado, apagado
base dorada de solo lectura, una superposición externa por escenario, redes en tiempo de ejecución
desactivado, sin recursos compartidos de host/credenciales/tiendas de producción/transmisión, invitado externo
certificaciones de identidad y restablecimiento, y registros explícitos de brechas físicas.

Los resultados visibles de lectura local están desinfectados en el terminal, redactados en función del valor de la credencial,
y los nombres de archivos confidenciales se eliminan antes de la sincronización del modelo. el activo
La instantánea de la conversación está delimitada y se inyecta como un historial citado que no es de confianza; eso
no puede otorgar admisión, mutación, privilegio o aprobación al corredor. la corriente
La solicitud permanece escrita por separado y vinculada a políticas. El contexto visible desinfectado se conserva en el almacén de conversaciones delimitado; el contenido bruto sigue excluido de la auditoría. La retención del Codex configurada es un límite de datos independiente.

Los planes de mutación del sistema de archivos vinculan la identidad principal y la de destino, rechazan los enlaces simbólicos,
objetivos ocultos, sensibles, especiales, protegidos, ambiguos o sobrescritos, y
consumir una aprobación en memoria. "Eliminar" se implementa como un mismo sistema de archivos
pasar a la Papelera del usuario actual. Los planes de paquete vinculan nombres exactos, estado previo de RPM y
una vista previa de DNF solo en caché; la instalación rechaza las eliminaciones, la eliminación desactiva la eliminación automática
y rechaza los paquetes resueltos protegidos y el asistente raíz de forma independiente
vuelve a comprobar el enlace antes de un comando fijo. Ninguna ruta acepta shell
sintaxis o aprobación permanente.

## Riesgo residual

Ningún agente puede garantizar un sistema perfecto o plenamente conocido. Las cadenas de hash locales no
derrotar a un atacante privilegiado. Los ganchos no cubren todas las trayectorias de las herramientas. Las pruebas no pueden
representan cada combinación de hardware y falla. Las aprobaciones humanas pueden estar equivocadas.
Las implementaciones de alta seguridad requieren copias de seguridad independientes, registros firmados remotamente,
credenciales de recuperación separadas y revisión periódica humana y de seguridad.
