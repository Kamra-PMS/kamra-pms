# Limpieza: habitaciones, limpiezas y lavandería

El módulo de Limpieza mantiene al día el estado de cada habitación y
organiza las limpiezas en el orden correcto. Los supervisores y la
recepción siguen el **Panel de habitaciones**; el personal de limpieza
trabaja desde la **aplicación móvil**, donde toma habitaciones, las marca
como terminadas, registra cargos de minibar y anota objetos perdidos. La
lavandería de huéspedes funciona desde el mismo módulo.

![El Panel de habitaciones: cada habitación por piso, con un color según su estado, el huésped alojado y la tarea abierta con su responsable](/img/housekeeping/room-board.png)

## Antes de empezar

1. **Asigne a cada empleado el rol correcto.** En **Configuración → Personal y acceso**:
   - **Limpieza** para el personal de limpieza. Tiene acceso a la
     aplicación móvil, la lista de tareas, la lavandería y los objetos
     perdidos, y puede marcar habitaciones como **Limpia** o **Sucia**.
   - **Supervisor de limpieza** para los supervisores. Incluye todo lo
     que puede hacer Limpieza, más el **Panel de habitaciones**, el
     permiso para marcar habitaciones como **Inspeccionada**, **Listo** o
     **Fuera de servicio**, aprobar inspecciones y asignar tareas, y
     **Configuración → Limpieza**.
   - Los roles **Recepción** y **Administrador del hotel** también pueden
     usar el Panel de habitaciones y poner cualquier estado.
