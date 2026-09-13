# Ciclo de vida de los datos

## Clases

- Referencia pública
- Operativo interno
- Metadatos del sistema restringidos: cifrados y desbloqueados por el usuario únicamente
- Secreto: cifrado y desbloqueado por el usuario solo cuando se realiza un procedimiento estrictamente aprobado
  realmente requiere perseverancia; de lo contrario nunca se almacena
- Incidente/retención legal

## Ciclo de vida

`recopilar lista de permitidos -> redactar -> validar -> clasificar -> almacenar -> hash -> replicar
cuando está configurado -> retener -> rotar -> destruir según la política exacta aprobada`

Utilice escrituras atómicas para el estado actual y rutas de instantáneas inmutables por convención.
Versiones de esquema y recopilador de registros. El estado caduca por capacidad; los datos obsoletos pueden
informar el historial pero no puede autorizar un cambio en vivo. Preservar la aprobación y la auditoría
registros más largos que los resultados de diagnóstico desechables. La rotación debe agregar un evento y
manifiesto; no debe romper silenciosamente la cadena de hash.

No recopile entornos completos, historiales de comandos, perfiles de navegador ni credenciales.
almacenes, claves privadas, tokens de autenticación o datos `/proc` sin restricciones.

Los eventos de auditoría de mutación del sistema de archivos TUI almacenan enlaces y objetivos categorizados
resúmenes, nunca texto de ruta/nombre, contenido de archivo, nombres de papelera o resultados renderizados.
Los eventos de paquete almacenan operación/recuento/estado y resúmenes vinculantes, nunca el DNF
vista previa del cuerpo o de los nombres de los paquetes. Las aprobaciones de un solo uso en memoria caducan con el
proceso y no son autorizaciones duraderas. Los registros de recuperación de Root-helper son
estado operativo protegido específico del propietario y puede autorizar sólo un
Deshacer aprobado después de la verificación del estado actual.

Hasta que se configure el cifrado, rechace las escrituras restringidas/secretas. crudo desinfectado
la retención de resultados depende del tamaño y del valor diagnóstico: prefiera un período corto,
luego conserve el hash de contenido, el extracto revisado relevante y la lección o enlace vinculado.
error. La replicación remota es solo una interfaz hasta que se apruebe un solo anexo.
El fregadero existe.
