# Operaciones - solicitudes de huéspedes y plazos

El módulo Operaciones es la lista de tareas de recepción para los huéspedes: toallas, un taxi,
un aire acondicionado averiado, una queja. Cada solicitud es una solicitud de servicio con una categoría, una
prioridad y un plazo, la haya creado una persona o un agente de IA. El
**Informe de plazos de atención (SLA)** muestra si las solicitudes se atienden a tiempo. Los usuarios de Recepción y
Administrador del hotel ven este módulo; solo un Administrador del hotel cambia su
configuración.

![La lista Solicitudes de huéspedes: solicitudes abiertas con su prioridad, categoría, insignia de origen, habitación y plazo, una de ellas fuera de plazo](/img/operations/guest-requests.png)

## Antes de empezar

1. **Fije los plazos.** **Configuración → Operaciones → Plazos de solicitudes
   de huéspedes**: cuántos minutos puede seguir abierta una solicitud de cada prioridad.
   Consulte [Configuración](#configuracion).
2. **Conecte WhatsApp** si los huéspedes deben poder escribirle por ahí
   ([configuración de WhatsApp](/whatsapp)). Los mensajes de los huéspedes alojados se
   convierten entonces en solicitudes de servicio automáticamente.

## Registrar una solicitud de huésped

1. Abra **Operaciones → Solicitudes de huéspedes**.
2. Pulse **Nueva solicitud de servicio**.
3. Escriba el **Asunto** ("Extra pillows for 201"), y elija la
   **Categoría**, la **Prioridad** y la **Habitación**. Añada **Detalles** si el personal los
   necesita.
4. Pulse **Crear solicitud de servicio**.

![El formulario Nueva solicitud de servicio: asunto, categoría Limpieza, prioridad Media, habitación 201 y detalles](/img/operations/new-ticket.png)

El plazo empieza ahora: la solicitud vence cuando pasan los minutos fijados para su
prioridad. La lista la muestra como *vence 10-19 22:40* (mes-día, hora).

## Gestionar una solicitud

Cada solicitud abierta tiene dos botones:

- **Iniciar** cuando alguien se ocupa de ella. La solicitud pasa a **En curso**.
- **Resolver** cuando está hecha. La solicitud pasa a **Resuelto** y
  sale de la lista.

![Registrar una solicitud de almohadas adicionales en la habitación 201 e iniciarla](/img/operations/new-ticket.gif)

Una solicitud que ha superado su plazo muestra **vencido** en rojo. Marque **Mostrar
cerrados** para ver también las solicitudes resueltas, cerradas y canceladas; una solicitud
resuelta después de su plazo muestra **SLA incumplido**.

![La lista con Mostrar cerrados marcado: las solicitudes resueltas y cerradas en gris, una marcada como SLA incumplido](/img/operations/show-closed.png)

**Cerrado** y **Cancelado** los fijan los agentes de IA y las integraciones; la
pantalla los muestra, pero no tiene botón para ellos.

### Las solicitudes de mantenimiento van a limpieza

Cuando pulsa **Iniciar** en una solicitud de **Mantenimiento** que tiene habitación,
Kamra añade una tarea de **Mantenimiento** a la cola de limpieza de esa habitación,
con la prioridad de la solicitud y una nota *From ticket TKT-…*. Aparece en
el [Panel de limpieza y la aplicación del teléfono](/es/housekeeping). Si la habitación ya
tiene una tarea de mantenimiento abierta, no se crea una segunda.

## De dónde vienen las solicitudes

La insignia de color que sigue a la categoría muestra quién creó la solicitud.
Las solicitudes creadas en esta pantalla no tienen insignia.

| Origen | Cómo llega |
| --- | --- |
| *(ninguna)* | El personal pulsó **Nueva solicitud de servicio** |
| **Agente de IA** | **Kamra Agent**, el asistente de la aplicación, la creó, o un agente de IA conectado por MCP la registró (la herramienta `create_ticket`) |
| **Voz** | Un agente de voz en la línea telefónica del hotel la registró |
| **WhatsApp** | La creó un mensaje de WhatsApp de un huésped (ver abajo), o una integración registró una solicitud de WhatsApp |
| **QR** | Una integración registró una solicitud desde un código QR |

**Mensajes de WhatsApp de huéspedes alojados.** Cuando un huésped con la entrada
registrada, o con una reserva confirmada, escribe a su número de WhatsApp, Kamra añade una solicitud
automáticamente: asunto *WhatsApp: …* con el inicio del mensaje, categoría
**Recepción**, prioridad **Media**, la insignia **WhatsApp**, vinculada a
la reserva. La
conversación completa está en **Operaciones → WhatsApp** (consulte
[WhatsApp](/whatsapp)).

## Categorías

La categoría indica qué equipo atiende la solicitud: **Limpieza**,
**Servicio a la habitación**, **Mantenimiento**, **Recepción**, **Conserjería**,
**Queja** u **Otro**. El informe de SLA desglosa sus cifras por
categoría, así que elija la que corresponde al equipo que hará el trabajo.

## Consultar el informe de SLA

**Informes → Informe de SLA** responde a una pregunta: ¿se resuelven las solicitudes de los huéspedes
dentro de su plazo?

1. Elija las fechas arriba a la derecha. Por defecto son los últimos 30 días.
   Las solicitudes cuentan por el día en que se crearon.
2. Lea las cuatro cifras: **Solicitudes**, **Resuelto**, **Porcentaje de incumplimiento** y
   **Tiempo medio de resolución** (tiempo desde la creación hasta la resolución). **Resuelto** cuenta
   las solicitudes **Resuelto** y **Cerrado**.
3. **Por categoría** y **Por prioridad** muestran las mismas cifras por equipo y
   por prioridad.
4. **Fuera de plazo ahora** muestra las solicitudes abiertas que han superado su plazo y por cuántas
   horas.

![El informe de SLA de Operaciones: 10 solicitudes, 4 resueltas, 20% de incumplimiento, 19 min de media, tablas por categoría y prioridad, y una solicitud fuera de plazo ahora](/img/operations/sla-report.png)

Una solicitud cuenta como incumplida si se resolvió después de su plazo, o si
sigue abierta después de él. El porcentaje de incumplimiento se pone ámbar al 10% y rojo al 25%. Una
solicitud cerrada sin haberse resuelto antes cuenta como resuelta, pero no suma
tiempo al **Tiempo medio de resolución**.

## Instrucciones de estancia

Cuando se crea una reserva, Kamra convierte lo que pidió el huésped en
instrucciones para el equipo que lo hace:

| De la reserva | Va a |
| --- | --- |
| Solicitudes especiales | Recepción |
| Recogida en el aeropuerto o la estación (con el número de vuelo o de tren) | Transporte |
| Traslado al aeropuerto o la estación | Transporte |
| Estacionamiento con servicio de aparcacoches | Conserjería |
| Entrada anticipada o salida tardía solicitada | Recepción |

Cada instrucción es para un equipo y está **Abierta** hasta que alguien la marca
como **Hecho**. Las encontrará en la tarjeta **Instrucciones** de la reserva
(pulse la reserva en **Reservas**).

1. Para añadir una, elija el equipo en la lista (**Limpieza**, **Recepción**,
   **Alimentos y bebidas**, **Conserjería**, **Transporte**, **Mantenimiento** o
   **Seguridad**), escriba la instrucción ("Fruit basket before arrival")
   y pulse **Agregar**.
2. Cuando esté hecha, pulse **Hecho** en su línea. La línea aparece tachada
   y muestra quién la hizo y cuándo. **Reabrir** la devuelve a
   **Abierta**.

![La tarjeta Instrucciones de una reserva: una cesta de fruta para limpieza aún abierta, una recogida en el aeropuerto hecha y el cuadro para añadir otra](/img/operations/stay-instructions.png)

El encabezado de la tarjeta cuenta las instrucciones abiertas. No puede añadir
instrucciones a una estancia cancelada, con la salida registrada o no presentada.
Recepción las añade; Recepción y Limpieza pueden marcarlas como hechas.
Cada cambio queda en el registro de actividad. Para todo lo que necesite un plazo
y seguimiento, registre también una solicitud de huésped. El personal de limpieza ve las
solicitudes especiales de una reserva en sus tarjetas de tarea en la
[aplicación del teléfono](/es/housekeeping).

## Configuración

**Configuración → Operaciones** (Administrador del hotel). **Módulo activado** oculta o muestra
todo el módulo.

![Configuración → Operaciones: plazos de solicitudes de huéspedes para Urgente, Alta, Media y Baja](/img/operations/settings.png)

| Ajuste | Dónde | Valor por defecto | Qué hace |
| --- | --- | --- | --- |
| **Urgente** | Plazos de solicitudes de huéspedes | 15 min | Minutos hasta que una solicitud Urgente queda fuera de plazo |
| **Alta** | Plazos de solicitudes de huéspedes | 30 min | Minutos hasta que una solicitud Alta queda fuera de plazo |
| **Media** | Plazos de solicitudes de huéspedes | 60 min | Minutos hasta que una solicitud Media queda fuera de plazo |
| **Baja** | Plazos de solicitudes de huéspedes | 240 min | Minutos hasta que una solicitud Baja queda fuera de plazo |

Los plazos de las tareas de limpieza son aparte: **Configuración → Limpieza**
([Limpieza](/es/housekeeping#configuracion)).

## Conviene saber

- El plazo se fija cuando se crea la solicitud. Cambiar los
  minutos en Configuración solo afecta a las solicitudes nuevas.
- Las solicitudes fuera de plazo se marcan en la lista y en el informe. Kamra
  no envía avisos por solicitudes de huéspedes atrasadas; el escalado por WhatsApp es
  solo para las tareas de limpieza.
- La lista muestra las 200 solicitudes más recientes.
- El personal de limpieza no ve Solicitudes de huéspedes. Las solicitudes para ellos llegan a la
  aplicación del teléfono como tareas de limpieza solo mediante solicitudes de mantenimiento (ver arriba)
  o una tarea que crea recepción.
- La lista se actualiza cuando otra persona cambia una solicitud mientras las actualizaciones en directo
  están activadas; si no, vuelva a cargar la página.

## Solución de problemas

**Los mensajes de WhatsApp no se convierten en solicitudes.** Solo crean una solicitud
los mensajes de un número que coincide con un huésped con una reserva confirmada o con la
entrada registrada. Compruebe que el número de teléfono del perfil del huésped es el
desde el que escribe, con el prefijo del país (por ejemplo `+91…`).

**Una solicitud no aparece como fuera de plazo.** Solo queda fuera de plazo cuando han pasado los minutos de su
prioridad desde que se creó. Revise **Configuración →
Operaciones**.

**No apareció ninguna tarea de mantenimiento.** La solicitud necesita la categoría **Mantenimiento**
y una habitación, y alguien debe pulsar **Iniciar**. Resolverla
directamente no crea ninguna tarea.

## Para desarrolladores

Las solicitudes funcionan con `kamra.api.create_ticket`, `tickets_list` y
`advance_ticket`; el informe es `kamra.reports.sla_report`. Las instrucciones
de estancia usan `kamra.api.stay_instructions`, `add_stay_instruction`
y `set_stay_instruction_status`. Los agentes de IA usan
las mismas llamadas que las herramientas MCP `create_ticket`, `list_tickets` y
`advance_ticket`; consulte las [MCP tools](/mcp-tools#ops) y la
[referencia de la API](/api-reference).
