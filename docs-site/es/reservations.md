# Reservas - reservas, calendario de ocupación y cancelaciones

Esta página explica cómo crear una reserva, buscarla y cambiarla, cobrar un
anticipo y cancelarla. Los usuarios de Recepción y Administrador del hotel pueden reservar;
el calendario de ocupación, el calendario de disponibilidad y la lista de reservas están en la aplicación
**Recepción**. El registro de entrada y salida de los huéspedes está en [Recepción](/es/front-desk).

![La ventana Nueva reserva: huésped, teléfono, tipo de habitación, fechas, personas y plan de comidas a la izquierda, y la cotización en directo con las condiciones de cancelación a la derecha](/img/reservations/booking-dialog.png)

## Antes de empezar

1. **Habitaciones, tipos de habitación y tarifas.** **Administración → Habitaciones** y **Tipos de habitación**,
   y sus tarifas y temporadas en **Ingresos** ([Ingresos](/es/revenue)). La
   cotización los usa.
2. **Sus políticas de estancia.** **Configuración → Políticas de estancia**: estancia mínima,
   **Cancelación gratuita hasta** (días antes de la llegada), **Cargo por cancelación
   tardía**, **Cargo por no presentación** y **Anticipo esperado al reservar**. La
   ventana de reserva los incluye en la cotización y la cancelación los aplica.
3. **Servicios adicionales, empresas y agencias de viajes**, si los vende. Los servicios adicionales
   aparecen como etiquetas en la ventana de reserva; las empresas y las agencias de viajes vienen
   de **Ingresos → Empresas** y **Agencias de viajes**.

## Crear una reserva

