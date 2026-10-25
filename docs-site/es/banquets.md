# Banquetes y grupos: eventos desde la consulta hasta el cierre

La aplicación Banquetes y grupos gestiona el negocio de eventos: bodas,
congresos, presentaciones, fiestas. Una sola **ficha del evento** lleva
un evento desde la primera llamada, pasando por la cotización, la orden
del evento y los pagos, hasta el cierre del salón esa noche. El personal
de Recepción y de Gestión de ingresos trabaja con los eventos; Finanzas y
Limpieza pueden consultarlos.

![El inicio de Banquetes: confirmados, en curso, pendientes de cobro y conversión, con la lista de eventos que requieren seguimiento](/img/banquets/home.png)

## Antes de empezar

1. **Agregue sus salones.** **Banquetes y grupos → Salones y espacios
   para eventos → Nuevo**. Introduzca el **Nombre del espacio para
   eventos**, el **Tipo**, los **Asientos (máximo de personas)**, el
   **Mínimo de asistentes para habilitar el salón**, el **Alquiler por
   día**, el **Alquiler por hora**, el **Mínimo de horas**, el tipo de
   impuesto del alquiler y los **Montajes admitidos**.

   ![La lista de salones y espacios para eventos: Boardroom, Riverside Deck, Garden Lawn y Grand Ballroom con asientos, alquiler por día y tarifa por hora](/img/banquets/venues.png)

2. **Cree el catálogo.** **Banquetes y grupos → Menús y servicios**. Un
   **menú** tiene una **Tarifa por persona**, un **Mínimo de personas** y
   sus tiempos. Un **servicio** es todo lo demás (pantalla LED, atril, DJ,
   decoración, bar, personal), con una tarifa y si es **Con cargo de
   forma predeterminada**. Los **platos** contienen recetas, para que el
   margen pueda contar el costo de los alimentos.

   ![El catálogo de banquetes: cinco paquetes de menú con precio por plato, mínimo de personas y tiempos](/img/banquets/catalogue.png)

