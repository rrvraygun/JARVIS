# Regresión de clic de punto de control

Se rastreó el informe de que se registró un clic en el punto de control pero no mostró opciones
para duplicar el manejo de eventos. ConversationCheckpointControl y JarvisTui ambos
manejó el mismo evento de botón; dependiendo de la propagación textual, un controlador
podía abrir el menú y el otro cerrarlo nuevamente.

El controlador infantil ahora es la única ruta y llama a `_toggle_checkpoint`
sincrónicamente, por lo que el estado del menú cambia en el mismo evento de clic. el botón
sigue siendo el primer hijo; OptionList es el segundo hijo y está posicionado
debajo de él. El mando mantiene una altura fija mientras está abierto; su menú tiene un fijo
altura de cuatro líneas y no cambia el ancho de la conversación. Un segundo clic cierra
eso. La aplicación ya no tiene un controlador de puntos de control competidor.

La regresión gráfica verifica las dimensiones de los botones, los archivos adjuntos del menú y
visibilidad, ubicación del menú debajo del botón y cierre al segundo clic. el
pases de prueba enfocados. No se cambiaron archivos del sistema, asistentes raíz ni credenciales.