1. Pulse **Nueva reserva** en la barra superior. Está en todas las pantallas.
2. Escriba el **Nombre del huésped**. Los huéspedes que ya se alojaron aparecen mientras
   escribe; elija uno para vincular la estancia a su perfil ("Returning guest ·
   4 stays"). Un huésped en la lista de bloqueo muestra una insignia roja.
3. Añada el **Teléfono**. El prefijo del país ya está puesto; escriba el número local.
4. Elija el **Tipo de habitación**, la fecha de **Registro de entrada** y el número de
   **Noches**, y luego **Adultos** y **Niños**. Elija un **Plan de comidas** y un
   **Plan tarifario**, y escriba un código de **Cupón** si el huésped tiene uno.
5. Revise la **Cotización** de la derecha. Se actualiza mientras escribe: habitación, impuestos,
   comidas, servicios adicionales y el total, con las condiciones de cancelación y de no presentación
   debajo. La línea de cancelación se calcula desde hoy, igual que
   la cobraría una cancelación. Dice "Cancelación gratuita hasta" una
   fecha y lo que se cobra después; "No reembolsable desde ahora" con el
   cargo, cuando el plazo gratuito ya terminó; o "Cancelación gratuita." Nunca
   muestra una fecha ya pasada.
6. Pulse **Confirmar reserva**.

![Crear una reserva: escribir el nombre y el teléfono del huésped, elegir Deluxe, fijar la fecha y tres noches, confirmar, y la reserva queda creada con la habitación 201](/img/reservations/booking.gif)

Recibe la referencia de la reserva y la habitación que asignó Kamra. Si no se
pudo asignar ninguna habitación, la reserva se crea igualmente; asigne una más tarde desde la
reserva (consulte [Cambiar una reserva](#cambiar-una-reserva)). La estancia aparece en
**Llegadas** en **Hoy** en su fecha de entrada.

Para una estancia de pocas horas, cambie **Durante la noche** a **Uso diurno** y fije la
franja horaria. El huésped entra y sale el mismo día.

## Añadir empresa, servicios adicionales y datos de llegada

Abra **Empresa, complementos y detalles de llegada** en la ventana de reserva para:

- **Empresa (facturación corporativa)** y **Agencia de viajes**. Una empresa la convierte en una
  reserva corporativa; las reglas de facturación de la empresa deciden qué paga.
- **Servicios adicionales**: pulse una etiqueta para añadirlo (traslado al aeropuerto, un ritual de spa…).
  Los servicios adicionales se suman a la cotización con sus impuestos y se cargan al folio.
- **Reserva realizada para otra persona**: el nombre, el teléfono y la relación de quien reserva,
  y **Enviar enlaces y novedades a** quien reserva, al huésped o a ambos.
- **Solicitudes especiales**, que llegan a recepción como instrucción, y
  casillas para **Recogida en el aeropuerto**, **Estacionamiento con servicio de aparcacoches**, **Entrada anticipada** y
  **Salida tardía**.
- Cómo y cuándo llega el huésped, **Camas adicionales**, **Motivo de la visita** y
  **Categoría de huésped**.

![La ventana de reserva con Empresa, complementos y detalles de llegada abierto: empresa y agencia de viajes, etiquetas de servicios adicionales con el traslado al aeropuerto seleccionado, la opción de quien reserva, solicitudes especiales y casillas de llegada](/img/reservations/booking-more.png)

Si hay más personas de las que admite el tipo de habitación, la ventana lo indica y
ofrece **Dividir en 2 habitaciones**. Cuando el tipo de habitación admite camas adicionales, puede
en su lugar mantener a todos en una habitación a un precio que acuerde, con una nota de
quién lo acordó.

## Reservar varias habitaciones para las mismas personas

1. En **Nueva reserva**, rellene la primera habitación como siempre.
2. Pulse **Añadir otra habitación**. Cada habitación adicional tiene su propio tipo de habitación,
   adultos y plan de comidas.
3. La cotización muestra cada habitación y el **Total · todas las habitaciones**.
4. Pulse **Confirmar reserva**.

![Una reserva de tres habitaciones Standard: las habitaciones 2 y 3 añadidas debajo de la primera, y la cotización con el total de todas las habitaciones](/img/reservations/multi-room.png)

Kamra reserva todas las habitaciones bajo un mismo grupo, para poder facturarlas juntas. Si
algunas habitaciones no se pueden reservar, le indica cuántas reservó y por qué fallaron
las demás. Los cupones, los servicios adicionales y los datos de quien reserva se añaden a cada estancia
después. Para bloquear habitaciones para un grupo cuyos nombres llegarán más tarde,
use [Grupos y bloqueos](#bloquear-habitaciones-para-un-grupo).

## Poner a un huésped en la lista de espera

Cuando las fechas están completas, puede tomar igualmente los datos del huésped:

1. Rellene **Nueva reserva** como siempre.
2. Pulse **Lista de espera** en lugar de **Confirmar reserva**.

La estancia se guarda con el estado Lista de espera y sin habitación. Cuando se libera una
habitación, abra la reserva y pulse **Pasar a una habitación**: Kamra le da la
primera habitación libre del tipo y la confirma. Una estancia en lista de espera que nadie
pasa a una habitación la elimina la auditoría nocturna dos días después de su fecha de salida.

## Buscar una reserva

- **Recepción → Reservas** muestra todas las reservas. Busque por referencia,
  huésped o habitación, filtre por **Estado** y por fechas de entrada, y use
  **Exportar** para obtener una hoja de cálculo.
- El cuadro de búsqueda de la barra superior (o ⌘K / Ctrl+K) encuentra huéspedes, reservas
  y habitaciones desde cualquier pantalla.

Pulse una reserva para abrir su panel de detalle: todo sobre la estancia en una
pantalla.

![El panel de detalle de una reserva confirmada: estado y origen, totales de facturación, el anticipo y el depósito de garantía, y después las fechas de la estancia y la identidad](/img/reservations/reservation.png)

- **Facturación**: total, pagado y saldo pendiente, con **Abrir folio →**.
- **Anticipo de reserva** y **Depósito de garantía** (consulte [Cobrar un anticipo antes de la
  llegada](#cobrar-un-anticipo-antes-de-la-llegada)).
- **Estancia**: las fechas (editables), **Llegada tardía**, noches, huéspedes y la
  tarifa por noche confirmada.
- **Identidad**: el estado del registro en línea y la foto del documento del huésped, con
  **Verificar identidad** después de que el huésped haga el registro en línea.
- **Habitación**, **Huésped** (con **Historial del huésped →**) y **Reservado por**.
- **Solicitudes especiales**: escriba y pulse **Guardar nota**.
- Abajo: **Registrar entrada**, **Registrar salida**, **Ficha de registro** y
  **Cancelar esta estancia…**, según corresponda.

![La mitad inferior del panel: tarjetas de estancia, identidad, habitación y huésped, solicitudes especiales, y los botones Registrar entrada, Ficha de registro y Cancelar esta estancia](/img/reservations/reservation-lower.png)

## Cambiar una reserva

Desde el panel de detalle de la reserva:

- **Nuevas fechas:** cambie el **Registro de entrada** o la **Salida** en la tarjeta **Estancia**
  y pulse **Actualizar fechas y recalcular precio**. Kamra calcula el precio de las nuevas fechas y
  le pide que confirme el nuevo total con el huésped antes de guardar. Una
  reserva con precio manual mantiene su importe.
- **Otra habitación:** pulse **Cambiar de habitación** (o **Asignar habitación**) en la
  tarjeta **Habitación**. Consulte [Cambiar a un huésped de habitación](/es/front-desk#cambiar-a-un-huesped-de-habitacion).
- **Llegada tardía:** marque **Llegada tardía** para que la auditoría nocturna mantenga la
  llegada como Pendiente de entrada en lugar de marcarla como no presentada.

Solo se pueden cambiar las reservas confirmadas y las que ya tienen la entrada registrada.

## Mover una estancia en el calendario de ocupación

**Recepción → Calendario de ocupación** muestra las habitaciones en el lateral y las fechas en la
parte superior, con cada estancia como una barra. Úselo para ver quién está en cada habitación y para
mover estancias.

Para reservar una habitación libre, pulse una celda vacía de hoy o de una fecha posterior.
**Nueva reserva** se abre con ese tipo de habitación, esa habitación y esa fecha ya puestos, y
la reserva se mantiene en esa habitación (muestra **Habitación** y el número). Si
cambia el tipo de habitación, Kamra elige la habitación por usted.

![El calendario de ocupación de dos semanas: habitaciones agrupadas por tipo, barras de huéspedes y la fila de posición con las habitaciones vendidas cada día](/img/reservations/tape-chart.png)

1. Pulse (o toque) la barra de un huésped. Se abre un panel con la habitación, las fechas
   y las acciones de esa estancia.
2. **Cambiar de habitación** abre el selector de habitaciones: elija una habitación, revise la línea
   de precio, elija un motivo y pulse **Cambiar a la habitación**. Consulte
   [Cambiar a un huésped de habitación](/es/front-desk#cambiar-a-un-huesped-de-habitacion).
3. **Cambiar fechas** muestra las fechas de entrada y salida. Cámbielas
   y Kamra muestra el nuevo número de noches y el nuevo total de la estancia. Pulse
   **Confirmar nuevas fechas** (o **Confirmar nuevas fechas y precio** cuando el
   total cambia). Cuando el huésped ya tiene la entrada registrada, solo se puede cambiar la fecha de
   salida.
4. **Registrar entrada** aparece el día de llegada y abre el registro de entrada guiado.
   **Registrar salida** aparece para un huésped alojado y abre la salida
   guiada.
5. Para anotar cuándo llega y se va el huésped, fije las horas en
   **Horarios de llegada/salida (ETA · ETD)** y pulse **Establecer**.
6. **Abrir reserva** abre la reserva en la lista de reservas.

Con un ratón también puede arrastrar:

- Arrastre una barra a la fila de otra habitación. El selector de habitaciones se abre con esa
  habitación elegida, para que vea el precio y elija un motivo antes del cambio.
- Arrastre una barra hacia los lados, o arrastre su borde inicial o final, para cambiar las
  fechas. El panel se abre con las nuevas fechas y el nuevo precio;
  no cambia nada hasta que confirme.

Arrastrar no funciona en pantallas táctiles. En una tableta, toque la barra y use los
botones. Kamra comprueba cada cambio en el servidor: se rechaza una habitación ocupada,
o un cambio de fechas que se solapa con otra reserva.

![El panel que se abre desde una barra del calendario de ocupación: la habitación y las fechas de la estancia, los botones Cambiar de habitación, Cambiar fechas y Registrar salida, y las horas de llegada y salida](/img/reservations/tape-bar.png)

Qué más hay en el calendario de ocupación:

- La fila **Posición** muestra las habitaciones vendidas sobre las disponibles cada día.
  ▲ significa que hay un recargo por demanda activo; OB significa que el día tiene sobreventa.
- Un punto en cada barra marca estancias VIP, corporativas, de grupo u OTA; un candado marca
  una habitación retenida por un bloqueo de habitaciones.
- Cuando una llegada está prevista antes de la hora de salida del huésped anterior, el
  calendario marca un conflicto de cambio de huésped.
- **Por hora** muestra hoy hora a hora, para las estancias de uso diurno.
- **Asignar habitaciones automáticamente** sugiere una habitación para cada llegada sin habitación,
  según el tipo y las preferencias. **Revisar** marca una elección que conviene revisar;
  **Asignar** las coloca todas.

## Vender desde el calendario

**Recepción → Calendario** muestra dos semanas de disponibilidad por tipo de habitación:
el número de habitaciones libres y la tarifa por noche para dos adultos, con las temporadas
aplicadas. Pulse una celda para abrir **Nueva reserva** con ese tipo de habitación y esa fecha
ya puestos.

![El calendario de disponibilidad: habitaciones libres y la tarifa de cada tipo de habitación durante dos semanas, con los fines de semana en verde](/img/reservations/calendar.png)

## Cobrar un anticipo antes de la llegada

El recuadro **Anticipo de reserva** está en la pantalla de reserva confirmada y en el
panel de detalle de la reserva. Muestra lo que espera el alojamiento (**Anticipo
esperado al reservar** en Políticas de estancia), lo que ha entrado y lo que
falta.

- **Registrar pago**: el huésped pagó en recepción o por transferencia. Elija el
  medio, compruebe el importe y pulse **Registrar ₹…**. Pasa por su
  caja, así que necesita una sesión de caja abierta.
- **Enviar enlace de pago**: aparece cuando hay una pasarela de pago conectada. Kamra
  crea un enlace por el importe pendiente y un mensaje listo; pulse **Copiar
  mensaje** o **WhatsApp**. Cuando el huésped paga, el anticipo se registra
  solo.

El dinero queda en el folio del huésped como anticipo y se descuenta de la
cuenta en el registro de entrada. Una reserva en estado Retenido o Pago pendiente se confirma con
su anticipo. Cobrar a un huésped que ya está alojado se hace en el
folio; consulte [Facturación](/es/billing).

## Cancelar una reserva

1. Abra la reserva (**Reservas** → púlsela).
2. Pulse **Cancelar esta estancia…** abajo.
3. Lea la línea de arriba. Le indica cuántos días quedan hasta la
   llegada y si la cancelación es gratuita o qué cargo se aplica.
4. Elija un **Motivo** y añada una nota si quiere.
5. Para eximir al huésped del cargo, marque **Exonerar el cargo (decisión del gerente que queda registrada)**.
6. Pulse **Confirmar cancelación**.

![Cancelar una reserva el día de llegada: dentro del plazo de 1 día, así que se cobrará la primera noche (₹2,800), con el motivo, la nota y la opción de eximir el cargo](/img/reservations/cancel-preview.png)

Kamra da un número de cancelación (CXL-…) y carga cualquier cargo al folio.
Pulse **Imprime/comparte la carta de confirmación** para obtener una carta que enviar al
huésped.

![La carta de confirmación de la cancelación con el número de cancelación, el valor de la estancia y el cargo por cancelación](/img/reservations/cancellation-letter.png)

Cómo se calcula el cargo:

- Cancelar antes de los días de **Cancelación gratuita hasta** previos a la llegada
  es gratuito.
- Dentro de ese plazo se aplica el **Cargo por cancelación tardía**: Ninguno, Primera
  noche o Toda la estancia.
- Si el alojamiento tiene tramos de cancelación (por ejemplo gratis con más de 7 días,
  50% de 3 a 7 días, 100% con menos de 3), el tramo de los días que quedan fija el
  porcentaje en su lugar.
- Las fechas de una temporada no reembolsable se cobran al 100%.

Solo se pueden cancelar las reservas confirmadas. Un huésped que está alojado registra
la salida en su lugar. No se puede cancelar cambiando el campo de estado; tiene que hacerse
con **Cancelar esta estancia…** para que se aplique la política.

## Responder a una solicitud de reserva

Cuando el motor de reservas funciona en modo Solicitar reserva, las reservas en línea
llegan como solicitudes que usted debe aprobar
([Motor de reservas](/es/booking-engine)). Aparecen en **Solicitudes de reserva** en
**Hoy** y con el estado Solicitado. Una solicitud no retiene ninguna habitación.

- **Aceptar** vuelve a comprobar la disponibilidad y toma una habitación.
- **Rechazar** necesita un motivo, cancela la solicitud sin cargo y avisa
  al huésped.

## Reservar en otro alojamiento

Si gestiona más de un alojamiento, **Recepción → Central de reservas**
busca en todos a la vez.

1. Fije **Registro de entrada**, **Noches**, **Adultos** y **Niños**, y pulse
   **Buscar**.
2. Cada alojamiento con disponibilidad muestra sus tipos de habitación, las habitaciones libres y el total
   con impuestos.
3. Pulse **Reservar**, introduzca el nombre y el teléfono del huésped, y pulse **Confirmar
   reserva**.

![Central de reservas: disponibilidad para una noche y dos adultos en tres alojamientos, con un botón Reservar en cada tipo de habitación](/img/reservations/crs.png)

## Bloquear habitaciones para un grupo

Para una boda, una conferencia o un circuito, bloquee primero un conjunto de habitaciones y ponga
los nombres de los huéspedes después. Los grupos están en **Banquetes y grupos → Grupos y bloqueos**.

1. Pulse **Nuevo**, indique el **Nombre del grupo**, la **Llegada**, la **Salida**
   y la **Fecha límite del bloqueo**. Guarde.
2. Abra el grupo. En **Bloqueo de habitaciones**, pulse **Agregar tipo de habitación**, elija el
   tipo, el número de habitaciones y la tarifa por noche, y luego **Guardar bloqueo**.
3. A medida que lleguen los nombres, use **Reservar una habitación del bloqueo**: elija el tipo de habitación, escriba el
   nombre y el teléfono del huésped, y pulse **Reservar del bloqueo**. Cada habitación tomada es una
   reserva normal en la **Lista de huéspedes del grupo**.

![Un grupo con un bloqueo de cuatro habitaciones Deluxe, dos ya tomadas, el formulario para tomar habitaciones y la lista de huéspedes del grupo](/img/reservations/group.png)

Las habitaciones del bloqueo quedan retenidas para el grupo hasta la fecha límite. Después de la
fecha límite, las habitaciones no tomadas vuelven a la venta. **Abrir folio del grupo** abre la
cuenta principal del grupo. Para eventos vinculados al grupo, consulte
[Banquetes](/es/banquets).

## Retirar una habitación de la venta

Para mantener una habitación libre para uso interno, un VIP, el propietario o mantenimiento:

1. **Recepción → Bloqueos de habitaciones → Nuevo**.
2. Elija la **Habitación** y el **Motivo** (Uso interno, Bloqueo VIP, Propietario,
   Mantenimiento, Otro).
3. Fije **Desde la fecha** y **Hasta la fecha (excluida)**, añada una **Nota** y guarde.

Una habitación bloqueada no aparece como disponible y no se vende; se muestra con un
candado en el calendario de ocupación. Ponga el **Estado** en Liberado para devolverla a la venta.

## Configuración

| Ajuste | Dónde | Valor por defecto | Qué hace |
| --- | --- | --- | --- |
| Estancia mínima | Configuración → Políticas de estancia | 1 noche | Se rechazan las reservas más cortas. Las temporadas pueden fijar su propio mínimo. |
| Cancelación gratuita hasta | Configuración → Políticas de estancia | 1 día antes | Las cancelaciones anteriores a este plazo son gratuitas. |
| Cargo por cancelación tardía | Configuración → Políticas de estancia | Primera noche | Ninguno, Primera noche o Toda la estancia, cobrado dentro del plazo. |
| Cargo por no presentación | Configuración → Políticas de estancia | Primera noche | Lo carga la auditoría nocturna cuando un huésped no llega. |
| Anticipo esperado al reservar | Configuración → Políticas de estancia | 0% | Se incluye en la cotización de la ventana de reserva y se muestra en el recuadro Anticipo de reserva. |
| Mantener reservas sin confirmar durante | Configuración → Recepción → Reservas provisionales y venta | 120 min | Cuánto tiempo mantiene su habitación una reserva Retenido o Pago pendiente antes de liberarse. |
| Mensaje de venta adicional | Configuración → Recepción → Reservas provisionales y venta | - | Aparece en la parte superior de la ventana de reserva como recordatorio de lo que debe ofrecer. |
| Liberar las reservas de llegada sin garantía a las | Configuración → Recepción → Auditoría nocturna y no presentados | En blanco (nunca) | A esta hora, las llegadas de hoy sin pago ni anticipo (que no sean reservas de OTA o de empresa, ni estén marcadas como tardías) se cancelan sin cargo. |

## Conviene saber

- Una reserva nueva no puede empezar en el pasado.
- Se rechaza una doble reserva de la misma habitación para las mismas fechas.
- A un huésped en la lista de bloqueo solo puede reservarle un Administrador del hotel, que debe marcar
  **Entiendo y deseo crear la reserva para este huésped de todos modos** e indicar un motivo. Una
  reserva de varias habitaciones no puede saltarse la lista de bloqueo.
- Cambiar las fechas o el tipo de habitación recalcula el precio de la estancia. Kamra siempre muestra el
  nuevo total y pregunta antes de guardar.
- Cada reserva, cambio, movimiento y cancelación queda en el registro de
  actividad con quién lo hizo.
- La auditoría nocturna marca las no presentaciones; consulte [Auditoría nocturna](/es/night-audit).

## Solución de problemas

**"Check-in … has already passed."** La fecha de entrada es anterior a hoy.
Elija hoy o una fecha posterior.

**"… is sold out for …"** Todas las habitaciones del tipo están vendidas al menos una
noche de la estancia (los bloqueos de grupo cuentan como vendidos). Pruebe otro tipo de habitación, use
**Lista de espera**, o busque un cambio en el calendario de ocupación.

**"This property requires a stay of at least … nights."** La estancia es
más corta que la estancia mínima del alojamiento o de la temporada.

**"Only confirmed bookings can be cancelled."** El huésped ya tiene la
entrada registrada (registre su salida en su lugar), o la reserva ya está cancelada.

**No aparece el botón Enviar enlace de pago.** No hay ninguna pasarela de pago conectada
para el alojamiento. Use **Registrar pago**, o conecte una pasarela (consulte
[Configuración](/es/settings)).

## Para desarrolladores

Las reservas se crean con `kamra.api.create_booking` (una habitación) y
`kamra.api.create_group_booking` (varias), con precio de `kamra.api.get_quote`.
El panel de detalle lee `kamra.api.reservation_detail`; los cambios de fechas usan
`kamra.api.amend_stay_preview` y `kamra.api.amend_stay`; la cancelación usa
`kamra.api.cancellation_preview` y `kamra.api.cancel_reservation`; la
lista de espera usa `kamra.api.promote_waitlist`. Los agentes de IA usan las herramientas `quote`,
`create_booking`, `add_to_waitlist`, `promote_waitlist`,
`cancellation_preview`, `cancel_booking`, `amend_stay`, `move_room` y
`create_group_block`. Consulte [MCP tools](/mcp-tools) y la
[referencia de la API](/api-reference).
