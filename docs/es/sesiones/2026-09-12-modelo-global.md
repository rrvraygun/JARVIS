# Selector global de modelo

Se agregó un selector `Global model` a la vista Agentes. Se sienta deliberadamente
Fuera del editor especializado: todos los especialistas comparten el modelo seleccionado.
Las opciones son los modelos Codex compatibles gpt-6-astra, gpt-5.6-sol, gpt-5.6-terra,
gpt-5.6-luna y gpt-5.5. Los valores están incluidos en la lista permitida y se conservan según el candidato.
runtime/jarvis-model.json y se aplicó a `thread/start` para nuevos turnos. existente
Los turnos mantienen su modelo.

El controlador de sesión valida el valor y recurre a gpt-5.6-terra si
el archivo de configuración está ausente o no es válido. No se incluyen credenciales ni datos de cuenta.
escrito. Ruff, verificación de manifiesto de liberación, verificación de documentación y
las 37 pruebas de sesión/servidor de aplicaciones pasaron después de la integración.