3. **Revise los valores predeterminados.** **Banquetes y grupos →
   Configuración**: margen objetivo y margen mínimo, las etapas de pago
   predeterminadas y cuándo hacer seguimiento de una consulta. Consulte
   [Configuración](#configuracion).

## Encuentre un salón libre

- **Disponibilidad mensual** muestra cada salón por sesión (mañana,
  tarde, noche) durante un mes. Haga clic en un hueco libre para empezar
  una consulta en él. La barra superior cuenta las noches de fin de
  semana que siguen libres.
- **Agenda de eventos** muestra cada salón durante dos semanas. Haga clic
  en un día para revisarlo, o en un evento para abrirlo. **Consultar una
  fecha** busca una sola fecha.

![Disponibilidad mensual: cuatro salones por mañana, tarde y noche en octubre, con una reserva provisional en dos noches](/img/banquets/month.png)

![La agenda de eventos: los salones en el lateral, dos semanas en horizontal y un bloque de evento al final](/img/banquets/diary.png)

Un evento **confirmado** ocupa el salón. Un bloqueo **provisional** es
un bloqueo flexible: el salón aparece como bloqueado, pero todavía puede
venderlo. Dos eventos pueden compartir un salón el mismo día siempre que
sus horarios no se solapen.

## Registre una consulta

1. En **Banquetes**, haga clic en **Nueva consulta**.
2. Introduzca el **Nombre del cliente**, el **Teléfono** y el **Correo
   electrónico**. Elija una **Empresa** para clientes corporativos;
   decide a qué folio va la cuenta.
3. Elija el **Tipo de evento**, la **Fecha** (y la **Fecha de
   finalización** para un evento de varios días), el **Número de
   asistentes previsto** y la **Sesión**. Una sesión (**Vespertino**, etc.)
   fija el horario y se guarda en el evento. Elija **Horario
   personalizado** para indicar su propio **De** y **A**.
4. Elija de dónde **Vino de** el cliente.
5. En **Salones disponibles para estas fechas y horarios**, elija un
   salón. Los salones ocupados no se pueden elegir; Kamra avisa cuando un
   salón es más pequeño que el número de asistentes.
6. Escriba **Lo que pidieron** con las palabras del cliente.
7. Haga clic en **Abrir la consulta**.

![Una nueva consulta de evento: cliente, tipo de evento, fecha, asistentes, sesión y el selector de salón con Grand Ballroom elegido](/img/banquets/new-enquiry.png)

El alquiler del salón entra en la cotización como primera línea, y se
fija una fecha de seguimiento (2 días de forma predeterminada).

![Apertura de una consulta y, después, alta de un menú de cóctel y una pantalla LED en su cotización](/img/banquets/enquiry-to-quote.gif)

## Trabaje con la ficha del evento

La ficha tiene seis pasos en la parte superior. Cada uno muestra una
marca de verificación cuando está terminado, o lo único que falta. Puede
abrir cualquier paso en cualquier momento.

![La cabecera de la ficha del evento: cotización, cobrado, saldo y margen, y los seis pasos: Consulta, Cotización, Margen, Resumen de pagos, Documentos, El evento](/img/banquets/function.png)

| Paso | Qué hace en él |
| --- | --- |
| **Consulta** | Datos del evento, tipo de montaje, asistentes garantizados, contacto, datos de facturación e impuestos, camerino, notas. |
| **Cotización** | Las líneas, el descuento y el cargo por servicio. |
| **Margen** | Ingresos frente a costos, y el pedido a cocina. |
| **Resumen de pagos** | Condiciones de pago y cobros. |
| **Documentos** | Cotización, contrato, orden del evento, lista de materiales, factura. |
| **El evento** | Contar lo servido, daños, depósito, cierre. |

## Prepare la cotización

1. Abra el paso **Cotización**.
2. Haga clic en **+ Menú** y en **Agregar** un paquete de menú. Su
   cantidad sigue a los asistentes garantizados.
3. Haga clic en **+ Servicio** y en **Agregar** lo que el cliente
   contrata. Haga clic en **Sin cargo** en su lugar para regalarlo: no
   cuesta nada en la cotización pero sigue apareciendo en la orden del
   evento y en la lista de materiales.
4. Cambie **Acordado** a la tarifa negociada en cualquier línea. La
   columna **Tarifa base** conserva el precio de lista.
5. Opcional: **Descuento sobre toda la cotización** y **Cargo por
   servicio (%)**.
6. Haga clic en **Guardar y recalcular precio**.

![Lo que contrata el cliente: alquiler del salón, menú, decoración, DJ, escenario, pantalla LED y aparcacoches como líneas con cargo, y tres líneas de cortesía, con los totales](/img/banquets/quote.png)

Un descuento sobre toda la cotización se reparte entre las líneas de
forma proporcional, así cada línea mantiene su propio tipo de impuesto.
Cada cambio queda registrado en **Evolución del precio**, con lo que
valía la cotización antes y después. Lo que aún se está negociando va en
**Conceptos por acordar**, cada uno con el efecto que tendría en el
precio si se acuerda.

El paso **Margen** muestra ingresos, costo y margen. Elija los platos del
menú (o ponga un costo a los servicios en el catálogo) para que el margen
los cuente. Las cotizaciones por debajo del margen mínimo se marcan.

## Envíe la cotización

1. Abra el paso **Documentos**.
2. Haga clic en **Emitir cotización v1**. Esto numera la cotización y la
   deja válida durante 15 días. Vuelva a emitirla después de un cambio
   para crear la siguiente versión.
3. Haga clic en **Enviar correo al huésped** o **Enviar WhatsApp al
   huésped**. El correo necesita el correo electrónico del cliente en el
   paso Consulta; WhatsApp necesita un teléfono y un número de
   [WhatsApp](/whatsapp) conectado.
4. Haga clic en **Abrir** en cualquier documento para verlo o imprimirlo.

![El paso Documentos: cotización, contrato, orden del evento, lista de materiales y factura, y los botones para emitirlos](/img/banquets/documents.png)

Si una cotización pasa 3 días sin respuesta, el evento aparece en la
lista de la mañana, y Kamra envía un recordatorio por correo al cliente
si tiene su correo electrónico.

## Registre la respuesta del cliente y confirme

1. En el evento, haga clic en **Respuesta del huésped**.
2. Elija el **Resultado** (**Confirmado**, **Cambios solicitados**,
   **Rechazado**) y el **Medio de respuesta** (teléfono, correo,
   WhatsApp).
3. Deje marcado **Cambiar también el evento a Confirmado** para
   confirmarlo ahora.
4. Haga clic en **Guardar respuesta**.

![El panel Respuesta del huésped en un evento provisional: resultado Confirmado, medio Teléfono, con la casilla para confirmar también el evento](/img/banquets/guest-response.png)

También puede cambiar el estado de un evento con los botones de la parte
superior: **Provisional**, **Confirmar**, **Cancelado**, **Perdido**, y
**Reabrir** para devolver a consulta un evento provisional, cancelado o
perdido. Cancelado y Perdido piden un motivo; el motivo se guarda para el
informe de oportunidades. En un evento confirmado, **Cerrar evento** abre
el paso **El evento** (consulte
[Cierre la noche del evento](#cierre-la-noche-del-evento)).

Cuando se confirma un evento, Kamra crea la **Lista de tareas por
departamento** (tareas de Ventas, Finanzas, Limpieza y Alimentos y
bebidas con fechas límite contadas hacia atrás desde el evento) y avisa a
esos equipos.

## Cobre los pagos

1. Abra el paso **Resumen de pagos**.
2. Haga clic en **Usar el calendario habitual** para fijar las etapas
   predeterminadas (anticipo al confirmar, un pago parcial, el saldo al
   finalizar), o en **Agregar** para crear las suyas. Haga clic en
   **Guardar términos**.
3. Cuando entre dinero, haga clic en **Registrar ingreso de dinero**.
   Introduzca el **Importe**, el **Concepto** (Anticipo, Pago, Depósito
   de garantía, Reembolso), **Cómo**, una **Referencia** y qué etapa de
   pago se completa en **Etapa de pago que se completa**.

![Condiciones de pago: anticipo de reserva recibido, antes del evento y al finalizar pendientes](/img/banquets/money.png)

Una etapa en porcentaje sigue a la cotización cuando cambia; un importe
fijo no se mueve. Un depósito de garantía es dinero retenido, no un pago:
nunca se descuenta de la cuenta.

### Cargue el evento a la cuenta del grupo

Para poner el evento en la misma cuenta que las habitaciones de los
huéspedes, vincúlelo a su reserva de grupo:

1. En **Reserva de grupo** (en la tarjeta de facturación del paso
   **Consulta**, o en el paso **Resumen de pagos** junto a **Registrar en
   la cuenta**), elija el grupo.
2. Haga clic en **Vincular a grupo**.
3. Cuando el evento esté confirmado, haga clic en **Registrar en la
   cuenta**. Se carga al folio principal del grupo (consulte
   [Facturación](/es/billing)).

![La tarjeta de liquidación en el paso Resumen de pagos: la lista Reserva de grupo con los invitados de la boda Sharma-Verma elegidos, Vincular a grupo y Registrar en la cuenta](/img/banquets/group-link.png)

La lista muestra los grupos de este hotel, no cancelados, que se alojan
en el mes anterior o posterior al evento. Un grupo ya vinculado a otro
evento aparece desactivado. Elija **Sin vincular a un grupo** y haga clic
en **Desvincular** para deshacerlo. Cuando el evento ya está facturado o
completado, su grupo no se puede cambiar.

## Emita la orden del evento

1. Confirme el evento.
2. En **Documentos**, haga clic en **Emitir orden del evento**.
3. Haga clic en **Abrir** en **Orden del evento (BEO)** e **Imprimir**.

La orden del evento es la hoja de trabajo para los equipos de banquetes,
cocina y audiovisuales: espacio, horarios, asistentes, montaje, cada
línea (también las gratuitas) con los menús desglosados en tiempos, y las
notas de la orden del evento. La **Lista de materiales** indica qué debe
llegar al salón y para cuándo.

![La orden del evento de banquete para la recepción Sharma-Verma: datos del evento, orden de desarrollo y lo que incluye](/img/banquets/beo.png)

## Cierre la noche del evento

1. Después del evento, abra **El evento**.
2. Haga clic en **Cerrar el evento**.
3. Introduzca los **Comensales atendidos**. La cuenta usa los asistentes
   garantizados o el recuento real, el que sea mayor.
4. Si algo se rompió, introduzca el importe en **Descontar del depósito**
   y la **Descripción de los daños**.
5. Deje marcado **Devolver ahora el saldo del depósito** para reembolsar
   el resto, y elija cómo.
6. Haga clic en **Cerrar evento**.

![Cierre del evento: comensales atendidos, daños, devolución del depósito y los importes retenidos y a devolver](/img/banquets/close-out.png)

El evento pasa a **Completado**. Los daños quedan como un cargo en el
evento, y el reembolso es una línea en su libro contable.

### Reabra un evento cerrado

Un usuario de Gestión de ingresos, Finanzas o Administrador del hotel
puede reabrir un evento **Completado** para corregir la ficha:

1. Haga clic en **Reabrir** en la parte superior del evento.
2. Escriba **¿Por qué se reabre?** (obligatorio) y haga clic en
   **Reabrir**.

El evento vuelve a **Confirmado**, y el motivo queda en sus notas y en el
registro de actividad. Los cobros, reembolsos y daños ya registrados se
conservan. En **El evento**, haga clic en **Cerrar nuevamente**: esta vez
solo se vuelven a contar los comensales. Facture cualquier otra cosa como
una línea del evento. Un evento ya cargado a un folio no se puede
reabrir; corrija la cuenta en el folio.

## Vea los próximos meses

En el inicio de Banquetes, abra **Mes a mes**. Cada mes muestra el valor
de los eventos confirmados y de los que siguen en curso, según la fecha
del evento, con los totales por estado. Cubre los seis meses siguientes
desde el día 1; ponga **De** y **A** para ver cualquier otro periodo.

## Imprima los registros

**Banquetes y grupos → Registros**: elija el periodo una vez y cambie
entre **Eventos**, **Cotizaciones**, **Consultas**, **Libro de caja** y
**Resumen de ventas**. Cada uno tiene **CSV** e **Imprimir**.

![Los registros de banquetes de octubre: un evento con asistentes, valor, cobrado y pendiente](/img/banquets/registers.png)

## Bloquee habitaciones para un grupo

Para las habitaciones de los huéspedes, use **Grupos y bloqueos**:

1. Haga clic en **Nuevo**, introduzca el **Nombre del grupo**, la
   **Llegada**, la **Salida** y la **Fecha límite del bloqueo**, y pulse
   **Guardar**.
2. Abra el grupo. Haga clic en **Agregar tipo de habitación**, indique
   cuántas habitaciones y pulse **Guardar bloqueo**.
3. Haga clic en **Confirmar bloqueo** cuando el cliente esté de acuerdo.
4. A medida que lleguen los nombres, use **Reservar una habitación del
   bloqueo** para reservar a un huésped dentro del bloqueo. Las
   habitaciones bloqueadas no vendidas vuelven a la venta después de la
   fecha límite.

![Un grupo: invitados de la boda Sharma-Verma, Abierto, con Agregar tipo de habitación, Confirmar bloqueo y Abrir folio del grupo](/img/banquets/group.png)

Para reservar una habitación de cambio para los novios y su séquito, use
**Camerino** en el paso Consulta del evento. Pone un bloqueo real sobre
esa habitación, así que sale del inventario disponible para la venta.

## Configuración

**Banquetes y grupos → Configuración**:

| Ajuste | Valor predeterminado | Qué hace |
| --- | --- | --- |
| Margen objetivo | 40% | El margen al que apuntan las cotizaciones. |
| Margen mínimo | 25% | Las cotizaciones por debajo se marcan para aprobación. |
| Anticipo al confirmar | 25% | Primera etapa de pago de un evento nuevo. |
| Pago parcial | 50% | Segunda etapa de pago. |
| Vencimiento del pago parcial | 15 días antes | Cuándo vence el pago parcial. |
| Hacer seguimiento de una consulta después de | 2 días | La fecha de seguimiento de una consulta nueva. |

## Conviene saber

- **Requiere seguimiento**, en el inicio de Banquetes, muestra lo que
  necesita cada evento abierto: seguimientos pendientes, una cotización
  sin respuesta desde hace 3 días, bloqueos provisionales que vencen en
  3 días, pagos pendientes, un evento confirmado sin orden del evento a
  7 días, sin asistentes garantizados a 3 días, un contrato sin firmar o
  nada cobrado a 14 días, y eventos ya pasados que no están cerrados.
- Cada mañana a las 08:30, Kamra envía los asuntos urgentes de los
  próximos 45 días al responsable del evento por WhatsApp cuando hay un
  número conectado, o al equipo de Recepción.
- Confirmar sin asistentes garantizados usa el número de asistentes
  previsto como garantía.
- Solo un evento confirmado recibe orden del evento o se puede cerrar.
- Un evento **Completado** no se puede editar hasta que alguien lo
  reabra (consulte [Reabra un evento cerrado](#reabra-un-evento-cerrado)).
- La única forma de llegar a **Completado** es el cierre en **El
  evento**, así los comensales y el depósito siempre quedan liquidados.
  El botón **Cerrar evento** de la parte superior le lleva allí.
- El alcohol nunca va a la cuenta de una empresa o de un grupo.
  **Registrar en la cuenta** deja fuera esas líneas, que se liquidan
  aparte.

## Solución de problemas

**"… ya está confirmado para … el …".** Otro evento confirmado ocupa ese
salón en horarios que se solapan. Mueva uno de los dos o elija otro
salón.

**Enviar correo al huésped aparece desactivado.** Emita primero la
cotización y agregue el correo electrónico del cliente en el paso
Consulta.

**Registrar en la cuenta aparece desactivado.** El evento no está
vinculado a una reserva de grupo (elija una en **Reserva de grupo** y
haga clic en **Vincular a grupo**), o todavía es una consulta.

**"Solo se puede reabrir un evento cerrado (Completado) …"** o **"Este
evento ya está facturado a …"** al reabrir. Solo se puede reabrir un
evento completado que todavía no está en un folio.

**El margen parece demasiado bueno.** La nota amarilla del paso Margen
muestra las líneas que aún no tienen costo. Elija los platos del menú o
agregue un costo al servicio en el catálogo.

## Para desarrolladores

Los eventos están en `kamra/banquet.py` y `kamra/banquet_ops.py` (el
doctype `Venue Booking`). Los agentes de IA usan las herramientas
`banquet_*`: `banquet_availability`, `banquet_enquiry`,
`banquet_add_menu`, `banquet_quote`, `banquet_status`,
`banquet_record_receipt`, `banquet_link_group`, `banquet_close_out` y
más. Reabrir un evento cerrado es `kamra.banquet.reopen_function` (sin
herramienta MCP). Consulte [MCP tools](/mcp-tools) y la
[API reference](/api-reference#banquets-functions-quotations-event-orders).