2. **Defina los plazos de las tareas** en **Configuración → Limpieza →
   Plazos de las tareas** (consulte [Configuración](#configuracion)).
   Kamra los usa para marcar las limpiezas atrasadas y escalarlas.
3. **Ponga un número de móvil en el usuario de cada gerente** si quiere
   recibir los avisos de escalado por WhatsApp. Los avisos se envían por
   la conexión de WhatsApp del alojamiento
   ([configuración de WhatsApp](/whatsapp)).
4. **Complete la hoja de tarifas de lavandería** si ofrece lavandería a
   huéspedes: **Limpieza → Lavandería → Tarifario** (consulte
   [Configurar el tarifario de lavandería](#configurar-el-tarifario-de-lavanderia)).

## De dónde vienen las tareas de limpieza

- **Salida.** Cuando la recepción registra la salida de un huésped, Kamra
  marca la habitación como **Sucia** y crea una tarea de **Limpieza por
  salida** con prioridad **Alta**. Una habitación **Fuera de servicio**
  no recibe tarea.
- **Incidencias de mantenimiento.** Cuando alguien inicia una solicitud
  de huésped de la categoría **Mantenimiento** para una habitación, Kamra
  agrega una tarea de **Mantenimiento** a esa habitación (consulte
  [Operaciones](/es/operations)).
- **Inspecciones.** Con **Inspeccionar después de cada limpieza por
  salida** activado, cada limpieza por salida terminada crea una tarea de
  **Inspección**.
- **A mano.** **Limpieza → Tareas → Nuevo**: elija la habitación, el tipo
  (**Limpieza por salida**, **Limpieza durante la estancia**, **Limpieza
  profunda**, **Inspección**, **Mantenimiento**), la prioridad y una nota
  opcional.

![El formulario de nueva tarea de limpieza con habitación, tipo, prioridad, estado y notas](/img/housekeeping/new-task.png)

Cada tarea recibe un plazo al crearse: los minutos de su prioridad en
**Plazos de las tareas**.

## Revise todas las habitaciones en el Panel de habitaciones

1. Abra **Limpieza → Panel de habitaciones**.
2. Cada recuadro muestra el número de habitación, su estado, el huésped
   alojado y la tarea abierta con su tipo y responsable. Un icono de cama
   indica que la habitación está ocupada; un icono de flecha indica que
   el huésped sale hoy.
3. Use los botones de la parte superior para mostrar solo las
   habitaciones **Sucia**, **Limpia**, **Inspeccionada**, **Listo** o
   **Fuera de servicio**, las de **Salida prevista para hoy** o las que
   están **Con tarea asignada**. Cada botón muestra su número. El botón
   **Listo** solo aparece mientras haya al menos una habitación **Listo**.
4. Use **Todos los pisos** / **Piso 1** … para ver un solo piso.

El panel se actualiza cada 30 segundos. Pulse **Actualizar** para
actualizarlo ahora.

Para ver la historia completa de una habitación (quién se alojó, quién la
limpió y cuándo, incidencias, las próximas semanas) y sus cifras, abra
[Habitaciones](/es/rooms).

## Cambie el estado de una habitación

1. En el Panel de habitaciones, haga clic en la habitación.
2. Elija **Marcar como Limpia**, **Marcar como Sucia**, **Marcar como
   Inspeccionada**, **Marcar como Listo** o **Marcar como Fuera de
   servicio**.

![El menú de una habitación en el Panel de habitaciones con las opciones Marcar y, debajo, la lista para asignar la tarea de la habitación a un miembro del personal de limpieza](/img/housekeeping/room-board-menu.png)

**Listo** significa que la habitación pasó su inspección, en los hoteles
que inspeccionan cada limpieza por salida (consulte
[Configuración](#configuracion)). El personal de limpieza solo ve
**Marcar como Limpia** y **Marcar como Sucia**. Aprobar una habitación
(**Inspeccionada** o **Listo**) o ponerla **Fuera de servicio**
corresponde a un supervisor, a la recepción o a un Administrador del
hotel. Kamra también lo comprueba en el servidor y registra cada cambio.

## Trabaje desde la aplicación móvil

La aplicación móvil está pensada para usarse con una mano, junto al carro
de limpieza. Abra **Limpieza → Aplicación móvil**, o vaya a `/kamra/hk`
en su dirección de Kamra, e inicie sesión. Agréguela a la pantalla de
inicio del teléfono para que el personal la abra como una aplicación.

![La pestaña Mis tareas de la aplicación móvil: la habitación 203 asignada y pendiente de aceptar, la habitación 104 lista para empezar](/img/housekeeping/hk-my-tasks.png)

La aplicación tiene cuatro pestañas en la parte inferior:

| Pestaña | Qué muestra |
| --- | --- |
| **Mis tareas** | Tareas asignadas a usted o tomadas por usted |
| **Disponibles** | Tareas que nadie ha tomado todavía |
| **Habitaciones** | Todas las habitaciones y su estado; toque una habitación ocupada para registrar un cargo |
| **Lavandería** | Solicitudes de recogida y bolsas en curso (igual que el tablero de lavandería de la recepción) |

Las tareas se ordenan para que la habitación correcta salga primero:
habitaciones con un huésped que llega hoy, luego limpiezas por salida,
luego por prioridad (**Urgente**, **Alta**, **Media**, **Baja**) y luego
de la más antigua a la más reciente. Cada tarjeta muestra:

- una estrella si el huésped es VIP,
- **llegada hoy** (con la hora de llegada del huésped si la reserva la
  tiene),
- las peticiones del huésped en la reserva y la nota de la tarea, si hay,
- **vencido** cuando la tarea supera su plazo.

### Tome una habitación de las disponibles

1. Abra **Disponibles**.
2. Toque **Asignarme esta habitación** en una tarjeta. La tarea pasa a
   **Mis tareas**.

![La pestaña Disponibles con tres habitaciones sin asignar, una de ellas una limpieza durante la estancia de un huésped VIP que está vencida](/img/housekeeping/hk-available.png)

Si otra persona tomó la habitación un momento antes, Kamra rechaza el
segundo toque, muestra *Ya la tomó …* en la parte superior y la tarjeta
sale de **Disponibles**.

### Acepte o rechace una habitación asignada

Una tarea asignada a usted muestra **asignado a usted** con **Aceptar** y
**Rechazar**.

- Toque **Aceptar** para quedársela.
- Toque **Rechazar**, escriba un motivo si quiere (es opcional) y toque
  **Enviar de vuelta**. La tarea vuelve a **Disponibles** y el motivo
  queda guardado en la tarea. **Mantener** cancela.

### Limpie una habitación

1. En **Mis tareas**, toque **Iniciar** al empezar. La tarjeta muestra
   **En curso…**.
2. Para dejar constancia de la limpieza, toque **Añadir foto/vídeo** y
   haga una foto o elija una. Agregue todas las que necesite; toque la
   **×** roja de una miniatura para quitarla.
3. Toque **Hecho ✓**.

![Un miembro del personal de limpieza toma la habitación 105 de Disponibles, la inicia, la marca como hecha y la habitación aparece como Limpia](/img/housekeeping/hk-take-and-finish.gif)

Al terminar una limpieza, la habitación pasa a **Limpia** en todas las
pantallas. Si la limpieza termina después de su plazo, la tarea queda
marcada como plazo incumplido. Si un huésped llega hoy a esa habitación,
la recepción recibe un mensaje de WhatsApp avisando de que la habitación
está lista.

### Apruebe una inspección

Una tarjeta de **Inspección** tiene **Aprobar inspección ✓** en lugar de
**Hecho ✓**. Solo un supervisor (Supervisor de limpieza, Recepción o
Administrador del hotel) puede tocarlo; el personal de limpieza ve el
botón desactivado como **El supervisor aprueba la inspección**. Aprobar
la inspección marca la habitación como **Listo** cuando **Inspeccionar
después de cada limpieza por salida** está activado, y como
**Inspeccionada** en caso contrario. Nunca devuelve la habitación a
**Limpia**.

![Una tarjeta de inspección de la habitación 106 en la aplicación móvil con el botón Aprobar inspección](/img/housekeeping/hk-inspection.png)

Si el servidor rechaza un toque, la aplicación indica el motivo en la
parte superior de la pantalla, por ejemplo *Ya la tomó …* cuando otra
persona tomó la habitación antes.

La recepción ve las fotos de la última limpieza de la habitación en
**Hoy** (el botón de cámara de la habitación) y en la tarea, en
**Limpieza → Tareas**.

## Asigne una habitación a un miembro del personal de limpieza

El personal toma habitaciones de **Disponibles** por su cuenta. Un
supervisor también puede entregar la tarea abierta de una habitación a
una persona concreta:

1. En el Panel de habitaciones, haga clic en la habitación.
2. En **Asignar *tarea* a** (por ejemplo **Asignar Limpieza por salida
   a**), elija a la persona en **Seleccione a un miembro del personal de
   limpieza…**.

La tarea aparece entonces en **Mis tareas** de esa persona como
**asignado a usted** hasta que la acepte o la rechace. La lista solo
incluye usuarios activos con el rol **Limpieza** o **Supervisor de
limpieza** que trabajan en este alojamiento. Kamra rechaza la asignación
si usted no es supervisor (Supervisor de limpieza, Recepción o
Administrador del hotel), si la persona no es personal de limpieza de
este alojamiento o si la tarea ya está **Hecho** o **Verificado**. Los
agentes de IA conectados por MCP usan la herramienta `hk_assign_task`,
con las mismas reglas.

## Vea todas las tareas

**Limpieza → Tareas** muestra todas las tareas, de la más reciente a la
más antigua, con su habitación, tipo, prioridad y estado. Haga clic en
una tarea para cambiarla o ver sus fotos.

![La lista de tareas de limpieza: cinco limpiezas pendientes y una hecha](/img/housekeeping/tasks.png)

El estado de una tarea pasa de **Pendiente → En curso → Hecho**.
**Verificado** es para una inspección: poner una tarea en **Verificado**
marca la habitación como **Inspeccionada** (o **Listo** cuando
**Inspeccionar después de cada limpieza por salida** está activado).
Desde la aplicación móvil, **Hecho** en una inspección cuenta como
**Verificado**, y solo un supervisor puede verificar. Poner una
inspección en **Hecho** aquí cierra la tarea sin cambiar la habitación.
Use el filtro **Estado** para ver un solo estado.

## Tareas atrasadas y escalado

Cada 15 minutos, Kamra busca tareas abiertas que superan su plazo:

1. En cuanto una tarea vence, se marca como plazo incumplido y todos los
   usuarios con el rol **Recepción** reciben un mensaje de WhatsApp:
   *habitación, tarea, prioridad, minutos de retraso*, que termina con
   *escalado a la recepción*.
2. Si sigue abierta después de otro plazo completo (por ejemplo, una
   limpieza **Alta** que sigue abierta 45 minutos después de vencer),
   todos los usuarios con el rol **Administrador del hotel** reciben un
   segundo mensaje, que termina con *escalado al administrador del
   hotel*.

Los mensajes van al número de móvil del registro de cada usuario, por la
conexión de WhatsApp del alojamiento. Sin un número de WhatsApp
conectado, el escalado solo se anota en el registro de actividad.

## Registre cargos de minibar y lavandería desde la habitación

1. En la aplicación móvil, abra **Habitaciones**.
2. Toque una habitación ocupada (las que tienen icono de cama).
3. Elija **Minibar** o **Lavandería**, escriba lo consumido ("2 colas, 1
   agua") y el importe.
4. Toque **Registrar**.

![Registro de un cargo de minibar de 240 en la habitación 101 desde la aplicación móvil](/img/housekeeping/hk-post-charge.png)

El cargo va al folio del huésped alojado. Limpieza solo puede registrar
**Minibar** o **Lavandería**, el importe debe ser mayor que cero y la
habitación debe tener un huésped con entrada registrada. Kamra calcula el
impuesto de la línea, no el personal de limpieza: la lavandería al tipo
de servicios de su país y el minibar a su tipo de alimentos y bebidas
(consulte [Country setup](/country-setup)). Para bolsas de lavandería
contadas, use el tablero de lavandería (más abajo): calcula el precio con
la hoja de tarifas.

## Gestione la lavandería de huéspedes

**Limpieza → Lavandería** (también en **Finanzas → Lavandería**) es el
tablero de lavandería. **Solicitudes de recogida** son las que esperan
recogida, **En custodia** son las bolsas que están en la
lavandería y **Reciente** son las últimas bolsas entregadas o canceladas.

![El tablero de lavandería: una solicitud de recogida de la habitación 101 y dos bolsas en curso, una lista y otra en proceso](/img/housekeeping/laundry-board.png)

1. **Registre la solicitud.** Pulse **Registrar solicitud de recogida**,
   elija la habitación, pulse **Servicio estándar** para cambiarlo a
   exprés si el huésped lo quiere, agregue una nota ("bolsa en la puerta
   después de las 15:00") y pulse **Agregar a la cola de recogida**. Los
   huéspedes también pueden pedir una recogida desde su página de
   registro de entrada en línea, una vez registrados.
2. **Recoja y cuente.** En la puerta, pulse **Recoger y contar prendas**
   en la solicitud. Use **+** y **−** en cada prenda y servicio, junto
   con el huésped. Los precios salen del tarifario; no puede escribir un
   precio. Pulse **Recoger … prendas**. Para llevarse una bolsa sin
   solicitud previa, pulse **Recoger ahora**.
3. **Envíela.** Pulse **Enviar a lavandería**, y **Marcar listo** cuando
   vuelva.
4. **Devuelva y entregue.** Pulse **Recibir y entregar prendas**, cuente
   cada prenda de vuelta (o pulse **Todo volvió**) y pulse **Entregar y
   facturar**.

![Recuento de una bolsa con el huésped: se agregan una americana, un vestido y unos vaqueros, y luego se recoge](/img/housekeeping/laundry-collect.gif)

![Devolución de una bolsa a la habitación 102 con un sari de menos y una nota que explica el motivo](/img/housekeeping/laundry-return.png)

Al entregar la bolsa, Kamra registra la cuenta de lavandería en el folio
del huésped. Si falta una prenda, debe escribir el motivo en el cuadro de
faltantes antes de entregar; la nota queda en el pedido.

Cada bolsa recibe una hora de **Entrega prevista para**: hoy a las 20:00
para exprés y mañana a las 20:00 para estándar. Una bolsa que supera esa
hora muestra **vencido**. **Comprobante de lavandería** imprime un recibo
de la bolsa en la impresora térmica.

**Lavandería del hotel y bolsas sin cargo.** En **Recoger ahora**, elija
**Uso interno (uniformes / ropa de cama)** para artículos del hotel, o
marque **De cortesía: no cobrar al huésped**. Kamra cuenta estas bolsas
pero nunca las factura.

**Cancelar** una bolsa que no se va a hacer. Debe indicar un motivo; se
guarda en el pedido.

La pestaña **Facturación** muestra los ingresos de lavandería de los
últimos días: pedidos facturados, prendas, ingresos por servicio y
cuántas bolsas fueron de uso interno o de cortesía.

## Configurar el tarifario de lavandería

1. Abra **Limpieza → Lavandería → Tarifario**.
2. Pulse **Agregar tarifa**. Introduzca la prenda (Camisa, Sari…), el
   servicio (**Lavado y planchado**, **Limpieza en seco** o **Solo
   planchado**), la tarifa y, si quiere, la tarifa exprés.
3. Pulse **Guardar**.

![La hoja de tarifas de lavandería con prendas, servicios, tarifas y tarifas exprés](/img/housekeeping/laundry-price-menu.png)

Si la tarifa exprés queda en blanco, se usa el multiplicador **Tarifa
exprés** de **Configuración → Limpieza** (1,5 × la tarifa de forma
predeterminada). La misma hoja está en **Configuración → Limpieza → Hoja
de tarifas de lavandería**, con **Importar CSV** y **Exportar CSV** para
cargar una lista completa. Recepción, Finanzas y Administrador del hotel
pueden cambiar las tarifas; el personal de limpieza solo puede verlas.

## Registre objetos encontrados, faltantes y dañados

Desde el teléfono:

1. Toque el icono de caja en la parte superior de la aplicación móvil.
2. Elija **Encontrado**, **Falta** o **Dañado**.
3. Escriba qué es, elija la habitación si la conoce y toque
   **Registrar**.

![Registro de una sudadera gris encontrada en la habitación 204 desde la aplicación móvil](/img/housekeeping/hk-log-item.png)

El objeto aparece en **Limpieza → Objetos perdidos y encontrados** como
**En custodia**, con la fecha de hoy y su nombre. La recepción también
puede agregar objetos allí con **Nuevo**.

![El registro de objetos perdidos y encontrados con cuatro objetos en custodia](/img/housekeeping/lost-found.png)

Cuando el huésped recoge el objeto, ábralo y ponga **Estado** en
**Devuelto**, el **Huésped** y la **Fecha de devolución**. Use
**Desechado** para objetos que tira o dona. Filtre la lista por **Tipo**
y **Estado**.

## Entregue un turno

**Finanzas → Entrega de turno** guarda un registro por turno (**Mañana**,
**Tarde**, **Noche**): efectivo inicial, efectivo cobrado, pagos,
efectivo final, a quién entregó el turno y notas para el siguiente turno.
Pulse **Nuevo**, complételo y ponga **Estado** en **Cerrado** cuando el
siguiente turno haya tomado el relevo.

![La lista de entregas de turno con tres turnos y su efectivo final](/img/housekeeping/shift-handover.png)

Es un registro simple: Kamra no calcula las cifras de efectivo. Para el
arqueo de caja con diferencias, use **Mi caja** e **Informe de turno**
del cajero (consulte [Facturación](/es/billing)).

## Configuración

**Configuración → Limpieza** (Administrador del hotel o Supervisor de
limpieza). **Módulo activado** oculta o muestra todo el módulo.

![Configuración → Limpieza: plazos de las tareas, preparación de habitaciones y el multiplicador exprés de lavandería](/img/housekeeping/settings.png)

| Ajuste | Dónde | Valor predeterminado | Qué hace |
| --- | --- | --- | --- |
| **Urgente** / **Alta** / **Media** / **Baja** | Plazos de las tareas | 20 / 45 / 90 / 180 min | Minutos desde la creación hasta que una tarea de esa prioridad vence y se escala |
| **Inspeccionar después de cada limpieza por salida** | Preparación de habitaciones | Desactivado | Al terminar una limpieza por salida, crea una tarea de **Inspección** con prioridad **Alta**; aprobarla marca la habitación como **Listo** |
| **Plazo de inspección** | Preparación de habitaciones | 30 min | El plazo de esa tarea de inspección |
| **Tarifa exprés** | Lavandería | 1,5 × normal | Precio exprés para las líneas de la hoja de tarifas sin tarifa exprés |

## Conviene saber

- El plazo de una tarea se fija al crearla. Cambiar un plazo en
  Configuración solo afecta a las tareas nuevas.
- **Hecho** en una limpieza pone la habitación en **Limpia**. Una
  inspección nunca devuelve una habitación a **Limpia**: aprobarla marca
  la habitación como **Inspeccionada**, o **Listo** cuando las
  inspecciones están activadas.
- Las fotos y vídeos de una tarea pueden ocupar hasta 25 MB cada uno.
- La aplicación móvil y el Panel de habitaciones se actualizan solos
  cada 20 y 30 segundos; toque **Actualizar** después de un cambio hecho
  en otro dispositivo.
- Una solicitud de recogida de lavandería necesita un huésped con entrada
  registrada en la habitación. Un huésped no puede pedir una segunda
  recogida mientras otra sigue en espera.

## Solución de problemas

**"Solo un supervisor de limpieza puede poner una habitación en
Inspeccionada."** (o **Listo**, o **Fuera de servicio**) El usuario solo
tiene el rol Limpieza. Asígnele **Supervisor de limpieza**, o pida a un
supervisor o a la recepción que apruebe la habitación. Lo mismo vale para
*"Solo un supervisor de limpieza puede aprobar una inspección o verificar
una limpieza."* y *"Solo un supervisor de limpieza puede asignar
tareas."*

**"… no es personal de limpieza de este alojamiento."** La persona que
eligió no tiene el rol Limpieza, está desactivada o está limitada a otros
alojamientos. Revísela en **Configuración → Personal y acceso**.

**"No hay ningún huésped registrado en esa habitación al que facturar."**
El cargo de minibar o lavandería necesita un huésped con entrada
registrada. Revise la habitación en la pantalla **Hoy** de la recepción.

**"No hay tarifa para … agréguela primero a la hoja de tarifas."** Esa
prenda y servicio no están en el tarifario, o están desactivados.
Agréguelos en **Lavandería → Tarifario**.

**"Aún pendiente: …"** al entregar la lavandería. Cuente de vuelta las
prendas que faltan o escriba una nota de faltantes.

**Los avisos de escalado no llegan por WhatsApp.** Compruebe que el
alojamiento tiene una conexión de WhatsApp activa en **Operaciones →
Canales**, y que los usuarios de Recepción y Administrador del hotel
tienen un número de móvil en su registro de usuario.

**La aplicación móvil no muestra nada asignado.** Abra **Disponibles**:
las tareas esperan allí hasta que alguien las tome.

## Para desarrolladores

La aplicación móvil, el Panel de habitaciones y las tareas funcionan con
endpoints de `kamra.api` (`hk_queue`, `hk_update_task`, `hk_claim_task`,
`hk_accept_task`, `hk_reject_task`, `hk_assign_task`, `hk_staff`,
`hk_post_consumable`, `hk_log_item`, `room_board`,
`set_housekeeping_status`); la lavandería funciona con `kamra.laundry`.
El escalado es la tarea programada
`kamra.housekeeping.escalate_overdue_tasks` (cada 15 minutos). Los
agentes de IA usan las mismas llamadas como herramientas MCP; consulte
[MCP tools](/mcp-tools#housekeeping) ([laundry](/mcp-tools#laundry)) y la
[API reference](/api-reference#laundry-housekeeping).
