# Revisión de las traducciones al español

Fecha: 22 de octubre de 2026. Base de comparación: commit beaabe9a.

Se revisaron las 2,339 entradas existentes, se corrigieron 722 traducciones y se añadieron 467 entradas para etiquetas dinámicas, estados y compatibilidad con el diccionario existente. El recurso español contiene ahora 2,806 entradas.

La revisión se apoyó en las pantallas y operaciones del código: recepción, reservas, habitaciones, limpieza, lavandería, restaurante y cocina, caja, facturación, tarifas, banquetes y auditoría nocturna.

## Criterios aplicados

| Término de origen | Criterio en español |
| --- | --- |
| book / booking | reservar / reserva |
| guest / in-house | huésped / huésped alojado |
| room / hall | habitación / salón para eventos |
| free / complimentary | disponible para inventario; de cortesía o sin cargo para importes |
| rate / tax rate | tarifa de alojamiento o servicio / tasa de impuesto |
| deposit / security deposit | anticipo de reserva en la pantalla de anticipo / depósito de garantía para daños; depósitos y anticipos en el libro contable conjunto |
| collect / collected | cobrar / cobrado para dinero; recoger prendas en lavandería |
| bill / invoice / folio | cuenta / factura / folio hotelero |
| till / float / cash drop / bank deposit | caja / fondo de caja / entrega a caja central / depósito en el banco |
| allowance / void / settle | bonificación / anular / liquidar |
| function / pax | evento / personas o asistentes |
| service ticket / kitchen ticket | solicitud de servicio / comanda |
| fire / held (kitchen) | enviar a preparación / en espera |
| walk-in / upgrade / stayover | sin reserva previa / mejora de categoría / continúa alojado |
| no-show / night audit | no presentado / auditoría nocturna |

## Alcance y comprobaciones

- Se conservaron todas las claves previas del recurso español.
- No se cambiaron el diccionario árabe, el traductor compartido ni los mensajes de origen de las pantallas.
- El catálogo se sincronizó con los recursos y el extractor conserva las claves usadas mediante etiquetas o estados dinámicos.
- Todas las traducciones tienen contenido y mantienen sus variables de datos.
- Solo se omiten dos sufijos gramaticales ingleses: {ord} en los pisos y {ies} en una frase antigua de disponibilidad. No representan datos del huésped o de la reserva y no se usan para formar palabras en español.
- El catálogo no contiene claves duplicadas y sus valores españoles coinciden con el JSON.
- La prueba de extracción e importación conserva las 2806 entradas españolas y las 2151 árabes, incluidos los espacios de los fragmentos concatenados.
- Compilación de producción: correcta (npm run build).

Esta es una revisión de recursos y contextos de código. No incluye una comprobación visual exhaustiva de todas las pantallas ni la traducción de textos ingresados por cada alojamiento.

## Traducciones corregidas

| Clave de origen | Antes | Revisado | Contexto |
| --- | --- | --- | --- |
|  ({n} short) |  ({n} corto) |  (faltan {n}) | screens/Laundry.tsx |
|  - add the first item. |  : agrega el primer elemento. |  — agregue el primer artículo. | screens/Laundry.tsx |
| (F&B rate) | (tarifa de alimentos y bebidas) | (tasa de impuesto de alimentos y bebidas) | screens/FolioView.tsx |
| + New Extra folio | + Nuevo Folio Extra | + Nuevo folio de extras | screens/FolioView.tsx |
| - write off part of the bill, with a reason | - cancela parte de la cuenta, con un motivo | — bonificar parte de la cuenta, indicando el motivo | screens/FolioView.tsx |
| 300 pax sangeet, veg buffet, DJ till 1am, green room for the bride… | Sangeet para 300 personas, buffet de verduras, DJ hasta la 1 de la madrugada, salón verde para la novia… | Sangeet para 300 personas, buffet vegetariano, DJ hasta la 1 a. m., camerino para la novia… | screens/Banquet.tsx |
| A dot means a season or busy-house rule moved it. Select a night to see which. | Un punto significa que una temporada o una regla de ajetreo lo movió. Seleccione una noche para ver cuál. | Un punto indica que una temporada o una regla de alta ocupación modificó la tarifa. Seleccione una noche para ver cuál se aplicó. | screens/RateCalendar.tsx |
| A kitchen screen is printing for it | Una pantalla de cocina está imprimiendo para ello | Una pantalla de cocina está asignada para imprimir en esta impresora | screens/KitchenPrinters.tsx; screens/settings/cards.tsx |
| A refundable security deposit of {amount} may be collected separately. | Es posible que se cobre por separado un depósito de seguridad reembolsable de {amount}. | Es posible que se cobre por separado un depósito de garantía reembolsable de {amount}. | screens/PublicBooking.tsx |
| A supervisor passes the inspection | Un supervisor pasa la inspección | Un supervisor aprueba la inspección | screens/HkApp.tsx |
| A walk-in arrives today | Hoy llega un walk-in | Un huésped sin reserva previa llega hoy | components/BookingDialog.tsx |
| Acknowledged by {who} at {when}: {why} | Reconocido por {who} en {when}: {why} | Revisado por {who}, {when}: {why} | screens/EndOfDayWizard.tsx |
| Add guests and their IDs | Agregar invitados y sus ID | Agregar huéspedes y sus documentos de identidad | components/CheckInDialog.tsx |
| Add listing | Agregar listado | Agregar alojamiento | screens/Setup.tsx |
| Add rate | Agregar tasa | Agregar tarifa | screens/Laundry.tsx |
| Address proof on file | Comprobante de dirección en el archivo | Comprobante de domicilio guardado | components/GuestDocuments.tsx |
| Advance bill | cuenta anticipada | Facturar por adelantado | screens/FolioView.tsx |
| Advance percent | Porcentaje de avance | Porcentaje de anticipo | screens/Setup.tsx |
| Advance Percent | Porcentaje de avance | Porcentaje de anticipo | screens/Setup.tsx |
| Agreed charge / night, all of them | Cargo/noche pactado, todos | Cargo por noche acordado para todos los huéspedes adicionales | components/BookingDialog.tsx |
| AI assistant (bring your own key) | Asistente de IA (traiga su propia llave) | Asistente de IA (use su propia clave API) | screens/settings/cards.tsx |
| Airport drop | Entrega en el aeropuerto | Traslado al aeropuerto | components/CheckInDialog.tsx |
| All functions | Todas las funciones | Todos los eventos | screens/Banquet.tsx |
| All payment modes | Todos los modos de pago | Todos los medios de pago | screens/pos/OrderHistory.tsx |
| All properties, including ones added later | Todas las alojamientos, incluidas las agregadas posteriormente | Todos los alojamientos, incluidos los que se agreguen después | screens/settings/AccessPages.tsx |
| All ready - send to pass | Todo listo - enviar para pasar | Todo listo: enviar al pase de cocina | screens/Kitchen.tsx |
| All types (upgrade) | Todos los tipos (actualización) | Todos los tipos (mejora de categoría) | components/RoomChangeDialog.tsx |
| Allowance | Asignación | Bonificación | screens/VoidAllowanceReport.tsx |
| Always required | Siempre requerido | Siempre obligatorio | screens/settings/cards.tsx |
| Amount | Cantidad | Importe | components/CheckOutDialog.tsx; components/DepositPanel.tsx; components/RoomStayPanels.tsx; components/SecurityDepositPanel.tsx; screens/CashierTill.tsx; screens/PettyCash.tsx; screens/pos/OrderHistory.tsx; screens/pos/PosSidePanel.tsx |
| Amount (held {amt}) | Cantidad (retenida {amt}) | Importe (retenido: {amt}) | components/SecurityDepositPanel.tsx |
| Amount collected | Monto recaudado | Importe cobrado | components/BookingDialog.tsx |
| Amount to bank | Importe al banco | Importe a depositar en el banco | screens/CashierBoard.tsx |
| Amount {cur} | Cantidad {cur} | Importe {cur} | screens/FolioView.tsx; screens/HkApp.tsx |
| Amounts are inclusive of GST at the rates shown. | Los montos incluyen el GST a las tarifas que se muestran. | Los importes incluyen el GST con las tasas indicadas. | screens/FolioView.tsx |
| An alert on screen when a booking, ticket or laundry order comes in. | Una alerta en pantalla cuando llega una reserva, un ticket o un pedido de lavandería. | Una alerta en pantalla al recibir una reserva, una solicitud de servicio o una orden de lavandería. | components/AlertSettings.tsx |
| and take UPI, cards and netbanking for advances and bills. | y toma UPI, tarjetas y netbanking para adelantos y cuentas. | y acepte UPI, tarjetas y banca en línea para cobrar anticipos y cuentas. | screens/settings/cards.tsx |
| Anything unusual (a split, an allowance, a correction)? Open the folio, then come back here. | ¿Algo inusual (una división, una asignación, una corrección)? Abra el folio y luego regrese aquí. | ¿Hay algo que revisar, como una división de cargos, una bonificación o una corrección? Abra el folio y después vuelva aquí. | components/CheckOutDialog.tsx |
| Arabic switches the interface to right-to-left | El árabe cambia la interfaz a de derecha a izquierda | El árabe muestra la interfaz de derecha a izquierda | screens/settings/cards.tsx |
| Arr | Llegada | Lleg. | screens/Dashboard.tsx; screens/Rooms.tsx |
| Arr = arriving today | Llegada = llegando hoy | Lleg. = llegada prevista para hoy | screens/Rooms.tsx |
| Arriving today | Llegando hoy | Llegadas de hoy | components/RoomDrawer.tsx; screens/Rooms.tsx |
| Ask if they need anything: an extra bed, a wake-up call, an airport drop. | Pregunte si necesitan algo: una cama extra, una llamada de atención, un traslado al aeropuerto. | Pregunte si necesitan algún servicio: una cama adicional, una llamada de despertador o un traslado al aeropuerto. | components/CheckInDialog.tsx |
| Assigned by {who} at {when} | Asignado por {who} en {when} | Asignado por {who}, {when} | components/CheckInDialog.tsx |
| Assigned by {who} on {when} | Asignado por {who} en {when} | Asignado por {who}, {when} | screens/Tickets.tsx |
| At this outlet before | Antes en este punto de venta | Historial en este punto de venta | screens/pos/PosSidePanel.tsx |
| Auto-assign arrivals | Asignación automática de llegadas | Asignar habitaciones automáticamente | screens/TapeChart.tsx |
| Auto-detect format | Formato de detección automática | Detectar formato automáticamente | screens/GoLiveImport.tsx |
| Available | Disponible | Disponibles | screens/HkApp.tsx |
| Available ({n}) | Disponible ({n}) | Disponibles ({n}) | screens/POS.tsx |
| Available{n} | Disponible{n} | Disponibles{n} | screens/HkApp.tsx |
| Average clean | Limpieza promedio | Tiempo medio de limpieza | components/RoomInsights.tsx |
| Avg clean | Limpieza promedio | Tiempo medio de limpieza | components/RoomInsights.tsx |
| Back on (first night it can be sold) | De nuevo (la primera noche se puede vender) | Disponible de nuevo (primera noche que se puede reservar) | components/RoomDrawer.tsx |
| Bag is back: mark ready | La bolsa está de vuelta: marca lista | Prendas devueltas: marcar como listas | components/CheckOutDialog.tsx |
| Balance {cur} | Balanza {cur} | Saldo {cur} | screens/Billing.tsx |
| Bank it | Depositar en caja central | Depositar en el banco | screens/CashierBoard.tsx |
| Bench | Banco | Bench | screens/SystemHealth.tsx |
| Bill actions | Acciones de cuenta | Acciones de la cuenta | screens/POS.tsx |
| Bill {total} · paid {paid} | cuenta {total} · pagado {paid} | Cuenta: {total} · pagado: {paid} | components/RoomStayPanels.tsx |
| Bill, KOT, table, room, name or phone | cuenta, KOT, mesa, habitación, nombre o teléfono | Cuenta, comanda, mesa, habitación, nombre o teléfono | screens/pos/OrderHistory.tsx; screens/pos/PosSidePanel.tsx |
| Bills | cuentas | Cuentas | screens/pos/OrderHistory.tsx |
| Bills and receipts | cuentas y recibos | Cuentas y recibos | screens/KitchenPrinters.tsx |
| Bills here: {n} | cuentas aquí: {n} | Cuentas en este punto de venta: {n} | screens/pos/PosSidePanel.tsx |
| Book | Libro | Reservar | screens/CRS.tsx |
| Book {type} | Libro {type} | Reservar {type} | screens/CRS.tsx |
| booked, not posted yet | Reservado, aún no registrado | Reservado, aún sin cargar al folio | components/RoomDrawer.tsx |
| Booking Payment Mode | Modo de pago de reserva | Medio de pago de la reserva | screens/Setup.tsx |
| Bring bookings, companies and opening balances over from your old system, then reconcile before you switch. | Traiga reservas, empresas y saldos de apertura desde su sistema anterior, luego concilie antes de cambiar. | Importe las reservas, las empresas y los saldos iniciales de su sistema anterior; después concilie los datos antes de empezar a operar. | screens/GoLiveImport.tsx |
| Business date {bd} · property time {now} | fecha operativa {bd} · hora de propiedad {now} | Fecha operativa: {bd} · hora del alojamiento: {now} | screens/EndOfDay.tsx |
| Business date {d} | fecha operativa {d} | Fecha operativa: {d} | screens/AuditPack.tsx |
| Busy house | Casa ocupada | Alta ocupación | screens/RateCalendar.tsx |
| Busy house {p}% | Casa ocupada {p}% | Alta ocupación: {p}% | components/RateOptions.tsx |
| By hall | Por pasillo | Por salón | screens/Banquet.tsx |
| By property | Por propiedad | Por alojamiento | screens/Dashboard.tsx |
| Came back? | ¿Volvió? | ¿El problema volvió a presentarse? | screens/Tickets.tsx |
| Cancel bill | Cancelar cuenta | Anular cuenta | screens/POS.tsx |
| Cancel invoice | Cancelar factura | Anular factura | screens/FolioView.tsx |
| Cancel this bill | Cancelar esta cuenta | Anular esta cuenta | screens/POS.tsx |
| Cancel {invoice}? The number goes on the cancelled register and the folio reopens for correction. | ¿Cancelar {invoice}? El número pasa al registro cancelado y se vuelve a abrir el folio para su corrección. | ¿Anular la factura {invoice}? El número quedará en el registro de facturas anuladas y el folio se volverá a abrir para corregirlo. | screens/FolioView.tsx |
| Capture | Captura | Capturar | screens/RegistrationCard.tsx |
| Card slip / transfer ref (optional) | Ref. de recibo/transferencia de tarjeta (opcional) | Comprobante de tarjeta o referencia de transferencia (opcional) | components/BookingDialog.tsx; components/DepositPanel.tsx; components/SecurityDepositPanel.tsx |
| carried | llevado | del día anterior | screens/pos/PosSidePanel.tsx |
| carried over | transferido | del día anterior | screens/pos/OrderHistory.tsx |
| Carried over | Transferido | Pendiente del día anterior | screens/GoLiveImport.tsx |
| Cash drop | Retiro de efectivo | Entrega de efectivo a caja central | screens/CashierTill.tsx |
| Cash in | Efectivo en | Entradas de efectivo | screens/CashierTill.tsx |
| Cashier PIN required for money actions. | Se requiere PIN de cajero para acciones de dinero. | Se requiere el PIN del cajero para realizar operaciones de cobro y caja. | screens/FolioView.tsx |
| Cashier total | Cajero total | Total del cajero | screens/AuditPack.tsx |
| Cashier unlocked - money actions are open for {n} minutes. | Cajero desbloqueado: las acciones de dinero están abiertas durante {n} minutos. | Caja desbloqueada: las operaciones de cobro y caja estarán habilitadas durante {n} minutos. | screens/FolioView.tsx |
| CHANGEOVER CONFLICT | CONFLICTO DE CAMBIO | CONFLICTO ENTRE SALIDA Y ENTRADA | screens/TapeChart.tsx |
| Checked in | Comprobado en | Entrada registrada | screens/TapeChart.tsx |
| Checked in · Room {n} | Registrado en · Habitación {n} | Entrada registrada · Habitación {n} | components/BookingDialog.tsx |
| Checked out with a company credit warning | Saldo con una advertencia de crédito de la empresa | Salida registrada con advertencia de crédito de la empresa | components/CheckOutDialog.tsx |
| Checks | Cheques | Comprobaciones | screens/SystemHealth.tsx |
| Choose a housekeeper… | Elige un ama de llaves... | Seleccione a un miembro del personal de limpieza… | screens/HousekeepingBoard.tsx |
| Clean | Limpiar | Limpia | screens/Dashboard.tsx; screens/Rooms.tsx; screens/Today.tsx |
| Cleaned by {who}, {when} | Limpiado por {who}, {when} | Limpieza realizada por {who}, {when} | components/RoomDrawer.tsx |
| Clear | Transparente | Borrar | components/ResourceScreen.tsx; screens/FolioView.tsx |
| Clear new | Borrar nuevo | Borrar novedades | screens/POS.tsx |
| Closed over or short by more than the allowed variance. | Cerrado por encima o por debajo de la variación permitida. | La caja se cerró con un sobrante o faltante superior a la diferencia permitida. | screens/CashierBoard.tsx |
| Collect & count | Recoger y contar | Recoger y contar prendas | screens/Laundry.tsx |
| Collect a payment on Front Desk (Today / reservation) or close a restaurant bill - they appear here while the till is open. | Cobrar un pago en recepción (hoy/reserva) o cerrar la cuenta de un restaurante: aparecen aquí mientras la caja está abierta. | Registre un cobro en Recepción (Hoy o una reserva) o cierre una cuenta de restaurante. Los movimientos aparecerán aquí mientras la caja esté abierta. | screens/CashierTill.tsx |
| Collect deposit | Recoger depósito | Cobrar depósito de garantía | components/SecurityDepositPanel.tsx |
| Collect more | Colecciona más | Cobrar un importe adicional | components/SecurityDepositPanel.tsx |
| Collect {amount} | Recoger {amount} | Cobrar {amount} | components/CheckOutDialog.tsx |
| Collect {amt} | Recoger {amt} | Cobrar {amt} | components/SecurityDepositPanel.tsx |
| Collect {n} piece{s} · {total} | Recoger {n} pieza{s} · {total} | Recoger {n} prenda{s} · {total} | screens/Laundry.tsx |
| Collected | Recogido | Cobrado | screens/Dashboard.tsx |
| Collected today | Recogido hoy | Cobrado hoy | screens/Dashboard.tsx |
| collected {n} | recogido {n} | prendas recogidas: {n} | screens/Laundry.tsx |
| Collections | Colecciones | Cobros | screens/Dashboard.tsx; screens/Reports.tsx |
| Collections by mode | Colecciones por modo | Cobros por medio de pago | screens/AuditPack.tsx |
| comp | comp. | cortesía | screens/Laundry.tsx |
| Company bill | cuenta de la empresa | Cuenta de la empresa | components/CheckOutDialog.tsx |
| complimentary | gratuito | de cortesía | components/CheckOutDialog.tsx |
| COMPLIMENTARY | GRATIS | DE CORTESÍA | screens/POS.tsx |
| Confirm cancel | Confirmar cancelar | Confirmar cancelación | screens/FolioView.tsx |
| COOKING | COCINAR | EN PREPARACIÓN | screens/Kitchen.tsx |
| Coordinated by {brand} | Administrado por {brand} | Coordinado por {brand} | screens/PublicListing.tsx |
| copy check-in link | copiar enlace de registro | copiar enlace de registro de entrada | screens/Today.tsx |
| Copy the self check-in link - send to the booker, {name}{phone} | Copie el enlace de llegada autónoma y envíelo al responsable de la reserva, {name}{phone} | Copie el enlace de registro de entrada en línea y envíelo al responsable de la reserva, {name}{phone} | screens/Today.tsx |
| Copy the self check-in link - send to the guest | Copie el enlace de llegada autónoma y envíelo al huésped | Copie el enlace de registro de entrada en línea y envíelo al huésped | screens/Today.tsx |
| Copy the self check-in link - send to the guest and the booker ({name}) | Copie el enlace de llegada autónoma y envíelo al huésped y al responsable de la reserva ({name}) | Copie el enlace de registro de entrada en línea y envíelo al huésped y al responsable de la reserva ({name}) | screens/Today.tsx |
| Count the bag | Cuenta la bolsa | Contar las prendas de la bolsa | screens/Laundry.tsx |
| Create ticket | Crear ticket | Crear solicitud de servicio | screens/Tickets.tsx |
| Creating sets this as your active property. Rates, seasons, vouchers and guardrails can be added later from Revenue. | La creación establece esto como su propiedad activa. Las tarifas, temporadas, vales y barreras de seguridad se pueden agregar más adelante desde Ingresos. | Al crear el alojamiento, quedará seleccionado como activo. Después podrá configurar tarifas, temporadas, cupones y límites de precio en Ingresos. | screens/Setup.tsx |
| Credit terms at this property | Términos de crédito en esta propiedad | Condiciones de crédito en este alojamiento | components/CreditTermsEditor.tsx |
| Customer, company, hall… | Cliente, empresa, hall… | Cliente, empresa, salón… | screens/Banquet.tsx |
| Customize Today | Personalizar hoy | Personalizar Hoy | components/CustomizeToday.tsx |
| Date changes re-price automatically (unless the booking holds a manual amount) and the double-booking guard re-checks the room. | Los cambios de fecha vuelven a fijar el precio automáticamente (a menos que la reserva contenga un importe manual) y el guardia de doble reserva vuelve a comprobar la habitación. | Al cambiar las fechas, la tarifa se recalcula automáticamente, salvo que la reserva tenga un importe manual. El sistema vuelve a comprobar que la habitación no tenga otra reserva para esas fechas. | screens/TapeChart.tsx |
| Day and month to date | Día y mes hasta la fecha | Día y acumulado del mes | screens/AuditPack.tsx |
| Day use · out {time} | Uso diurno · fuera {time} | Uso diurno · salida: {time} | screens/HousekeepingBoard.tsx |
| Default opening float | Flotador de apertura por defecto | Fondo inicial de caja predeterminado | screens/CashierBoard.tsx |
| Demo accounts - one tap to try each role | Cuentas de demostración: un toque para probar cada función | Cuentas de demostración: un toque para probar cada rol | screens/Login.tsx |
| Dep | Depósito | Sal. | screens/Dashboard.tsx; screens/Rooms.tsx |
| Dep = leaving today | Dep = sale hoy | Sal. = salida prevista para hoy | screens/Rooms.tsx |
| Departing today | Saliendo hoy | Salidas de hoy | components/RoomDrawer.tsx; screens/Rooms.tsx |
| Deposit | Depósito | Anticipo de reserva | components/DepositPanel.tsx |
| Deposit and advance | Depósito y anticipo | Depósito de garantía y anticipo | components/CheckInDialog.tsx; screens/settings/cards.tsx |
| Deposit held | Depósito retenido | Depósito de garantía retenido | screens/RegistrationCard.tsx |
| Detach profile | Perfil de separación | Desvincular perfil | components/BookingDialog.tsx |
| Diary | Diario | Agenda | screens/Banquet.tsx |
| Differs from folios by {amount} | Se diferencia de los folios de {amount} | Hay una diferencia de {amount} respecto a los folios | screens/AuditPack.tsx |
| Dirty | Sucio | Sucia | screens/Dashboard.tsx; screens/Rooms.tsx; screens/Today.tsx |
| Docket | Expediente | Comprobante de lavandería | screens/Laundry.tsx |
| Done by {who} at {when} | Hecho por {who} en {when} | Completado por {who}, {when} | components/CheckInDialog.tsx |
| Drop to safe | Bajar a la caja fuerte | Entregar efectivo a caja central | screens/CashierTill.tsx |
| Drops | Gotas | Entregas de efectivo | screens/CashierShiftReport.tsx; screens/CashierTill.tsx |
| due | debido a | pendiente de pago | screens/Banquet.tsx; screens/Today.tsx |
| Due | Vencimiento | Pendiente de pago | screens/Banquet.tsx; screens/Today.tsx |
| Due out | Vencimiento | Salida prevista para hoy | screens/HousekeepingBoard.tsx |
| Each hotel / branch keeps its own float and voucher list. Changing property in the header switches the box. | Cada hotel/sucursal mantiene su propia lista flotante y de cupones. Cambiar la propiedad en el encabezado cambia el cuadro. | Cada hotel o sucursal tiene su propio fondo de caja chica y sus vales. Al cambiar de alojamiento en el encabezado, se cambia también de caja chica. | screens/PettyCash.tsx |
| Each unit / room sells on its own (hotel-style inventory). | Cada unidad/habitación se vende por sí sola (inventario estilo hotel). | Cada unidad o habitación se reserva por separado, como en un hotel. | screens/Setup.tsx |
| End of Day for {bd} is complete. | El fin del día para {bd} está completo. | Se completó el cierre del día {bd}. | screens/EndOfDayWizard.tsx |
| End of Day is the night audit. Close each property's business date: work through the checklist, post room and tax, roll the date and print the audit pack. The 3 AM job runs the same steps on its own. | El cierre del día corresponde a la auditoría nocturna. Cierre la fecha operativa de cada alojamiento: complete la lista de verificación, registre los cargos de habitación e impuestos, avance la fecha e imprima el informe de auditoría. El proceso de las 3 a. m. realiza los mismos pasos automáticamente. | El cierre del día corresponde a la auditoría nocturna. Cierre la fecha operativa de cada alojamiento: complete la lista de verificación, registre los cargos de habitación e impuestos, avance la fecha e imprima el paquete de auditoría. El proceso de las 3 a. m. realiza los mismos pasos automáticamente. | screens/EndOfDay.tsx |
| End of Day walks the night audit checklist, posts room and tax, rolls the business date and prints the audit pack. Runs automatically at 3 AM. | El cierre del día recorre la lista de verificación de auditoría nocturna, registra los cargos de habitación e impuestos, avanza la fecha operativa e imprime el informe de auditoría. Se ejecuta automáticamente a las 3 a. m. | El cierre del día recorre la lista de verificación de auditoría nocturna, registra los cargos de habitación e impuestos, avanza la fecha operativa e imprime el paquete de auditoría. Se ejecuta automáticamente a las 3 a. m. | screens/Billing.tsx |
| Endpoint URL (HTTPS) | URL de punto final (HTTPS) | URL del endpoint (HTTPS) | screens/settings/WebhooksPage.tsx |
| Endpoints | Puntos finales | Endpoints | screens/settings/WebhooksPage.tsx |
| Ends | Extremos | Fecha de finalización | screens/Banquet.tsx |
| Enquiries and tentative holds | Consultas y retenciones provisionales | Consultas y bloqueos provisionales | screens/Banquet.tsx |
| Enter 1-99%, or a {cur} amount under the line's {cur}{amount} (before {tax}). | Ingrese 1-99%, o un monto {cur} bajo {cur}{amount} de la línea (antes de {tax}). | Ingrese un porcentaje entre 1 y 99 %, o un importe en {cur} inferior al total de la línea ({cur}{amount}, antes de {tax}). | screens/FolioView.tsx |
| Entire place | Lugar completo | Alojamiento completo | screens/Setup.tsx |
| Entire place or a few units. No meal plans; overbooking off by default. | Lugar completo o algunas unidades. Sin planes de alimentación; overbooking desactivado de forma predeterminada. | Alojamiento completo o varias unidades. Sin planes de comidas y con la sobreventa desactivada de forma predeterminada. | screens/Setup.tsx |
| Every action on the property, newest first - who did it and what changed. | Cada acción en la propiedad, la más reciente primero: quién la realizó y qué cambió. | Todas las acciones del alojamiento, de la más reciente a la más antigua: quién las realizó y qué cambió. | screens/Agents.tsx |
| Every file ties to Kamra as of business date {date}. Switch the desk over. | Cada archivo está vinculado a Kamra a partir de la fecha operativa {date}. Cambia el escritorio. | Todos los archivos coinciden con Kamra para la fecha operativa {date}. Ya puede empezar a operar la recepción en Kamra. | screens/GoLiveImport.tsx |
| Every guest, their stays and lifetime value. Click for the full journey. | Cada huésped, sus estadías y su valor de por vida. Haga clic para ver el viaje completo. | Consulte los huéspedes, sus estancias y su gasto acumulado. Haga clic para ver el historial completo. | screens/Guests.tsx |
| Every void, allowance and cancelled invoice: who, when and why. | Cada factura anulada, amortizada y cancelada: quién, cuándo y por qué. | Todas las anulaciones, bonificaciones y facturas anuladas: quién las realizó, cuándo y por qué. | screens/VoidAllowanceReport.tsx |
| Everyone staying | Todos se quedan | Todas las personas alojadas | components/CheckInDialog.tsx |
| Expected pax | Pax esperado | Número de asistentes previsto | screens/Banquet.tsx |
| Extend stay | Extender el soporte | Extender estancia | screens/EndOfDayWizard.tsx |
| Extra bed | Cama supletoria | Cama adicional | components/CheckInDialog.tsx |
| Extra beds | Camas supletorias | Camas adicionales | components/RoomDrawer.tsx |
| Extra guest price / night | Precio huésped adicional/noche | Tarifa por huésped adicional y por noche | screens/Setup.tsx |
| Extra guests | Invitados adicionales | Huéspedes adicionales | components/BookingDialog.tsx |
| Extra guests by arrangement - up to {beds} above the {cap} it sleeps, at a price you agree | Invitados adicionales según acuerdo: hasta {beds} por encima del {cap} con capacidad para dormir, a un precio que usted acuerde | Huéspedes adicionales sujetos a acuerdo: hasta {beds} personas por encima de la capacidad de {cap}, con una tarifa acordada | components/BookingDialog.tsx |
| Fewer keys | Menos claves | Menos llaves | components/CheckInDialog.tsx |
| File rows | Archivo de filas | Filas del archivo | screens/GoLiveImport.tsx |
| File total | Archivo total | Total del archivo | screens/GoLiveImport.tsx |
| Filter rooms | Salas de filtrado | Filtrar habitaciones | screens/HousekeepingBoard.tsx |
| Find a room across every property you manage, and book into whichever has space. | Encuentre una habitación en cada propiedad que administre y reserve en la que tenga espacio. | Busque habitaciones en todos los alojamientos que administra y reserve donde haya disponibilidad. | screens/CRS.tsx |
| Find it under Arrivals on the stay date. | Encuéntrelo en Llegadas en la fecha de estancia. | Encontrará la reserva en Llegadas para la fecha de entrada. | components/BookingDialog.tsx |
| Finish | Acabado | Finalizar | components/CheckOutDialog.tsx |
| Finish setting up: {done} of {total} done. | Finalice la configuración: {done} de {total} hecho. | Complete la configuración: {done} de {total} pasos completados. | components/SetupNag.tsx |
| Fire | Fuego | Enviar a preparación | screens/Kitchen.tsx |
| Fire {course} | Fuego {course} | Enviar {course} a preparación | screens/Kitchen.tsx |
| Fired | Despedido | Enviado a preparación | screens/Kitchen.tsx |
| Float | Flotador | Fondo de caja | screens/CashierShiftReport.tsx; screens/CashierTill.tsx |
| Food & beverage is taxed at the property's F&B rate. | Los alimentos y bebidas están sujetos a impuestos según la tarifa de alimentos y bebidas del establecimiento. | Los alimentos y bebidas tributan según la tasa de impuesto configurada para alimentos y bebidas en el alojamiento. | screens/FolioView.tsx |
| Free | Gratis | Disponible | components/RoomDrawer.tsx |
| Free Child Age Limit (Years) | Límite de edad gratuito para niños (años) | Edad máxima para alojamiento infantil sin cargo (años) | screens/Setup.tsx |
| from {date} | de {date} | desde {date} | components/RoomDrawer.tsx |
| from {n} timed cleans | de {n} limpiezas programadas | a partir de {n} limpiezas con duración registrada | components/RoomInsights.tsx |
| Front Desk Overview | Descripción general de la recepción | Resumen de recepción | screens/Today.tsx |
| Function prospecting through to the event order - enquiry, quotation, contract, and the day itself. | Función de prospección hasta el pedido del evento: consulta, cotización, contrato y el día mismo. | Gestione los eventos desde la consulta inicial hasta la orden de servicio: consulta, cotización, contrato y operación el día del evento. | screens/Banquet.tsx |
| Go-live import | Importación de entrada en funcionamiento | Importación para puesta en marcha | screens/GoLiveImport.tsx |
| Good to know | Es bueno saberlo | Información útil | components/CheckInDialog.tsx |
| Group account pays | La cuenta grupal paga | A cargo de la cuenta del grupo | components/CheckInDialog.tsx |
| Group bill | cuenta de grupo | Cuenta del grupo | components/CheckOutDialog.tsx |
| Guest and IDs | huésped e ID | Huésped y documentos de identidad | components/CheckInDialog.tsx; screens/settings/cards.tsx |
| Guest conversations on your own number - confirmations go out automatically, replies land here and on the desk queue. | Conversaciones de huéspedes en su propio número: las confirmaciones se envían automáticamente, las respuestas llegan aquí y en la cola del escritorio. | Conversaciones con huéspedes desde su propio número. Las confirmaciones se envían automáticamente y las respuestas aparecen aquí y en la bandeja de recepción. | screens/WhatsAppChat.tsx |
| Guest moment | Momento del huésped | Atención al huésped | components/CheckOutDialog.tsx |
| Guest only | Solo huéspedes | Solo el huésped | components/CheckOutDialog.tsx |
| Guest or customer | huésped o cliente | Huésped o cliente | screens/pos/OrderHistory.tsx |
| GUEST REGISTRATION CARD | TARJETA DE REGISTRO DE HUÉSPEDES | FICHA DE REGISTRO DE HUÉSPEDES | screens/RegistrationCard.tsx |
| Guest request - SLA starts from priority at creation | Solicitud de huésped: el SLA comienza desde la prioridad en el momento de la creación | Solicitud de huésped: el plazo de atención (SLA) se calcula según la prioridad al crearla | screens/Tickets.tsx |
| Guest requests with deadlines by priority - set them in Settings → Operations | Solicitudes de huéspedes con fechas límite por prioridad: configúrelas en Configuración → Operaciones | Solicitudes de huéspedes con plazos de atención según la prioridad. Configúrelos en Configuración → Operaciones | screens/Tickets.tsx |
| Guest told by {via}. | huésped contado por {via}. | Se informó al huésped por {via}. | components/BookingRequests.tsx |
| Guests need a mobile number on their profile to receive a Cashfree link. | Los invitados necesitan un número de móvil en su perfil para recibir un enlace Cashfree. | Los huéspedes deben tener un número de celular en su perfil para recibir un enlace de Cashfree. | screens/settings/cards.tsx |
| Have the guest sign on screen, or tick that they signed the printed card. | Haga que el huésped firme en la pantalla o marque que firmó en la tarjeta impresa. | Solicite al huésped que firme en pantalla o marque que firmó la ficha impresa. | components/CheckInDialog.tsx |
| held | retenido | en espera | screens/Kitchen.tsx |
| HELD | RETENIDO | EN ESPERA | screens/Kitchen.tsx |
| Held (house use / VIP / maintenance) | Retenido (uso doméstico / VIP / mantenimiento) | Bloqueada (uso interno / VIP / mantenimiento) | screens/TapeChart.tsx |
| Held / out of service | Retenido/fuera de servicio | Bloqueada / fuera de servicio | components/RoomDrawer.tsx |
| Held late arrivals | Llegadas tardías retenidas | Reservas mantenidas por llegada tardía | screens/AuditPack.tsx |
| History | Historia | Historial | components/RoomDrawer.tsx |
| Hold bill | Retener cuenta | Dejar cuenta pendiente | screens/POS.tsx |
| Holds also show on the Tape Chart and in | Las retenciones también se muestran en el gráfico de cintas y en | Los bloqueos también se muestran en el calendario de ocupación y en | components/RoomDrawer.tsx |
| house | casa | uso interno | screens/Laundry.tsx |
| House (uniforms / linen) | Casa (uniformes / lencería) | Uso interno (uniformes / ropa de cama) | screens/Laundry.tsx |
| Housekeeping: mark {to} | Limpieza: marca {to} | Limpieza: marcar como {to} | screens/Today.tsx |
| How do guests book this property? This sets Sellable Units and competition groups - not a separate product fork. | ¿Cómo reservan los huéspedes esta propiedad? Esto establece Unidades Vendibles y grupos de competencia, no una bifurcación de producto separada. | ¿Cómo reservan los huéspedes este alojamiento? Esta opción define las unidades que se pueden reservar y qué unidades comparten disponibilidad dentro del mismo producto. | screens/Setup.tsx |
| How to clear this | Cómo borrar este | Cómo resolverlo | screens/EndOfDayWizard.tsx |
| I understand and want to book this guest anyway | Entiendo y quiero reservar a este huésped de todos modos | Entiendo y deseo crear la reserva para este huésped de todos modos | components/BookingDialog.tsx |
| I use a channel manager (OTA bookings) | Utilizo un administrador de canales (reservas OTA) | Utilizo un gestor de canales (reservas de agencias en línea) | screens/Setup.tsx |
| ID missing | Falta ID | Falta el documento de identidad | components/CheckInDialog.tsx |
| ID on file | ID en el archivo | Documento de identidad guardado | components/CheckInDialog.tsx; components/GuestDocuments.tsx |
| ID proof | Prueba de identificación | Documento de identidad | components/GuestDocuments.tsx |
| ID scan | Escaneo de identificación | Imagen del documento de identidad | components/GuestDocuments.tsx |
| ID still needed for: {names}. | Aún se necesita ID para: {names}. | Falta el documento de identidad de: {names}. | components/CheckInDialog.tsx |
| If you override: | Si anula: | Si autoriza la excepción: | screens/EndOfDayWizard.tsx |
| Imprest (this property) | Imprest (esta propiedad) | Fondo fijo de caja chica (este alojamiento) | screens/PettyCash.tsx |
| Imprest for this property | Anticipo para esta propiedad | Fondo fijo de caja chica de este alojamiento | screens/PettyCash.tsx |
| In hand | En la mano | Efectivo disponible | screens/Laundry.tsx |
| in house | en casa | alojado | components/RoomDrawer.tsx |
| In house | En casa | Huéspedes alojados | screens/Dashboard.tsx |
| in house, room {n} | en casa, habitación {n} | alojado, habitación {n} | screens/pos/PosSidePanel.tsx |
| In kitchen / not settled | En cocina / no asentado | En cocina / pendiente de pago | screens/POS.tsx |
| in play | en juego | en negociación | screens/Banquet.tsx |
| In Razorpay, add a webhook for the payment_link.paid event pointing to | En Razorpay, agregue un webhook para el evento Payment_link.paid que apunte a | En Razorpay, agregue un webhook para el evento payment_link.paid que apunte a | screens/settings/cards.tsx |
| In-house | Interno | Alojados | screens/Dashboard.tsx; screens/Reports.tsx; screens/Today.tsx |
| In-house guest | huésped interno | Huésped alojado | screens/POS.tsx; screens/pos/PosSidePanel.tsx |
| In-house guests | Invitados internos | Huéspedes alojados | screens/Today.tsx |
| Inside the {days}-day window - the {basis} ({amount}) will be charged. | Dentro de la ventana del día {days}, se cargará el {basis} ({amount}). | Dentro del plazo de {days} días previo a la llegada, se cobrará {basis} ({amount}). | components/CancelPanel.tsx |
| Insights | Perspectivas | Estadísticas | screens/Rooms.tsx |
| Inspected | Inspeccionado | Inspeccionada | screens/Dashboard.tsx; screens/Rooms.tsx; screens/Today.tsx |
| Inspected by {who}, {when} | Inspeccionado por {who}, {when} | Inspeccionada por {who}, {when} | components/RoomDrawer.tsx |
| Invoice cancelled | Factura cancelada | Factura anulada | screens/VoidAllowanceReport.tsx |
| Invoices are issued once the guest is checked out. | Las facturas se emiten una vez que el huésped realiza el check out. | Las facturas se emiten después de registrar la salida del huésped. | components/CheckOutDialog.tsx |
| IT | ES | TI | screens/settings/SettingsHub.tsx |
| It opens the agent with this check described. You approve what it changes. | Abre el agente con este check descrito. Apruebas lo que cambia. | Abre el agente con la descripción de esta comprobación. Usted aprueba los cambios que realice. | screens/EndOfDayWizard.tsx |
| Item (Shirt…) | Artículo (Camisa…) | Prenda (camisa…) | screens/Laundry.tsx |
| Journal by kind / mode | Diario por tipo/modo | Diario por tipo y medio de pago | screens/CashierShiftReport.tsx |
| Kamra total | Kamra total | Total en Kamra | screens/GoLiveImport.tsx |
| Kamra Verify | Kamra Verificar | Kamra Verify | screens/settings/cards.tsx |
| Kamra Verify checks this tax ID with the tax network. Charged per check to your Kamra Connect wallet. | Kamra Verify verifica este ID fiscal con la red fiscal. Se cobra por cheque a su billetera Kamra Connect. | Kamra Verify comprueba esta identificación fiscal con la red tributaria. Cada verificación se cobra a su saldo de Kamra Connect. | screens/FolioView.tsx |
| Kamra Verify reads the ID and fills the profile. Charged per read to your Kamra Connect wallet. | Kamra Verify lee el documento de identidad y completa el perfil. Se cobra por cada lectura a la billetera de Kamra Connect. | Kamra Verify lee el documento de identidad y completa el perfil. Cada lectura se cobra a su saldo de Kamra Connect. | screens/RegistrationCard.tsx |
| Kamra will create a whole-property sellable unit for each listing. You can add physical rooms later for housekeeping if needed. | Kamra creará una unidad vendible para todo el alojamiento por cada anuncio. Si lo necesita, más adelante podrá agregar habitaciones físicas para la limpieza. | Kamra creará una unidad reservable de alojamiento completo por cada alojamiento publicado. Si lo necesita, después podrá agregar sus habitaciones físicas para gestionar la limpieza. | screens/Setup.tsx |
| Keep part of the security deposit ({held} held) against damage before refunding the rest. | Conserve parte del depósito de seguridad ({held} retenido) contra daños antes de reembolsar el resto. | Retenga del depósito de garantía la parte que corresponda a los daños ({held} retenidos) antes de reembolsar el resto. | components/CheckOutDialog.tsx |
| Keys | Teclas | Llaves | components/CheckInDialog.tsx; screens/settings/cards.tsx |
| Keys {range} · {all} all | Teclas {range} · {all} todos | Claves {range} · {all} en total | components/CheckOutDialog.tsx |
| Kitchen Display | Expositor de cocina | Pantalla de cocina | screens/KitchenPrinters.tsx |
| KOT | KOT | Comanda (KOT) | screens/POS.tsx |
| KOT printer off | Impresora KOT apagada | Impresión de comandas desactivada | screens/POS.tsx |
| KOT printer on | En | Impresión de comandas activada | screens/POS.tsx |
| KOT prints on send | KOT imprime en el envío | La comanda se imprime al enviarla | screens/POS.tsx |
| KOT {kot} is on the kitchen display. Turn on Print KOT to send it to the printer. | KOT {kot} está en la pantalla de la cocina. Active Imprimir KOT para enviarlo a la impresora. | La comanda {kot} aparece en la pantalla de cocina. Active «Imprimir comandas» para enviarla a la impresora. | screens/POS.tsx |
| KOT {kot} printed and on the kitchen display. | KOT {kot} impreso y en el expositor de la cocina. | La comanda {kot} se imprimió y aparece en la pantalla de cocina. | screens/POS.tsx |
| KOT {kot} sent to {printers}. | KOT {kot} enviado a {printers}. | Comanda {kot} enviada a {printers}. | screens/POS.tsx |
| KOT {n} | KOT {n} | Comanda {n} | screens/pos/PosSidePanel.tsx |
| Last closed {d} | Último cerrado {d} | Último cierre: {d} | screens/EndOfDay.tsx |
| Last printed {n} ticket(s) at {time} | Último billete impreso {n} en {time} | Última impresión: {n} comandas a las {time} | screens/Kitchen.tsx |
| Last {days} days | Últimos días {days} | Últimos {days} días | screens/Laundry.tsx |
| Last {n} days | Últimos días {n} | Últimos {n} días | components/RoomInsights.tsx |
| LATE | TARDE | CON RETRASO | screens/Kitchen.tsx |
| Leave off to share access yourself. | Déjelo para compartir el acceso usted mismo. | Deje esta opción desactivada si desea compartir el acceso personalmente. | screens/settings/AccessPages.tsx |
| Leave POS | Salir POS | Salir del punto de venta | screens/POS.tsx |
| Leaves {when} | Hojas {when} | Salida: {when} | screens/Today.tsx |
| Ledgers | Libros mayores | Libros contables | screens/CashierTill.tsx; screens/Reports.tsx |
| Lifetime {cur} | Vida útil {cur} | Gasto acumulado {cur} | screens/Guests.tsx |
| Light | Luz | Claro | screens/settings/cards.tsx |
| Listing code | Código de listado | Código del alojamiento | screens/Setup.tsx |
| Listing name | Nombre del listado | Nombre del alojamiento | screens/Setup.tsx |
| Live quote as you type | Cotización en vivo mientras escribe | La cotización se actualiza mientras escribe | components/BookingDialog.tsx |
| Live updates are not reaching this browser, so the kitchen display only refreshes every few seconds. Check that socket.io is running and proxied by the web server. | Las actualizaciones en vivo no llegan a este navegador, por lo que la pantalla de la cocina solo se actualiza cada pocos segundos. Compruebe que socket.io se esté ejecutando y que el servidor web esté utilizando como proxy. | Este navegador no recibe actualizaciones en tiempo real, por lo que la pantalla de cocina se actualiza cada pocos segundos. Compruebe que socket.io esté en ejecución y que el servidor web tenga configurado su proxy. | screens/settings/cards.tsx |
| Log it | Iniciar sesión | Registrar | screens/HkApp.tsx |
| Log pickup request | Solicitud de recogida de registros | Registrar solicitud de recogida | screens/Laundry.tsx |
| Maintenance and service tickets | Tickets de mantenimiento y servicio | Solicitudes de mantenimiento y servicio | components/RoomDrawer.tsx |
| Make this the hotel default | Establecer este como hotel predeterminado | Usar esta configuración como predeterminada del hotel | components/CustomizeToday.tsx |
| Manager flash | Administrador flash | Resumen gerencial | screens/Reports.tsx |
| Mark NC & close | Marcar NC y cerrar | Marcar de cortesía y cerrar | screens/pos/SettleSheet.tsx |
| Mark no-show | Marcar como ausencia | Marcar como no presentado | screens/EndOfDayWizard.tsx |
| Mark solved | Marca solucionado | Marcar como resuelto | screens/Tickets.tsx |
| Mark {status} | Marca {status} | Marcar como {status} | screens/HousekeepingBoard.tsx |
| Marketplace | Mercado | Catálogo de integraciones | screens/AppLauncher.tsx; screens/Marketplace.tsx |
| Matches | Coincidencias | Coincide | screens/GoLiveImport.tsx |
| Max guests (base) | Número máximo de invitados (base) | Capacidad base de huéspedes | screens/Setup.tsx |
| Module off | Módulo apagado | Módulo desactivado | screens/settings/SettingsHub.tsx |
| Module on | En | Módulo activado | screens/settings/SettingsHub.tsx |
| month to date | mes hasta la fecha | acumulado del mes | screens/Dashboard.tsx |
| Month to date | Mes hasta la fecha | Acumulado del mes | screens/AuditPack.tsx; screens/Reports.tsx |
| More keys | Más claves | Más llaves | components/CheckInDialog.tsx |
| Move it on | Muévelo | Avanzar al siguiente estado | screens/Tickets.tsx |
| move only | mover solo | solo trasladar | screens/FolioView.tsx |
| Move room | Mover habitación | Cambiar de habitación | components/RoomDrawer.tsx; screens/TapeChart.tsx |
| Move to another room | Mover a otra habitación | Cambiar a otra habitación | components/RoomDrawer.tsx |
| Move to {room} | Mover a {room} | Cambiar a la habitación {room} | components/RoomChangeDialog.tsx |
| Multiple rooms, optional F&B and events. Classic front-desk flow. | Múltiples salas, comidas y bebidas opcionales y eventos. Flujo clásico de recepción. | Varias habitaciones, con alimentos y bebidas y eventos opcionales. Operación habitual de recepción. | screens/Setup.tsx |
| Needs chasing{urgent} | Necesita persecución{urgent} | Requiere seguimiento{urgent} | screens/Banquet.tsx |
| Network round trip {ms} ms - fine. | Red de ida y vuelta {ms} ms: bien. | Tiempo de respuesta de la red: {ms} ms. Adecuado. | screens/settings/cards.tsx |
| Network round trip {ms} ms - slow. The server is far from the hotel or the connection is weak; every POS action waits this long. | Red de ida y vuelta {ms} ms: lento. El servidor está lejos del hotel o la conexión es débil; cada acción de POS espera este tiempo. | Tiempo de respuesta de la red: {ms} ms. Es lento. El servidor está lejos del hotel o la conexión es débil; cada acción del punto de venta tarda ese tiempo. | screens/settings/cards.tsx |
| New function enquiry | Consulta de nueva función | Nueva consulta para un evento | screens/Banquet.tsx |
| New service ticket {name} | Nuevo ticket de servicio {name} | Nueva solicitud de servicio {name} | components/NotificationHost.tsx |
| New ticket | Nuevo billete | Nueva solicitud de servicio | screens/Tickets.tsx |
| New {thing} | Nuevo {thing} | Crear {thing} | components/ResourceScreen.tsx |
| Next {n} days | Próximos días {n} | Próximos {n} días | components/RoomDrawer.tsx |
| No address proof | Sin prueba de dirección | Sin comprobante de domicilio | components/GuestDocuments.tsx |
| No arrival is booked into this room yet. | Aún no se ha reservado ninguna llegada a esta habitación. | Esta habitación aún no tiene una llegada asignada. | components/RoomDrawer.tsx |
| No bills match. | No hay billetes coincidentes. | Ninguna cuenta coincide con la búsqueda. | screens/pos/PosSidePanel.tsx |
| No busy-house rule applies ({p}% full). | No se aplica ninguna regla de estar ocupado ({p}% lleno). | No se aplica ninguna regla de alta ocupación ({p}% de ocupación). | screens/RateCalendar.tsx |
| No fee applied. | No se aplica ninguna tarifa. | No se aplica ningún cargo. | components/CancelPanel.tsx |
| No floor set | Sin juego de suelo | Sin piso asignado | screens/Rooms.tsx |
| No free room of this type for these dates. Try an upgrade to another type. | No hay habitaciones libres de este tipo para estas fechas. Pruebe una actualización a otro tipo. | No hay habitaciones disponibles de este tipo para estas fechas. Pruebe una mejora a otra categoría. | components/CheckInDialog.tsx |
| No free room tonight | No hay habitaciones libres esta noche | No hay habitaciones disponibles esta noche | components/BookingDialog.tsx |
| No functions in this window. | No hay funciones en esta ventana. | No hay eventos en este periodo. | screens/Banquet.tsx |
| No guest is checked in right now. Check the guest in first, or take payment above. | Ningún huésped está registrado en este momento. Registre al huésped primero o realice el pago arriba. | No hay un huésped con entrada registrada. Registre primero su entrada o cobre el pago en la sección anterior. | screens/pos/SettleSheet.tsx |
| No guest was moved into or out of this room. | Ningún huésped entró o salió de esta habitación. | No se han registrado traslados de huéspedes desde o hacia esta habitación. | components/RoomDrawer.tsx |
| No guests found. | No se encontraron invitados. | No se encontraron huéspedes. | screens/Guests.tsx |
| No guests in house | No hay invitados en la casa | No hay huéspedes alojados | screens/POS.tsx |
| No halls set up for this property yet - add one under Halls & Venues. | Aún no hay salas configuradas para esta propiedad; agregue una en Salas y lugares. | Este alojamiento aún no tiene salones configurados. Agregue uno en «Salones y espacios para eventos». | screens/Banquet.tsx |
| No ID on file | No hay ID en el archivo | No hay documento de identidad guardado | components/GuestDocuments.tsx |
| No ID proof | Sin prueba de identificación | Sin documento de identidad | components/GuestDocuments.tsx |
| No keys recorded. | No se registraron claves. | No hay llaves registradas. | components/CheckInDialog.tsx |
| No kitchen screen is printing for it right now | No se está imprimiendo ninguna pantalla de cocina en este momento | Ninguna pantalla de cocina está configurada para imprimir en esta impresora | screens/KitchenPrinters.tsx; screens/settings/cards.tsx |
| No laundry out right now. | No hay servicio de lavandería en este momento. | No hay prendas en lavandería en este momento. | screens/Laundry.tsx |
| No open tickets - a quiet day at the desk. | No hay entradas abiertas: un día tranquilo en el escritorio. | No hay solicitudes de servicio pendientes en recepción. | screens/Tickets.tsx |
| No open tickets. The kitchen is clear. | No hay entradas abiertas. La cocina está despejada. | No hay comandas pendientes en cocina. | screens/Kitchen.tsx |
| No other guests recorded. Add them on the registration card, then come back here. | No se registraron otros invitados. Agréguelos en la tarjeta de registro y luego regrese aquí. | No hay otros huéspedes registrados. Agréguelos en la ficha de registro y después vuelva aquí. | components/CheckInDialog.tsx |
| No petty cash vouchers for this property yet. Post one above - other hotels keep their own lists. | Aún no hay comprobantes de caja chica para este alojamiento. Registre uno arriba; cada hotel mantiene su propia lista. | Este alojamiento aún no tiene vales de caja chica. Registre uno en la sección anterior; cada hotel mantiene su propia lista. | screens/PettyCash.tsx |
| No rate card yet - add laundry rates in the Price menu tab. | Aún no hay hoja de tarifas: agregue tarifas de lavandería en la pestaña del menú Precio. | Aún no hay tarifas de lavandería. Agréguelas en la pestaña «Tarifario». | screens/Laundry.tsx |
| No room | Sin espacio | Sin habitación | screens/Tickets.tsx |
| No room yet | Aún no hay espacio | Sin habitación asignada | screens/Today.tsx |
| No rooms across the chain for these dates and party. | No hay habitaciones en toda la cadena para estas fechas y fiesta. | No hay habitaciones disponibles en la cadena para las fechas y el número de huéspedes indicados. | screens/CRS.tsx |
| No season or demand rule applies: every night is at BAR. | No aplica regla de temporada ni exigencia: todas las noches son en BAR. | No se aplica ninguna regla de temporada ni de demanda: todas las noches tienen la mejor tarifa disponible (BAR). | components/RateOptions.tsx |
| No sessions on this date. Open a till on My Till to start a shift. | No hay sesiones en esta fecha. Abra una caja en My Till para iniciar un turno. | No hay sesiones para esta fecha. Abra una caja en «Mi caja» para iniciar un turno. | screens/CashierShiftReport.tsx |
| No tables match. | Ninguna tabla coincide. | Ninguna mesa coincide con la búsqueda. | screens/POS.tsx |
| No terminals yet. Everyone works from the Default till, as before. | Aún no hay terminales. Todo el mundo trabaja desde el valor predeterminado caja, como antes. | Aún no hay terminales. Todos trabajan desde la caja predeterminada. | screens/CashierBoard.tsx |
| No tickets for this room. | No hay entradas para esta habitación. | No hay solicitudes de servicio para esta habitación. | components/RoomDrawer.tsx |
| No tickets match. | No hay entradas coincidentes. | Ninguna solicitud coincide con la búsqueda. | screens/Tickets.tsx |
| No timed cleans yet | Aún no hay limpiezas programadas | Aún no hay limpiezas con duración registrada | components/RoomInsights.tsx |
| No unassigned rooms right now. | No hay salas sin asignar en este momento. | No hay habitaciones sin asignar en este momento. | screens/HkApp.tsx |
| No voids, allowances or cancelled invoices in this window. | No hay anulaciones, bonificaciones ni facturas canceladas en esta ventana. | No hay anulaciones, bonificaciones ni facturas anuladas en este periodo. | screens/VoidAllowanceReport.tsx |
| No-shows | Ausencias | No presentados | screens/AuditPack.tsx; screens/EndOfDay.tsx; screens/Reports.tsx |
| Non AC | Sin CA | Sin aire acondicionado | screens/Setup.tsx |
| None taken | Ninguno adoptado | No se ha cobrado | components/SecurityDepositPanel.tsx |
| Not acknowledged | No reconocido | Sin confirmar | screens/AuditPack.tsx |
| not done | no hecho | sin completar | components/CheckInDialog.tsx |
| Nothing collected yet. | Aún no se ha recopilado nada. | Aún no se han registrado cobros. | screens/Reports.tsx |
| Nothing is waiting on you - every follow-up, hold and payment is current. | Nada le espera: cada seguimiento, retención y pago está al día. | No tiene pendientes: los seguimientos, los bloqueos y los pagos están al día. | screens/Banquet.tsx |
| Nothing moves to the company's account. | Nada se mueve a la cuenta de la empresa. | No se transfiere ningún importe a la cuenta de la empresa. | components/CheckOutDialog.tsx |
| occupied | ocupado | ocupada | screens/Today.tsx |
| Occupied | Ocupado | Ocupada | components/RoomDrawer.tsx; screens/HousekeepingBoard.tsx; screens/Rooms.tsx; screens/Today.tsx |
| Occupied ({n}) | Ocupado ({n}) | Ocupadas ({n}) | screens/POS.tsx |
| Of everything decided | De todo lo decidido | Del total de oportunidades cerradas | screens/Banquet.tsx |
| off | apagado | desactivado | screens/Kitchen.tsx |
| Off | Apagado | Desactivado | screens/settings/ModulePage.tsx; screens/settings/SettingsHub.tsx |
| on | en | activado | screens/Kitchen.tsx |
| On | En | Activado | screens/settings/ModulePage.tsx |
| On file | En el archivo | Guardado | components/GuestDocuments.tsx |
| One consolidated company bill across every room of the group | Una cuenta de empresa consolidada en todas las habitaciones del grupo | Una sola cuenta de empresa para todas las habitaciones del grupo | screens/FolioView.tsx |
| One listing for the whole property. No room numbers required. | Un listado para toda la propiedad. No se requieren números de habitación. | Un alojamiento completo por anuncio. No se requieren números de habitación. | screens/Setup.tsx |
| One row per balance. Type is In-house (what the guest owes; negative if in credit, 0 if settled), City ledger (an unpaid company invoice; negative for money paid ahead) or Deposit (an advance a future booking has paid). Use the closing figures from the old system's last night audit. | Una fila por saldo. El tipo puede ser «Huésped alojado» (lo que debe el huésped; negativo si tiene crédito y 0 si está saldado), «Cuenta de empresa» (factura pendiente de pago; negativo si se pagó de más) o «Depósito» (anticipo recibido para una reserva futura). Ingrese las cifras del último cierre nocturno del sistema anterior. | Una fila por saldo. El tipo puede ser «Huésped alojado» (lo que debe el huésped; negativo si tiene saldo a favor y 0 si está saldado), «Cuenta de empresa» (factura pendiente; negativo si se pagó por adelantado) o «Anticipo de reserva» (anticipo recibido para una reserva futura). Use las cifras del último cierre nocturno del sistema anterior. | screens/GoLiveImport.tsx |
| Online payment links are not available for this country yet. Take payments at the desk. | Los enlaces de pago en línea aún no están disponibles para este país. Tomar pagos en el mostrador. | Los enlaces de pago en línea aún no están disponibles para este país. Registre los cobros en recepción. | screens/settings/cards.tsx |
| Only a Hotel Admin can book a blacklisted guest. | Solo un administrador de hotel puede reservar un huésped en la lista negra. | Solo un administrador del hotel puede crear una reserva para un huésped en la lista negra. | components/BookingDialog.tsx |
| Only Finance or a Hotel Admin can override it. | Solo Finanzas o un administrador de hotel pueden anularlo. | Solo Finanzas o un administrador del hotel pueden autorizar la excepción. | components/BookingDialog.tsx |
| Only Hotel Admin can switch modules. | Solo el administrador del hotel puede cambiar de módulo. | Solo un administrador del hotel puede activar o desactivar módulos. | screens/settings/AccessPages.tsx |
| Only these properties | Sólo estas alojamientos | Solo estos alojamientos | screens/settings/AccessPages.tsx |
| Open a session for your shift (that is the till). Guest payments and POS bills post here automatically while the till is open - take them on Front Desk or Restaurant, not on this page. Use Paid out and Cash drop for cash leaving the drawer, then count and close. | Abra una sesión para su turno (la caja). Los pagos de huéspedes y las cuentas del POS se registran aquí automáticamente mientras la caja está abierta. Recíbalos desde Recepción o Restaurante, no desde esta página. Use «Egreso de caja» y «Retiro de efectivo» para registrar el dinero que sale del cajón; después cuente el efectivo y cierre la sesión. | Abra una sesión de caja para su turno. Mientras esté abierta, los pagos de huéspedes y las cuentas del punto de venta se registran aquí automáticamente; cobre desde Recepción o Restaurante. Use «Egreso de caja» y «Entrega de efectivo a caja central» para registrar las salidas del cajón; después cuente el efectivo y cierre la sesión. | screens/CashierTill.tsx |
| Open bills | Abrir cuentas | Cuentas abiertas | screens/POS.tsx; screens/pos/OpenBillsPopup.tsx |
| Open End of Day | Abierto al final del día | Abrir cierre del día | screens/Billing.tsx |
| Open folios | Abrir folios | Folios abiertos | screens/Dashboard.tsx |
| Open Marketplace → HeyKoala WhatsApp | Mercado abierto → HeyKoala WhatsApp | Abrir catálogo de integraciones → HeyKoala WhatsApp | screens/Setup.tsx |
| Open reservation | Reserva abierta | Abrir reserva | screens/TapeChart.tsx |
| Open session | Sesión abierta | Abrir sesión de caja | screens/CashierTill.tsx |
| Open stay → | Estancia abierta → | Abrir estancia → | screens/WhatsAppChat.tsx |
| Open tasks | Abrir tareas | Tareas abiertas | components/OpenTasksCard.tsx; screens/Dashboard.tsx; screens/Today.tsx |
| Open your till to take or give back money. Count the cash in the drawer and enter it as the opening float (0 if it is empty). | Abre tu caja para recibir o devolver dinero. Cuente el efectivo en el cajón e ingréselo como flotador de apertura (0 si está vacío). | Abra su caja para cobrar o reembolsar. Cuente el efectivo del cajón e ingréselo como fondo inicial de caja (0 si está vacío). | components/TillCard.tsx |
| Open your till {purpose}. Count the cash in the drawer and enter it as the opening float (0 if it is empty). | Abre tu caja {purpose}. Cuente el efectivo en el cajón e ingréselo como flotador de apertura (0 si está vacío). | Abra su caja {purpose}. Cuente el efectivo del cajón e ingréselo como fondo inicial de caja (0 si está vacío). | components/TillCard.tsx |
| Open your till, reconcile cash and close the session under Finance → Cashier. Collections live there now. | Abra su caja, concilie el efectivo y cierre la sesión en Finanzas → Cajero. Las colecciones viven allí ahora. | Abra su caja, concilie el efectivo y cierre la sesión en Finanzas → Cajero. Los cobros se consultan en esa sección. | screens/Billing.tsx |
| Opening float | Fondo inicial | Fondo inicial de caja | components/TillCard.tsx; screens/CashierTill.tsx |
| Opening… | Apertura… | Abriendo… | components/GuestDocuments.tsx |
| Or a screen, a feature (cash drop, night audit, BAR rates) or a setting. | O una pantalla, una función (cobro de efectivo, auditoría nocturna, tarifas BAR) o una configuración. | O una pantalla, una función (entrega de efectivo, auditoría nocturna, tarifas BAR) o una configuración. | components/CommandPalette.tsx |
| or paste it below | o pégalo debajo de | o péguela a continuación | screens/GoLiveImport.tsx |
| Order items | Pedir artículos | Artículos del pedido | screens/pos/OpenBillsPopup.tsx |
| Ordered | Ordenado | Pedido | screens/Kitchen.tsx |
| Orders | Órdenes | Pedidos | screens/POS.tsx; screens/pos/PosSidePanel.tsx |
| Other countries run on a simple flat-tax setup - enter the currency code below. | Otros países utilizan una configuración simple de impuesto fijo: ingrese el código de moneda a continuación. | Otros países utilizan una configuración de impuesto con tasa única. Ingrese el código de moneda a continuación. | screens/Setup.tsx |
| Others from this group still in house | Otros de este grupo todavía en casa | Otros huéspedes de este grupo que siguen alojados | components/CheckOutDialog.tsx |
| Outside the fee window - cancellation is free. | Fuera del período de tarifas: la cancelación es gratuita. | La cancelación queda fuera del plazo sujeto a penalización y no tiene cargo. | components/CancelPanel.tsx |
| Outstanding | Sobresaliente | Saldo pendiente | screens/Banquet.tsx; screens/Dashboard.tsx |
| Overdue by | Vencido por | Retraso de | screens/Tickets.tsx |
| overdue by {t} | vencido por {t} | con {t} de retraso | screens/Tickets.tsx |
| Override with reason | Anulación con motivo | Autorizar excepción con un motivo | screens/EndOfDayWizard.tsx |
| Owes {amount} · terms {n} days | Debe {amount} · términos {n} días | Debe {amount} · plazo de crédito: {n} días | components/CreditTermsEditor.tsx |
| Paid outs | Pagos | Egresos de caja | screens/CashierShiftReport.tsx; screens/CashierTill.tsx |
| Park this stay with no room; promote when inventory frees | Aparca esta estancia sin habitaciones; promocionar cuando el inventario se libere | Poner la reserva en lista de espera, sin habitación; confirmar cuando haya disponibilidad | components/BookingDialog.tsx |
| Parked with no room. Promote it from the reservation when a room frees. Auto-purges 2 days after departure. | Estacionado sin espacio. Promocionarlo desde la reserva cuando se libere una habitación. Autopurgas 2 días después de la salida. | Reserva en lista de espera, sin habitación. Confírmela desde la reserva cuando haya disponibilidad. Se elimina automáticamente 2 días después de la fecha de salida. | components/BookingDialog.tsx |
| Part paid | Parte pagada | Pago parcial | components/DepositPanel.tsx |
| Part to move (percent, or {cur} before {tax}) | Pieza a mover (porcentaje, o {cur} antes de {tax}) | Importe a trasladar (porcentaje o importe en {cur} antes de {tax}) | screens/FolioView.tsx |
| Party | Fiesta | Personas | screens/POS.tsx |
| Pass an allowance | Pasar una asignación | Aplicar una bonificación | screens/FolioView.tsx |
| Pass inspection ✓ | Pasar la inspección ✓ | Aprobar inspección ✓ | screens/HkApp.tsx |
| Pax | Pax | Personas | screens/Banquet.tsx |
| Payment mode | Modo de pago | Medio de pago | components/BookingDialog.tsx; components/CheckOutDialog.tsx; components/DepositPanel.tsx; components/SecurityDepositPanel.tsx; screens/pos/OrderHistory.tsx |
| Per-item prices the app quotes and bills from. A blank express price uses the multiplier in Settings → Housekeeping. | Precios por artículo desde los que la aplicación cotiza y cuenta. Un precio exprés en blanco utiliza el multiplicador en Configuración → Limpieza. | Tarifas por prenda que la aplicación usa para cotizar y facturar. Si el precio del servicio exprés se deja en blanco, se aplica el multiplicador de Configuración → Limpieza. | screens/Laundry.tsx |
| Photo on file | Foto en el archivo | Foto guardada | components/CheckInDialog.tsx |
| Pick a hall. | Elige una sala. | Seleccione un salón. | screens/Banquet.tsx |
| Pick a property first. | Primero elija una propiedad. | Seleccione primero un alojamiento. | screens/GoLiveImport.tsx; screens/KitchenPrinters.tsx |
| Pick your region and name the property. Currency, time zone, tax and language follow the region. Add rooms, rates and the rest later, at your pace. | Elija su región y nombre la propiedad. La moneda, la zona horaria, los impuestos y el idioma siguen la región. Añade habitaciones, tarifas y el resto después, a tu ritmo. | Seleccione su región y asigne un nombre al alojamiento. La moneda, la zona horaria, los impuestos y el idioma se configuran según la región. Después podrá agregar habitaciones, tarifas y el resto de la configuración a su ritmo. | screens/Setup.tsx |
| Pieces | Piezas | Prendas | screens/Laundry.tsx |
| POS and kitchen sound | TPV y sonido de cocina | Sonido del punto de venta y de cocina | components/AlertSettings.tsx |
| POS bill cancelled | cuenta POS cancelada | Cuenta del punto de venta anulada | screens/VoidAllowanceReport.tsx |
| POS speed check | Comprobación de velocidad POS | Comprobación de velocidad del punto de venta | screens/settings/cards.tsx |
| POS void | POS nulo | Anulación en punto de venta | screens/VoidAllowanceReport.tsx |
| Post voucher | Registrar cupón | Registrar vale | screens/PettyCash.tsx |
| Posted on {date}: {i} in-house ({it}), {d} deposit(s) ({dt}), {r} city ledger ({rt}); {a} already posted | Registrado el {date}: {i} saldo(s) de huéspedes alojados ({it}), {d} depósito(s) ({dt}), {r} cuenta(s) de empresa ({rt}); {a} ya estaban registrados | Registrado el {date}: {i} saldos de huéspedes alojados ({it}), {d} anticipos de reserva ({dt}), {r} cuentas por cobrar a empresas ({rt}); {a} ya estaban registrados | screens/GoLiveImport.tsx |
| Posted {n} room nights ({amount}), {ns} no-shows. The business date is now {next}. | Se registraron {n} noches de habitación ({amount}) y {ns} ausencias. La fecha operativa ahora es {next}. | Se registraron {n} noches de habitación ({amount}) y {ns} huéspedes no presentados. La fecha operativa ahora es {next}. | screens/EndOfDayWizard.tsx |
| Pre-checked-in | Registro previo | Registro previo completado | screens/Today.tsx |
| Preparing End of Day… | Preparando el final del día… | Preparando el cierre del día… | screens/EndOfDayWizard.tsx |
| Price menu | Menú de precios | Tarifario | screens/Laundry.tsx |
| Print GRC | Imprimir GRC | Imprimir ficha de registro | screens/RegistrationCard.tsx |
| Print registration card | Imprimir tarjeta de registro | Imprimir ficha de registro | components/CheckInDialog.tsx |
| Print station (a kitchen screen prints it) | Estación de impresión (una serigrafía de cocina lo imprime) | Estación de impresión (imprime desde una pantalla de cocina) | screens/KitchenPrinters.tsx |
| Printers at this property | Impresoras en esta propiedad | Impresoras de este alojamiento | screens/KitchenPrinters.tsx |
| Printing waited on the print dialog. Start Chrome with --kiosk-printing on this till to print KOTs instantly. | La impresión esperó en el cuadro de diálogo de impresión. Inicie Chrome con --kiosk-printing en esta caja registradora para imprimir KOT al instante. | La impresión quedó esperando el cuadro de diálogo. Inicie Chrome con --kiosk-printing en esta caja para imprimir las comandas al instante. | screens/POS.tsx |
| Property access | Acceso a la propiedad | Acceso a alojamientos | screens/settings/AccessPages.tsx |
| Property name * | Nombre de propiedad * | Nombre del alojamiento * | screens/Setup.tsx |
| Property time | Tiempo de propiedad | Hora del alojamiento | screens/EndOfDayWizard.tsx |
| property-specific guidance - upsell priorities, tone | Orientación específica de propiedad: prioridades de ventas adicionales, tono | Instrucciones del alojamiento: prioridades de venta de servicios adicionales y tono | screens/settings/cards.tsx |
| Provisional Bill | Proyecto de ley provisional | Cuenta provisional | screens/FolioView.tsx |
| Rate | Tasa | Tarifa | screens/Laundry.tsx; screens/RateCalendar.tsx |
| Rate {cur} | Tasa {cur} | Tarifa {cur} | screens/Laundry.tsx |
| Ready / unpaid | Listo/no pagado | Listo / pendiente de pago | screens/POS.tsx; screens/pos/OpenBillsPopup.tsx |
| Ready by | Listo por | Entrega prevista para | screens/Laundry.tsx |
| Ready to sell | Listo para vender | Disponibles para reservar | screens/Rooms.tsx |
| Reason (guest declined, duplicate…) | Motivo (huésped rechazado, duplicado...) | Motivo (el huésped rechazó el servicio, solicitud duplicada…) | screens/Laundry.tsx |
| Reason for overriding the blacklist | Motivo para anular la lista negra | Motivo para autorizar una reserva pese a la lista negra | components/BookingDialog.tsx |
| Reason for the credit override (logged) | Motivo de la anulación de crédito (registrado) | Motivo de la excepción de crédito (queda registrado) | components/BookingDialog.tsx |
| Reason for the override (logged with your name) | Motivo de la anulación (registrado con su nombre) | Motivo de la excepción (se registra con su nombre) | components/CheckOutDialog.tsx |
| Reason, e.g. guest left | Motivo, p. huésped abandonado | Motivo, por ejemplo, el huésped ya se retiró | screens/pos/VoidApproval.tsx |
| Reason… | Razón… | Motivo… | screens/pos/VoidApproval.tsx |
| Record | Registro | Registrar | screens/FolioView.tsx |
| Record {amt} | Registro {amt} | Registrar {amt} | components/DepositPanel.tsx |
| Red bills were never sent. Send them, or cancel with a reason. | Los billetes rojos nunca fueron enviados. Envíalos o cancela con un motivo. | Las cuentas en rojo no se enviaron a cocina. Envíelas o cancélelas indicando un motivo. | screens/POS.tsx |
| Refund by | Reembolso por | Medio de reembolso | components/CheckOutDialog.tsx |
| Refund deposit | Depósito de reembolso | Reembolsar depósito de garantía | components/SecurityDepositPanel.tsx |
| Refund money (deposit return / over-collection) | Reembolso de dinero (devolución de depósito/sobrecobro) | Reembolsar dinero (devolución de depósito o cobro en exceso) | screens/FolioView.tsx |
| Refund {amount} | Reembolso {amount} | Reembolsar {amount} | components/CheckOutDialog.tsx |
| Refund {amt} | Reembolso {amt} | Reembolsar {amt} | components/SecurityDepositPanel.tsx |
| Refundable damage deposit - held for the guest, not revenue. Refunded or withheld at check-out. | Depósito reembolsable por daños: se retiene para el huésped y no se considera ingreso. Se devuelve o se descuenta al registrar la salida. | Depósito de garantía reembolsable por daños. Se retiene para el huésped y no es un ingreso. Al registrar la salida se devuelve o se retiene para cubrir los daños. | components/SecurityDepositPanel.tsx |
| Refundable deposit of {amount}, payable separately | Depósito reembolsable de {amount}, a pagar por separado | Depósito de garantía reembolsable de {amount}, a pagar por separado | screens/PublicBooking.tsx |
| Refundable deposit: {amount} | Depósito reembolsable: {amount} | Depósito de garantía reembolsable: {amount} | screens/PublicListing.tsx |
| Registration card | Tarjeta de registro | Ficha de registro | components/CheckInDialog.tsx; components/RoomDrawer.tsx; screens/RegistrationCard.tsx; screens/Today.tsx; screens/settings/cards.tsx |
| Registration card - your signature | Tarjeta de registro: tu firma | Ficha de registro: tu firma | screens/PublicCheckin.tsx |
| Registration checklist | Lista de verificación de registro | Lista de verificación del registro de entrada | screens/RegistrationCard.tsx |
| Reprint KOT | Reimpresión KOT | Reimprimir comanda | screens/POS.tsx |
| Request implementation | Solicitud de implementación | Solicitar implementación | screens/Marketplace.tsx |
| Requests don't hold a room. Accepting checks availability again. | Las solicitudes no ocupan una habitación. Al aceptar cheques disponibilidad nuevamente. | Las solicitudes no bloquean habitaciones. Al aceptarlas, se vuelve a comprobar la disponibilidad. | components/BookingRequests.tsx |
| Required | Requerido | Obligatorio | components/CheckInDialog.tsx; components/SecurityDepositPanel.tsx; screens/settings/cards.tsx |
| required, not done | requerido, no hecho | obligatorio, sin completar | components/CheckInDialog.tsx |
| Reset {name}'s cashier PIN? They set a new one on their next money action. | ¿Restablecer el PIN de cajero de {name}? Establecieron uno nuevo en su próxima acción monetaria. | ¿Restablecer el PIN de cajero de {name}? Deberá crear uno nuevo en su próxima operación de cobro o caja. | screens/settings/AccessPages.tsx |
| Restaurant & other bills to check | Restaurante y otras cuentas para verificar | Cuentas de restaurante y otros servicios por revisar | components/CheckOutDialog.tsx |
| Restaurant / laundry not on folio yet | Restaurante/lavandería aún no está en el folio | Consumos de restaurante o lavandería aún sin cargar al folio | components/CheckOutDialog.tsx |
| Restaurant POS | POS de restaurante | Punto de venta del restaurante | screens/CashierTill.tsx; screens/POS.tsx |
| Retake | Retomar | Volver a tomar la foto | components/CameraCapture.tsx |
| Return & deliver | Devolución y entrega | Recibir y entregar prendas | screens/Laundry.tsx |
| Return to room {room} | Regresar a la habitación {room} | Devolver prendas a la habitación {room} | screens/Laundry.tsx |
| Returning guest · {n} stay{s} | Huésped frecuente · {n} estancia{s} | Huésped recurrente · {n} estancia{s} | components/BookingDialog.tsx |
| Review | Revisión | Revisar | screens/TapeChart.tsx |
| RevPAX = total guest spend (room + F&B + experiences + extras) per in-house guest - the ancillary revenue RevPAR can't see. | RevPAX = gasto total de los huéspedes (habitación + comida y bebida + experiencias + extras) por huésped interno: los ingresos por servicios complementarios que RevPAR no puede ver. | RevPAX = gasto total (habitación, alimentos y bebidas, experiencias y extras) por huésped alojado. Incluye los ingresos adicionales que no refleja el RevPAR. | screens/Reports.tsx |
| Room Blocks | Bloques de habitaciones | Bloqueos de habitaciones | components/RoomDrawer.tsx |
| Room board | Tablero de habitación | Panel de habitaciones | screens/Today.tsx |
| Room Board | Tablero de habitación | Panel de habitaciones | screens/HousekeepingBoard.tsx |
| Room given by {who} | Habitación cedida por {who} | Habitación asignada por {who} | components/RoomDrawer.tsx |
| Room moves | Movimientos de habitación | Cambios de habitación | components/RoomDrawer.tsx |
| Room nights | Habitaciones noches | Noches de habitación | screens/EndOfDay.tsx |
| room rev / room | habitación rev/habitación | ingresos por habitaciones / habitación | screens/Reports.tsx |
| Room {n} assigned. | habitación {n} asignada. | Habitación {n} asignada. | components/BookingDialog.tsx |
| Room {room} on {date}: out {etd} ({out}) / in {eta} ({in}) | habitación {room} en {date}: fuera {etd} ({out}) / en {eta} ({in}) | Habitación {room}, {date}: salida {etd} ({out}) / entrada {eta} ({in}) | screens/TapeChart.tsx |
| Rooms are matched to each guest's type and preferences. Assigning places them now; "Review" flags a choice worth a second look. | Las habitaciones se adaptan al tipo y preferencias de cada huésped. Asignarlos los coloca ahora; "Revisar" señala una opción que merece una segunda mirada. | Las habitaciones se seleccionan según el tipo reservado y las preferencias del huésped. Al asignarlas, la habitación queda confirmada; «Revisar» indica una propuesta que conviene comprobar. | screens/TapeChart.tsx |
| Rotate secret | Girar secreto | Renovar clave secreta | screens/settings/WebhooksPage.tsx |
| Rotate the signing secret? The receiver must switch to the new one. | ¿Rotar el secreto de firma? El receptor debe cambiar al nuevo. | ¿Renovar la clave secreta de firma? El sistema receptor deberá usar la nueva. | screens/settings/WebhooksPage.tsx |
| Running tables | Mesas de carrera | Mesas con cuentas abiertas | screens/POS.tsx |
| Safe (no receipt) | Caja fuerte (sin recibo) | Caja fuerte (sin confirmación de recepción) | screens/CashierTill.tsx |
| Save for me | Ahorra para mí | Guardar mi diseño | components/CustomizeToday.tsx |
| Save imprest | Guardar anticipo | Guardar fondo fijo de caja chica | screens/PettyCash.tsx |
| Scheduled 3 AM audit when checks block: {mode} | Auditoría programada a las 3 a.m. cuando se bloquean los controles: {mode} | Acción de la auditoría automática de las 3 a. m. si hay bloqueos: {mode} | screens/EndOfDayWizard.tsx |
| Search guests, bookings, invoices, screens, features, settings… | Buscar invitados, reservas, facturas, pantallas, funciones, configuraciones… | Buscar huéspedes, reservas, facturas, pantallas, funciones, configuración… | components/CommandPalette.tsx |
| Search guests, bookings, screens, settings… | Buscar invitados, reservas, pantallas, configuraciones… | Buscar huéspedes, reservas, pantallas, configuración… | AppShell.tsx |
| Search menu items… | Buscar elementos del menú… | Buscar artículos del menú… | screens/POS.tsx |
| Search settings | Configuración de búsqueda | Buscar en configuración | screens/settings/SettingsHub.tsx |
| Search subject, room, guest, id | Asunto de búsqueda, habitación, huésped, id | Buscar por asunto, habitación, huésped o identificador | screens/Tickets.tsx |
| Search table… | Buscar en la tabla… | Buscar mesa… | screens/POS.tsx |
| seats {n} | asientos {n} | Capacidad: {n} personas | screens/Banquet.tsx |
| Secured | Garantizado | Anticipo cubierto | components/DepositPanel.tsx |
| Security deposit | Depósito de seguridad | Depósito de garantía | components/SecurityDepositPanel.tsx; screens/PublicBooking.tsx |
| Security Deposit Amount | Monto del depósito de seguridad | Importe del depósito de garantía | screens/Setup.tsx |
| Security deposit held | Depósito de seguridad retenido | Depósito de garantía retenido | components/CheckInDialog.tsx; components/CheckOutDialog.tsx |
| Select | Seleccione | Seleccionar | components/BookingDialog.tsx; screens/FolioView.tsx; screens/Setup.tsx |
| Select charge | Seleccionar carga | Seleccionar cargo | screens/FolioView.tsx |
| Select items from the menu | Seleccionar elementos del menú | Seleccione artículos del menú | screens/POS.tsx |
| Server work {ms} ms - fine. | El servidor funciona {ms} ms: bien. | Tiempo de procesamiento del servidor: {ms} ms. Adecuado. | screens/settings/cards.tsx |
| Server work {ms} ms - slow. The server is busy or under-sized. | El servidor funciona {ms} ms: lento. El servidor está ocupado o es de tamaño insuficiente. | Tiempo de procesamiento del servidor: {ms} ms. Es lento. El servidor está sobrecargado o tiene recursos insuficientes. | screens/settings/cards.tsx |
| Service Tickets | Tickets de servicio | Solicitudes de servicio | screens/Tickets.tsx |
| Set | Conjunto | Establecer | screens/TapeChart.tsx |
| Set for corporate business - it also decides which folio the bill lands on. | Establecido para negocios corporativos: también decide en qué folio aterriza el billete. | Configure las condiciones para empresas; también determinan a qué folio se carga la cuenta. | screens/Banquet.tsx |
| Sets {currency}, {tax} invoices, local ID types and payment methods. | Establece facturas {currency}, {tax}, tipos de ID locales y métodos de pago. | Configura la moneda {currency}, las facturas con {tax}, los documentos de identidad locales y los medios de pago. | screens/Setup.tsx |
| Settle | Resolver | Liquidar | screens/POS.tsx; screens/pos/OpenBillsPopup.tsx; screens/pos/SettleSheet.tsx |
| Settle to continue | Conformarse para continuar | Liquidar para continuar | components/CheckOutDialog.tsx |
| Settling a bill separately takes money: open your till on the Payment step first. | Liquidar una cuenta por separado requiere dinero: primero abra su caja en el paso de Pago. | Para cobrar una cuenta por separado, abra primero su caja en el paso «Pago». | components/CheckOutDialog.tsx |
| Shared playground, not your hotel. Data is wiped every night. | Parque infantil compartido, no en tu hotel. Los datos se borran todas las noches. | Entorno de demostración compartido. Los datos se borran cada noche. | AppShell.tsx |
| Shortage | Escasez | Faltante | screens/Laundry.tsx |
| Show or print the registration card and have the guest sign it. | Muestre o imprima la tarjeta de registro y haga que el huésped la firme. | Muestre o imprima la ficha de registro y solicite la firma del huésped. | components/CheckInDialog.tsx |
| Show {n} deactivated | Mostrar {n} desactivado | Mostrar personal desactivado: {n} | screens/settings/AccessPages.tsx |
| Showing {n} of {total} bills | Mostrando {n} de los billetes {total} | Mostrando {n} de {total} cuentas | screens/pos/OrderHistory.tsx |
| sign the printed card | firmar la tarjeta impresa | firmar la ficha impresa | screens/RegistrationCard.tsx |
| Signed in | Iniciado en | Sesión iniciada | screens/Agents.tsx |
| Signed out | Cerrado sesión | Sesión cerrada | screens/Agents.tsx |
| Skipped by {who} at {when} | Omitido por {who} en {when} | Omitido por {who}, {when} | components/CheckInDialog.tsx |
| Sleeps | Duerme | Capacidad | components/RoomDrawer.tsx |
| Sleeps up to {guests} | Tiene capacidad para {guests} | Huéspedes: hasta {guests} | components/BookingDialog.tsx |
| Sleeps up to {n} | Capacidad para hasta {n} adultos | Adultos: hasta {n} | screens/PublicBooking.tsx; screens/PublicListing.tsx |
| Smaller than the pax count | Menor que el recuento de personas | Inferior al número de asistentes | screens/Banquet.tsx |
| Smoking | Fumar | Se permite fumar | components/RoomDrawer.tsx |
| Soft hold you can sell over | Fijación suave que puedes vender sobre | Bloqueo provisional que permite aceptar otras reservas | screens/Banquet.tsx |
| Sold out | Agotado | Sin disponibilidad | components/BookingRequests.tsx; screens/PublicListing.tsx |
| Solved in | Resuelto en | Tiempo de resolución | screens/Tickets.tsx |
| Some items have no kitchen printer; turn on Print KOT to print them here. | Algunos artículos no tienen impresora de cocina; Active Imprimir KOT para imprimirlos aquí. | Algunos artículos no tienen una impresora de cocina asignada. Active «Imprimir comandas» para imprimirlos aquí. | screens/POS.tsx |
| Source | Fuente | Origen | screens/RegistrationCard.tsx; screens/Today.tsx |
| Spent this month | Pasó este mes | Gastado este mes | screens/PettyCash.tsx |
| Split | Dividido | Dividir | screens/POS.tsx |
| Split folio | Folio dividido | Dividir folio | screens/FolioView.tsx |
| Statistics (month to date) | Estadísticas (mes hasta la fecha) | Estadísticas (acumulado del mes) | screens/Dashboard.tsx |
| Status of each printer. Add or edit under F&B → Printers. | Estado de cada impresora. Agregue o edite en F&B → Impresoras. | Estado de cada impresora. Agregue o edite impresoras en Alimentos y bebidas → Impresoras. | screens/settings/cards.tsx |
| Stay actions | Acciones de suspensión | Acciones de la estancia | screens/TapeChart.tsx |
| Stay info | Información estancia | Información de la estancia | components/CheckInDialog.tsx |
| staying over | quedarse sobre | continúa alojado | screens/TapeChart.tsx |
| Still due | Aún vencido | Pendiente de pago | components/DepositPanel.tsx |
| Still in play | Todavía en juego | En negociación | screens/Banquet.tsx |
| Suggested room plan for {date} | Plano de habitación sugerido para {date} | Propuesta de asignación de habitaciones para {date} | screens/TapeChart.tsx |
| Supervisor passes | El supervisor pasa | El supervisor aprueba la inspección | screens/HkApp.tsx |
| Switch off {name} for this property? | ¿Desactivar {name} para esta propiedad? | ¿Desactivar {name} para este alojamiento? | screens/settings/AccessPages.tsx; screens/settings/SettingsHub.tsx |
| Switch on what you need. You can change this any time in Settings. | Enciende lo que necesitas. Puedes cambiar esto en cualquier momento en Configuración. | Active los módulos que necesite. Puede cambiarlos en cualquier momento en Configuración. | screens/Setup.tsx |
| Switch to light mode | Cambiar al modo de luz | Cambiar al modo claro | AppShell.tsx |
| Table name | Nombre de la tabla | Nombre de la mesa | screens/POS.tsx |
| Table note | Nota de tabla | Nota de la mesa | screens/Kitchen.tsx |
| Table or room | Mesa o salón | Mesa o habitación | screens/pos/OrderHistory.tsx |
| Table {n} has {count} bills | La tabla {n} tiene billetes {count} | La mesa {n} tiene {count} cuentas | screens/POS.tsx |
| Tables & running bills | Tablas y cuentas corrientes | Mesas y cuentas abiertas | screens/POS.tsx |
| Take it | Tómalo | Asignarme la solicitud | screens/Tickets.tsx |
| Take the deposit (or waive it with a reason) to continue. | Tomar el depósito (o renunciar a él con un motivo) para continuar. | Cobre el depósito de garantía o indique un motivo para exonerarlo y continuar. | components/CheckInDialog.tsx |
| Take the security deposit (or waive it with a reason) and any advance the booking still owes. | Tomar el depósito de seguridad (o renunciar a él con un motivo) y cualquier anticipo que la reserva aún deba. | Cobre el depósito de garantía, o indique un motivo para exonerarlo, y el anticipo pendiente de la reserva. | components/CheckInDialog.tsx |
| Take the security deposit or waive it with a reason to continue. | Tomar el depósito de seguridad o renunciar a él con un motivo para continuar. | Cobre el depósito de garantía o indique un motivo para exonerarlo y continuar. | components/CheckInDialog.tsx |
| Take this room | Toma esta habitación | Asignarme esta habitación | screens/HkApp.tsx |
| Taken | Tomado | Reservado | screens/Banquet.tsx |
| Tape chart | Gráfico de cintas | Calendario de ocupación | screens/TapeChart.tsx |
| Tax Invoice | Factura de impuestos | Factura fiscal | screens/FolioView.tsx |
| taxable {cur}{amount} | sujeto a impuestos {cur}{amount} | base imponible: {cur}{amount} | screens/FolioView.tsx |
| Tell the guest the Wi-Fi, breakfast and check-out times. Print it or send it on WhatsApp. | Informe al huésped los horarios del wifi, el desayuno y la salida. Imprima la información o envíela por WhatsApp. | Informe al huésped los datos del wifi y los horarios de desayuno y salida. Imprima la información o envíela por WhatsApp. | components/CheckInDialog.tsx |
| Temp / custom table… | Tabla temporal/personalizada… | Mesa temporal o personalizada… | screens/POS.tsx |
| Test connection | Conexión de prueba | Probar conexión | screens/settings/cards.tsx |
| Test page sent. It prints on the kitchen screen set to print for {printer}. | Página de prueba enviada. Se imprime en la pantalla de la cocina configurada para imprimir para {printer}. | Página de prueba enviada. Se imprimirá desde la pantalla de cocina configurada para la impresora {printer}. | screens/KitchenPrinters.tsx |
| Test sound | Prueba de sonido | Probar sonido | components/AlertSettings.tsx |
| The folio only has {amt} in credit - settle the bill first, or let the deposit cover it. | El folio solo tiene {amt} en crédito: liquide la cuenta primero o deje que el depósito la cubra. | El folio solo tiene {amt} de saldo a favor. Liquide la cuenta primero o use el depósito de garantía para cubrirla. | components/SecurityDepositPanel.tsx |
| The guest checked in online{when}. Check what they sent against the guest at the desk. | El huésped realizó el check-in en línea{when}. Verifique lo que enviaron contra el huésped en el mostrador. | El huésped completó el registro de entrada en línea{when}. Verifique en recepción que los datos enviados correspondan al huésped. | components/CheckInDialog.tsx |
| The guest is in-house: the old room is marked Dirty for housekeeping. | El huésped está en la casa: la antigua habitación está marcada como Sucia para el servicio de limpieza. | El huésped está alojado. La habitación anterior se marcará como sucia para que el personal de limpieza la atienda. | components/RoomChangeDialog.tsx |
| The guest signed the printed card | El huésped firmó la tarjeta impresa | El huésped firmó la ficha impresa | components/CheckInDialog.tsx |
| The hall's rack rental goes on as the first line - the number the conversation starts from. | El alquiler de racks de la sala continúa en la primera línea: el número desde el que comienza la conversación. | La tarifa base de alquiler del salón se agrega como primera línea y sirve de punto de partida para la cotización. | screens/Banquet.tsx |
| The hotel's billing rules pick the folio, and food and drink take the hotel's food tax rate. | Las reglas de facturación del hotel eligen el folio, y los alimentos y bebidas toman la tasa de impuesto a los alimentos del hotel. | Las reglas de facturación determinan el folio al que se cargan los consumos. A los alimentos y bebidas se les aplica la tasa de impuesto configurada para ellos. | components/RoomStayPanels.tsx |
| The online booking page can run alongside a channel manager or on its own. | La página de reservas en línea puede ejecutarse junto con un administrador de canal o de forma independiente. | La página de reservas en línea puede funcionar junto con un gestor de canales o de forma independiente. | screens/Setup.tsx |
| The rest printed here. | El resto impreso aquí. | Las comandas restantes se imprimieron aquí. | screens/POS.tsx |
| The room is still occupied. Check the current guest out first. | La habitación todavía está ocupada. Primero, revisa al huésped actual. | La habitación sigue ocupada. Registre primero la salida del huésped actual. | components/RoomDrawer.tsx |
| The slot must end after it starts. | La ranura debe finalizar después de comenzar. | La franja horaria debe terminar después de su hora de inicio. | components/BookingDialog.tsx |
| Then recreate the stack / run migrate. Nightly channel | Luego vuelva a crear la pila/ejecute la migración. Canal nocturno | Después vuelva a crear los contenedores o ejecute la migración. Canal de compilaciones diarias | screens/SystemHealth.tsx |
| This blocks the audit. Fix it above, or override it with a reason - your name and the time are recorded on the audit. | Esto bloquea la auditoría. Corríjalo arriba o anúlelo con un motivo: su nombre y la hora se registran en la auditoría. | Esto bloquea la auditoría. Resuélvalo en la sección anterior o autorice una excepción indicando el motivo. Su nombre y la hora quedarán registrados en la auditoría. | screens/EndOfDayWizard.tsx |
| This closes the bag without billing. Tell us why - it's recorded on the order. | Esto cierra la bolsa sin facturación. Díganos por qué: está registrado en el pedido. | Esto cierra la orden de lavandería sin facturar. Indique el motivo; quedará registrado en la orden. | screens/Laundry.tsx |
| This module is off, so its apps are hidden for everyone. Settings are kept for when you switch it back on. | Este módulo está desactivado, por lo que sus aplicaciones están ocultas para todos. La configuración se conserva hasta que la vuelvas a encender. | Este módulo está desactivado y sus aplicaciones están ocultas para todos. La configuración se conserva para cuando vuelva a activarlo. | screens/settings/SettingsHub.tsx |
| This posts tonight's room and tax for every in-house guest, applies the no-show policy, saves the audit pack and rolls the business date from {bd}. It cannot be undone. | Esto registra los cargos de habitación e impuestos de esta noche para cada huésped alojado, aplica la política de ausencias, guarda el informe de auditoría y avanza la fecha operativa desde {bd}. Esta acción no se puede deshacer. | Esto registra los cargos de habitación e impuestos de esta noche para cada huésped alojado, aplica la política de huéspedes no presentados, guarda el paquete de auditoría y avanza la fecha operativa desde {bd}. Esta acción no se puede deshacer. | screens/EndOfDayWizard.tsx |
| This property | Esta propiedad | Este alojamiento | screens/Dashboard.tsx |
| This property only - switch hotel in the header to see another. | Solo esta propiedad: cambie de hotel en el encabezado para ver otro. | Solo este alojamiento. Cambie de hotel en el encabezado para consultar otro. | screens/PettyCash.tsx |
| This sets currency {currency}, time zone {tz}, and {tax} invoices. | Esto establece la moneda {currency}, la zona horaria {tz} y {tax} de las facturas. | Configura la moneda {currency}, la zona horaria {tz} y las facturas con {tax}. | screens/Setup.tsx |
| This type is full tonight - try another room type. | Este tipo está lleno esta noche; pruebe con otro tipo de habitación. | No hay disponibilidad de este tipo de habitación para esta noche. Pruebe con otro tipo. | components/BookingDialog.tsx |
| Tick all | Marque todo | Seleccionar todo | components/CheckOutDialog.tsx |
| Tick Credit allowed and save to bill this company on the city ledger. | Marque Crédito permitido y guárdelo para facturar a esta empresa en el cuenta por cobrar de empresas. | Marque «Crédito permitido» y guarde los cambios para facturar a esta empresa en su cuenta por cobrar. | components/CreditTermsEditor.tsx |
| Tick the lines moving to the new bill. | Marque las líneas que se mueven al nuevo billete. | Marque las líneas que desea trasladar a la nueva cuenta. | screens/POS.tsx |
| Ticket {kot} {dest} | Boleto {kot} {dest} | Comanda {kot} {dest} | screens/Kitchen.tsx |
| Tickets for this printer print on this device's default printer. | Los boletos para esta impresora se imprimen en la impresora predeterminada de este dispositivo. | Las comandas dirigidas a esta impresora se imprimen en la impresora predeterminada de este dispositivo. | screens/Kitchen.tsx |
| Times drive the house position: back-to-back rooms flag a conflict when the arrival lands before the departure. | Los tiempos influyen en la posición de la casa: las habitaciones consecutivas señalan un conflicto cuando la llegada aterriza antes de la salida. | Los horarios determinan la disponibilidad real de las habitaciones. En reservas consecutivas se indica un conflicto si la llegada está prevista antes de la salida del huésped anterior. | screens/TapeChart.tsx |
| to pick up a room. | para recoger una habitación. | para asignarse la limpieza de una habitación. | screens/HkApp.tsx |
| to take the deposit | para tomar el depósito | para cobrar el depósito de garantía | components/CheckInDialog.tsx |
| to take the walk-in's payment | para aceptar el pago sin cita previa | para cobrar al huésped sin reserva previa | components/BookingDialog.tsx |
| Today at this property, by department. | Hoy en esta propiedad, por departamento. | Actividad de hoy en este alojamiento, por departamento. | screens/Dashboard.tsx |
| total, taxes in | total, impuestos en | total, impuestos incluidos | screens/CRS.tsx |
| Trigger | Gatillo | Origen de la ejecución | screens/EndOfDay.tsx |
| Txns | Transmisores | Movimientos | screens/CashierShiftReport.tsx |
| Undo NC | Deshacer NC | Quitar cortesía | screens/POS.tsx |
| Up to {n} adults | Hasta {n} adultos | Adultos: máximo {n} | screens/PublicBooking.tsx |
| Up to {n} children | Hasta {n} niños | Niños: máximo {n} | screens/PublicBooking.tsx; screens/PublicListing.tsx |
| Up to {n} guests | Hasta {n} huéspedes | Huéspedes: máximo {n} | screens/PublicListing.tsx |
| Upgrade or another type | Actualización u otro tipo | Mejora de categoría u otro tipo de habitación | components/CheckInDialog.tsx |
| Use property default ({n} days) | Usar propiedad predeterminada ({n} días) | Usar el plazo predeterminado del alojamiento ({n} días) | components/CreditTermsEditor.tsx |
| Used on {n} earlier stays | Usado en estancias anteriores {n} | Usado en {n} estancias anteriores | components/CheckInDialog.tsx; components/GuestDocuments.tsx |
| Vacant | Vacante | Desocupada | components/RoomDrawer.tsx |
| Veg | Vegetal | Vegetariano | screens/Kitchen.tsx; screens/POS.tsx |
| View ID scan | Ver escaneo de ID | Ver imagen del documento de identidad | components/GuestDocuments.tsx |
| View only. {roles} can change these. | Ver solo. {roles} puede cambiarlos. | Solo lectura. Los roles {roles} pueden modificar estos datos. | screens/settings/ModulePage.tsx |
| VIP guest | huésped VIP | Huésped VIP | components/CheckInDialog.tsx |
| Visits: {visits} · Bills: {bills} · Spent: {amount} · Last: {day} | Visitas: {visits} · cuentas: {bills} · Gastadas: {amount} · Últimas: {day} | Visitas: {visits} · Cuentas: {bills} · Gasto: {amount} · Última visita: {day} | screens/pos/PosSidePanel.tsx |
| Void | Nulo | Anular | screens/FolioView.tsx; screens/VoidAllowanceReport.tsx |
| Void (the kitchen has it) | Vacío (la cocina lo tiene) | Anular (ya enviado a cocina) | screens/POS.tsx; screens/pos/OpenBillsPopup.tsx |
| Void item | Artículo anulado | Anular artículo | screens/POS.tsx |
| Void {item} | Vacío {item} | Anular {item} | screens/POS.tsx |
| Voided after the kitchen had it | Anulado después de que la cocina lo tuviera | Anulado después de enviarse a cocina | screens/pos/PosSidePanel.tsx |
| WAITING | ESPERANDO | EN ESPERA | screens/Kitchen.tsx |
| Waive | Renunciar a | Exonerar | components/SecurityDepositPanel.tsx |
| Waive deposit | Renunciar al depósito | Exonerar depósito de garantía | components/SecurityDepositPanel.tsx |
| Waive the fee (logged - manager's call) | Renunciar a la tarifa (registrado - llamada del gerente) | Exonerar el cargo (decisión del gerente que queda registrada) | components/CancelPanel.tsx |
| Waived: {reason} | Exención: {reason} | Exonerado: {reason} | components/SecurityDepositPanel.tsx |
| Walk-in | Vestidor | Sin reserva previa | AppShell.tsx; components/BookingDialog.tsx |
| Webhook | Gancho web | Webhook | screens/settings/WebhooksPage.tsx |
| What each room costs per night, and what moved it. | Cuánto cuesta cada habitación por noche y qué la movió. | La tarifa de cada habitación por noche y los ajustes que se le aplicaron. | screens/RateCalendar.tsx |
| What everyone at this hotel sees until they customise their own Today. | Lo que todos en este hotel ven hasta personalizar el suyo Today. | El diseño que verá el personal del hotel hasta que personalice su propia pantalla Hoy. | components/CustomizeToday.tsx |
| What for | Qué pasa con | Concepto | components/RoomStayPanels.tsx |
| What this money is: against the bill, an advance, or a refundable deposit | Qué es este dinero: contra la cuenta, un anticipo o un depósito reembolsable | Concepto del pago: abono a la cuenta, anticipo de reserva o depósito de garantía reembolsable | screens/FolioView.tsx |
| What was damaged | Qué fue dañado | Descripción de los daños | components/CheckOutDialog.tsx |
| What was done? (kept with the ticket) | ¿Qué se hizo? (conservado con el ticket) | ¿Qué se hizo? (se guarda en la solicitud) | screens/Tickets.tsx |
| What you agreed for them | Lo que acordaste para ellos | Importe acordado para los huéspedes adicionales | components/BookingDialog.tsx |
| When | Cuando | Cuándo | screens/Agents.tsx; screens/CashierTill.tsx; screens/VoidAllowanceReport.tsx |
| When the guest pays, the deposit posts here automatically. | Cuando el huésped paga, el depósito se registra aquí automáticamente. | Cuando el huésped pague, el anticipo se registrará aquí automáticamente. | components/DepositPanel.tsx |
| Where | Donde | Dónde | screens/pos/PosSidePanel.tsx |
| Where a ticket goes if this printer fails. | Adónde va un ticket si esta impresora falla. | Impresora a la que se enviará la comanda si esta falla. | screens/KitchenPrinters.tsx |
| Where the months are landing | Donde aterrizan los meses | Previsión mensual de eventos | screens/Banquet.tsx |
| Which hall - free for these dates and hours | Qué sala - libre para estas fechas y horarios | Salones disponibles para estas fechas y horarios | screens/Banquet.tsx |
| Who cleaned it | Quién lo limpió | Responsable de limpieza | components/RoomDrawer.tsx |
| Who signed in to and out of Kamra, newest first. | Quién inició sesión y salió de Kamra, el más nuevo primero. | Inicios y cierres de sesión en Kamra, del más reciente al más antiguo. | screens/Agents.tsx |
| Who stayed here | Quién se quedó aquí | Quién se alojó aquí | components/RoomDrawer.tsx |
| Whose function is this? | ¿De quién es esta función? | ¿Para quién se organiza este evento? | screens/Banquet.tsx |
| Why business went away | Por qué el negocio desapareció | Motivos de pérdida de oportunidades | screens/Banquet.tsx |
| Why this total | Por qué este total | Desglose del total | components/CheckOutDialog.tsx |
| Wi-Fi and stay info | Wi-Fi e información estancia | Wifi e información de la estancia | components/CheckInDialog.tsx; screens/settings/cards.tsx |
| Withhold for damage | Retención por daños | Retener por daños | components/CheckOutDialog.tsx; components/SecurityDepositPanel.tsx |
| Within | Dentro de | Dentro del plazo | screens/Tickets.tsx |
| Write the reason for the override to continue. | Escriba el motivo por el que continúa la anulación. | Indique el motivo de la excepción para continuar. | components/CheckOutDialog.tsx |
| Wrong payment mode? Change it | ¿Modo de pago incorrecto? Cámbielo | ¿Medio de pago incorrecto? Cámbielo | screens/pos/PosSidePanel.tsx |
| Your property is created. These are the things still to do, in any order. Each one links to where you do it. | Se crea su propiedad. Estas son las cosas que aún quedan por hacer, en cualquier orden. Cada uno enlaza con el lugar donde lo haces. | Su alojamiento ya está creado. Estas son las tareas pendientes; puede completarlas en cualquier orden. Cada una incluye un enlace a la sección correspondiente. | screens/FinishSetup.tsx |
| Your role can't change this bill. Ask {who}. | Su función no puede cambiar esta cuenta. Pregunte a {who}. | Su rol no permite modificar esta cuenta. Solicite ayuda a {who}. | components/CheckOutDialog.tsx |
| Your role can't open a till. Ask {who} to take the money. | Su rol no puede abrir una caja. Pídele a {who} que acepte el dinero. | Su rol no permite abrir una caja. Solicite a {who} que registre el cobro. | components/TillCard.tsx |
| Your session ended. Sign in to pick up where you left off. | Su sesión finalizó. Inicia sesión para continuar donde lo dejaste. | Su sesión finalizó. Inicie sesión para continuar donde lo dejó. | screens/Login.tsx |
| Zero-rate and complimentary rooms | Habitaciones tarifa cero y cortesía | Habitaciones con tarifa cero y de cortesía | screens/AuditPack.tsx |
| {amount} moves to the company's account. | {amount} se mueve a la cuenta de la empresa. | {amount} pasa a la cuenta por cobrar de la empresa. | components/CheckOutDialog.tsx |
| {amt} left on the bill. | {amt} queda en la cuenta. | Quedan {amt} por pagar en la cuenta. | components/BookingDialog.tsx |
| {amt} of {total} collected | {amt} de {total} recogido | {amt} de {total} cobrados | components/BookingDialog.tsx |
| {avail} left · sleeps {cap} · {rate}/night | Quedan {avail} · capacidad para {cap} adultos · {rate}/noche | Disponibles: {avail} · capacidad (adultos): {cap} · {rate}/noche | screens/CRS.tsx |
| {course} held · {n} | {course} retenido · {n} | {course} en espera · {n} | screens/Kitchen.tsx |
| {c} companies created, {u} updated | {c} empresas creadas, {u} actualizadas | Empresas creadas: {c}; actualizadas: {u} | screens/GoLiveImport.tsx |
| {done} of {total} done | {done} de {total} hecho | {done} de {total} completados | screens/FinishSetup.tsx |
| {free} free · {booked} booked · {blocked} held | {free} gratis · {booked} reservado · {blocked} retenido | {free} disponibles · {booked} reservadas · {blocked} bloqueadas | components/RoomDrawer.tsx |
| {from} to {to}, nights up to last night | {from} a {to}, noches hasta anoche | Del {from} al {to}, con las noches hasta anoche | components/RoomInsights.tsx |
| {f} Floor | {f} Piso | Piso {f} | screens/Today.tsx |
| {guest} moved in from room {room} | {guest} se mudó desde la habitación {room} | {guest} fue trasladado desde la habitación {room} | components/RoomDrawer.tsx |
| {guest} moved out to room {room} | {guest} se mudó a la habitación {room} | {guest} fue trasladado a la habitación {room} | components/RoomDrawer.tsx |
| {guest} · check out or open registration | {guest} · registrar la salida o abrir el registro | {guest} · registrar la salida o abrir la ficha de registro | screens/Today.tsx |
| {lock} makes the keys when you check the guest in. | {lock} hace las llaves cuando registras al huésped. | {lock} genera las llaves al registrar la entrada del huésped. | components/CheckInDialog.tsx |
| {name} is checked in | {name} está marcado en | Se registró la entrada de {name} | components/CheckInDialog.tsx |
| {name} is checked in to room {room} | {name} está registrado en la habitación {room} | Se registró la entrada de {name} en la habitación {room} | components/CheckInDialog.tsx |
| {name} is checked out. | {name} está desprotegido. | Se registró la salida de {name}. | components/CheckOutDialog.tsx |
| {name} module | {name} módulo | Módulo {name} | screens/settings/SettingsHub.tsx |
| {name} usually takes {min}+ - check the minimum spend applies. | {name} generalmente toma {min}+; verifique que se aplique el gasto mínimo. | {name} suele requerir al menos {min} personas. Verifique si se aplica el consumo mínimo. | screens/Banquet.tsx |
| {n} ad | {n} anuncio | {n} ad. | components/BookingRequests.tsx; screens/Today.tsx |
| {n} already in Kamra (left alone) | {n} ya en Kamra (solo) | {n} ya estaban en Kamra (sin cambios) | screens/GoLiveImport.tsx |
| {n} blocker(s) | {n} bloqueador(es) | Bloqueos: {n} | screens/EndOfDay.tsx; screens/EndOfDayWizard.tsx |
| {n} booking(s) imported, {h} as past-stay history, {a} already in Kamra | {n} reservas importadas, {h} como historial de estancias pasadas, {a} ya en Kamra | Reservas importadas: {n}; historial de estancias pasadas: {h}; ya existentes en Kamra: {a} | screens/GoLiveImport.tsx |
| {n} changeover conflict{s} | {n} conflicto{s} de cambio | {n} conflicto{s} entre salidas y entradas | screens/TapeChart.tsx |
| {n} exception(s) | {n} excepción(es) | Incidencias: {n} | screens/Billing.tsx |
| {n} failed today | {n} falló hoy | Fallos de hoy: {n} | screens/KitchenPrinters.tsx; screens/settings/cards.tsx |
| {n} free now | {n} gratis ahora | Disponibles ahora: {n} | components/BookingRequests.tsx |
| {n} functions on the books | {n} funciones en los libros | Eventos registrados: {n} | screens/Banquet.tsx |
| {n} function{s} · {pax} pax | {n} función{s} · {pax} pax | {n} evento{s} · {pax} personas | Clave de compatibilidad del diccionario |
| {n} key(s) handed over. | {n} llave(s) entregada(s). | Llaves entregadas: {n}. | components/CheckInDialog.tsx |
| {n} late arrival(s) held | {n} Llegadas tardías retenidas | Reservas mantenidas por llegada tardía: {n} | screens/Billing.tsx |
| {n} modules | {n} módulos | Módulos: {n} | screens/Setup.tsx |
| {n} new, {e} existing (updated), {c} on credit | {n} nuevo, {e} existente (actualizado), {c} a crédito | Nuevos: {n}; existentes actualizados: {e}; a crédito: {c} | screens/GoLiveImport.tsx |
| {n} night{s} · {amount} · {folios} folio{s2} · {noShows} no-show{s3} | {n} noche{s} · {amount} · {folios} folio{s2} · {noShows} ausencia{s3} | {n} noche{s} · {amount} · {folios} folio{s2} · {noShows} no presentado{s3} | screens/Billing.tsx |
| {n} out of service | {n} fuera de servicio | Fuera de servicio: {n} | components/RoomInsights.tsx |
| {n} overdue · Housekeeping | {n} vencido · Limpieza | Limpieza · tareas vencidas: {n} | screens/Today.tsx |
| {n} pc | {n} pieza | {n} pzas. | screens/Laundry.tsx |
| {n} pending | {n} pendiente | Pendientes: {n} | screens/Laundry.tsx |
| {n} piece(s) short - why? (required) | {n} pieza(s) corta(s) - ¿por qué? (obligatorio) | Faltan {n} prendas. Indique el motivo (obligatorio) | screens/Laundry.tsx |
| {n} posted | {n} registrados | Registrados: {n} | screens/PettyCash.tsx |
| {n} propert{ies} with space · {nights} night{s}, {adults} adult{s2}{children} | {n} propiedad{ies} con espacio · {nights} noche{s}, {adults} adulto{s2}{children} | Alojamientos disponibles: {n} · {nights} noche{s}, {adults} adulto{s2}{children} | Clave de compatibilidad del diccionario |
| {n} ready to import | {n} listo para importar | Listos para importar: {n} | screens/GoLiveImport.tsx |
| {n} rooms | {n} habitaciones | Habitaciones: {n} | screens/Dashboard.tsx |
| {n} rooms free for these dates | {n} habitaciones libres para estas fechas | Habitaciones disponibles para estas fechas: {n} | components/RoomChangeDialog.tsx |
| {n} rooms · from {rate}/night | {n} habitaciones · desde {rate}/noche | Habitaciones: {n} · desde {rate}/noche | screens/CRS.tsx |
| {n} seats | {n} asientos | Asientos: {n} | screens/POS.tsx |
| {n} staying | {n} permaneciendo | Huéspedes alojados: {n} | screens/Today.tsx |
| {n} this session | {n} esta sesión | En esta sesión: {n} | screens/CashierTill.tsx |
| {n} tickets | {n} entradas | Comandas: {n} | screens/Kitchen.tsx |
| {n} unassigned - take one to add it to your list | {n} sin asignar: tome uno para agregarlo a su lista | {n} sin asignar. Tome una tarea para agregarla a su lista | screens/HkApp.tsx |
| {n} waiting | {n} esperando | En espera: {n} | screens/KitchenPrinters.tsx; screens/settings/cards.tsx |
| {n}{ord} Floor | {n}{ord} Piso | Piso {n} | screens/Today.tsx |
| {rooms} rooms · {booked} in use | {rooms} habitaciones · {booked} en uso | Habitaciones: {rooms} · en uso: {booked} | screens/TapeChart.tsx |
| {room} hasn't been cleaned yet - housekeeping will see the room flip to occupied. | {room} aún no se ha limpiado: el servicio de limpieza hará que la habitación pase a estar ocupada. | La habitación {room} aún no está limpia. El personal de limpieza verá que pasa a estar ocupada. | components/BookingDialog.tsx |
| {tax} rate | {tax} tasa | Tasa de {tax} | components/RoomStayPanels.tsx; screens/FolioView.tsx |
| {tax} summary | {tax} resumen | Resumen de {tax} | screens/FolioView.tsx |
| {type} folio | {type} folio | Folio de {type} | components/CheckOutDialog.tsx; components/RoomStayPanels.tsx |
| {type} room | {type} habitación | Habitación {type} | screens/PublicCheckin.tsx |
| {type}: stay total +{amt} (now {total}) | {type}: permanece en total +{amt} (ahora {total}) | {type}: el total de la estancia sube {amt} (nuevo total: {total}) | components/RoomChangeDialog.tsx |
| {type}: stay total -{amt} (now {total}) | {type}: estancia total -{amt} (ahora {total}) | {type}: el total de la estancia baja {amt} (nuevo total: {total}) | components/RoomChangeDialog.tsx |
| {t} left | {t} izquierda | Quedan {t} | screens/Tickets.tsx |
| {who} raised it ({source}) | {who} lo levantó ({source}) | {who} creó la solicitud ({source}) | screens/Tickets.tsx |
| {who} took the assignee off | {who} quitó al cesionario | {who} quitó al responsable asignado | screens/Tickets.tsx |

## Entradas añadidas

Incluyen nombres de módulos, estados, comprobaciones recibidas del servidor y claves de compatibilidad. Los identificadores, siglas y rangos numéricos que son iguales en ambos idiomas se conservan explícitamente.

| Clave de origen | Español | Contexto |
| --- | --- | --- |
|  ({n} as past-stay history) |  ({n} como historial de estancias pasadas) | Clave de compatibilidad del diccionario |
| 0-30 | 0-30 | screens/AuditPack.tsx |
| 120+ | 120+ | screens/AuditPack.tsx |
| 31-60 | 31-60 | screens/AuditPack.tsx; screens/EndOfDayWizard.tsx |
| 61-90 | 61-90 | screens/AuditPack.tsx; screens/EndOfDayWizard.tsx |
| 91-120 | 91-120 | screens/AuditPack.tsx |
| Aadhaar | Aadhaar | components/GuestDocuments.tsx; components/IdDocumentField.tsx; lib/money.ts; otras ubicaciones |
| About this install | Acerca de esta instalación | Clave de compatibilidad del diccionario |
| Account | Cuenta | App.tsx; lib/api.ts; lib/apps.ts; otras ubicaciones |
| Accounting Export | Exportación contable | lib/apps.ts; screens/AccountingExport.tsx |
| Acknowledge | Confirmar revisión | lib/eod.ts; screens/AuditPack.tsx; screens/EndOfDayWizard.tsx |
| Acknowledged | Revisión confirmada | screens/AuditPack.tsx; screens/EndOfDayWizard.tsx |
| Acknowledged check | Comprobación revisada | screens/EndOfDayWizard.tsx |
| Activity Log | Registro de actividad | components/CommandPalette.tsx; lib/apps.ts; screens/Activity.tsx |
| Ad/Ch | Ad./Ni. | screens/EndOfDayWizard.tsx |
| Add a Room Service outlet to give each room an in-room dining code. | Agregue un punto de venta de servicio a la habitación para generar un código de pedidos para cada habitación. | Clave de compatibilidad del diccionario |
| Add discount | Agregar descuento | Clave de compatibilidad del diccionario |
| Add round & fire KOT | Agregar ronda y enviar comanda a preparación | Clave de compatibilidad del diccionario |
| Admin | Administración | AppShell.tsx; components/BookingDialog.tsx; components/BookingRequests.tsx; otras ubicaciones |
| Agent | Agente | App.tsx; AppShell.tsx; components/BookingDialog.tsx; otras ubicaciones |
| Agent access (MCP) | Acceso de agentes (MCP) | Clave de compatibilidad del diccionario |
| all | todos | App.tsx; AppShell.tsx; components/BillingRulesEditor.tsx; otras ubicaciones |
| All Functions | Todos los eventos | lib/apps.ts; screens/configs.ts |
| Already ran for today ({audit}). | La auditoría de hoy ya se ejecutó ({audit}). | Clave de compatibilidad del diccionario |
| Apply discount | Aplicar descuento | Clave de compatibilidad del diccionario |
| AR balance | Saldo de cuentas por cobrar | screens/EndOfDayWizard.tsx |
| Arabic switches the interface to right-to-left · this browser only | El árabe muestra la interfaz de derecha a izquierda · solo en este navegador | Clave de compatibilidad del diccionario |
| Area | Área | screens/configs.ts; screens/POS.tsx |
| Arrival | Llegada | components/BookingDialog.tsx; components/CustomizeToday.tsx; lib/api.ts; otras ubicaciones |
| Arrivals not checked in | Llegadas pendientes de registrar | screens/EndOfDayWizard.tsx |
| Arrivals not checked in exist. Review them or Continue - the no-show policy applies as shown. | Hay llegadas pendientes de registrar. Revíselas o continúe; se aplicará la política de huéspedes no presentados que se muestra. | screens/EndOfDayWizard.tsx |
| Arrivals, departures, bookings and guests - the day's work. | Llegadas, salidas, reservas y huéspedes: la operación del día. | lib/apps.ts |
| Ask for feedback | Solicitar comentarios | kamra/sop.py |
| Ask housekeeping / inspect for damage. Withhold from the deposit or refund the balance. | Consulte al personal de limpieza y revise si hay daños. Retenga del depósito de garantía el importe correspondiente o reembolse el saldo. | kamra/sop.py |
| At audit for arrival date | En la auditoría de la fecha de llegada | kamra/no_show.py; kamra/settings.py; kamra/kamra/doctype/property/property.json |
| Attached | Adjunto | screens/configs.ts |
| Authorize NC | Autorizar cortesía | Clave de compatibilidad del diccionario |
| Auto-accept and print KOT | Aceptar e imprimir comandas automáticamente | kamra/settings.py |
| Auto-print KOT | Imprimir comandas automáticamente | Clave de compatibilidad del diccionario |
| Back from the laundry. Hand it to the guest and post it to the room. | Las prendas regresaron de lavandería. Entréguelas al huésped y cargue el servicio a la habitación. | Clave de compatibilidad del diccionario |
| Balances on departed stays | Saldos pendientes de estancias finalizadas | kamra/night_audit.py |
| Bank Transfer | Transferencia bancaria | lib/money.ts; screens/BanquetFunction.tsx; screens/CityLedgerPayment.tsx; otras ubicaciones |
| Banquets & Groups | Banquetes y grupos | lib/apps.ts |
| before GST | antes del GST | Clave de compatibilidad del diccionario |
| Bill no | N.º de cuenta | screens/EndOfDayWizard.tsx |
| Bill's room | Habitación de la cuenta | screens/EndOfDayWizard.tsx |
| Bills not on the folio yet | Cuentas aún sin cargar al folio | Clave de compatibilidad del diccionario |
| block | bloquear | App.tsx; AppShell.tsx; components/AlertSettings.tsx; otras ubicaciones |
| Blocked | Bloqueado | components/BookingDialog.tsx; components/CheckOutDialog.tsx; screens/configs.ts; otras ubicaciones |
| Booked rate | Tarifa reservada | screens/AuditPack.tsx; screens/EndOfDayWizard.tsx |
| Booking Engine | Motor de reservas | lib/apps.ts; screens/BookingEngine.tsx |
| Booking page | Página de reservas | screens/BookingEngine.tsx |
| Books | Contabilidad | lib/apps.ts; screens/AccountingExport.tsx; screens/Ledgers.tsx |
| Calendar | Calendario | App.tsx; components/CalendarView.tsx; components/RoomDrawer.tsx; otras ubicaciones |
| Cancellation no | N.º de cancelación | screens/AuditPack.tsx |
| Captain / GM name | Nombre del jefe de servicio o gerente general | Clave de compatibilidad del diccionario |
| Capture the ID on the GRC - check-in is never blocked, but the register wants it before the night audit. | Registre el documento de identidad en la ficha del huésped. Esto no bloquea la entrada, pero debe completarse antes de la auditoría nocturna. | Clave de compatibilidad del diccionario |
| Card slip / UTR (optional) | Comprobante de tarjeta o referencia UTR (opcional) | Clave de compatibilidad del diccionario |
| Cart | Pedido | screens/POS.tsx |
| Cash taken | Efectivo cobrado | screens/EndOfDayWizard.tsx |
| Cashier closure | Cierre de caja | kamra/night_audit.py |
| Cashier PIN reset | Restablecimiento del PIN de cajero | kamra/api.py |
| Cashier summary | Resumen por cajero | screens/AuditPack.tsx |
| Cashier till, folios, ledgers, night audit and books export. | Caja del cajero, folios, libros contables, auditoría nocturna y exportación contable. | lib/apps.ts |
| Cashier unlocked - money actions are open for 15 minutes. | Caja desbloqueada: las operaciones de cobro y caja estarán habilitadas durante 15 minutos. | Clave de compatibilidad del diccionario |
| Categories with occupancy-based pricing. | Categorías con tarifas según la ocupación. | screens/configs.ts |
| Central Reservations | Central de reservas | lib/apps.ts |
| CGST ({rate}%) | CGST ({rate}%) | Clave de compatibilidad del diccionario |
| Channel Manager | Gestor de canales | lib/apps.ts; screens/configs.ts |
| Channels | Canales | lib/apps.ts; screens/configs.ts; screens/WhatsAppChat.tsx |
| Charge | Cargo | components/BookingDialog.tsx; components/CheckInDialog.tsx; components/CheckOutDialog.tsx; otras ubicaciones |
| Check | Comprobación | App.tsx; components/BillingRulesEditor.tsx; components/BookingDialog.tsx; otras ubicaciones |
| Check damages & security deposit | Revisar daños y depósito de garantía | kamra/sop.py |
| Check in & collect {amt} | Registrar entrada y cobrar {amt} | Clave de compatibilidad del diccionario |
| Check in to {room} | Registrar entrada en la habitación {room} | Clave de compatibilidad del diccionario |
| Check-in time | Hora de entrada | kamra/settings.py |
| Checked In | Entrada registrada | components/CheckOutDialog.tsx; components/CommandPalette.tsx; components/GroupControl.tsx; otras ubicaciones |
| Checked Out | Salida registrada | components/ResourceScreen.tsx; screens/configs.ts; screens/GuestJourney.tsx; otras ubicaciones |
| Checking in… | Registrando entrada… | Clave de compatibilidad del diccionario |
| Checkout Clean | Limpieza por salida | screens/configs.ts |
| City ledger / AR summary | Resumen de cuentas por cobrar a empresas | screens/AuditPack.tsx |
| Cleaning Fee | Cargo de limpieza | screens/configs.ts |
| Clear all | Borrar todo | Clave de compatibilidad del diccionario |
| Click a bar to move rooms or change dates. | Haga clic en una barra para cambiar de habitación o modificar las fechas. | Clave de compatibilidad del diccionario |
| Close each property's business date: work through the checklist, post room and tax, roll the date and print the audit pack. The 3 AM job runs the same steps on its own. | Cierre la fecha operativa de cada alojamiento: complete las comprobaciones, registre los cargos de habitación e impuestos, avance la fecha e imprima el paquete de auditoría. El proceso de las 3 a. m. realiza estos pasos automáticamente. | screens/EndOfDay.tsx |
| Close the day | Cerrar el día | lib/apps.ts; lib/searchIndex.ts |
| Code | Código | App.tsx; lib/apps.ts; screens/Agents.tsx; otras ubicaciones |
| Collect payment or settle | Cobrar o liquidar la cuenta | kamra/sop.py |
| Collect what is owed, refund overpayments, or send a corporate balance to the city ledger. | Cobre el saldo pendiente, reembolse los pagos en exceso o transfiera el saldo corporativo a la cuenta por cobrar de la empresa. | kamra/sop.py |
| Common | General | screens/configs.ts |
| Companies | Empresas | components/LinkedRecords.tsx; lib/apps.ts; lib/eodFixes.ts; otras ubicaciones |
| Companies over their credit limit | Empresas que exceden su límite de crédito | kamra/night_audit.py |
| Complaint | Queja | components/RoomStayPanels.tsx; screens/Tickets.tsx |
| Completed | Completado | components/ResourceScreen.tsx; lib/api.ts; screens/BanquetDiary.tsx; otras ubicaciones |
| Completed with Warnings | Completado con advertencias | kamra/folio.py; kamra/kamra/doctype/night_audit_run/night_audit_run.json |
| Confirm billing instructions | Confirmar instrucciones de facturación | kamra/sop.py |
| Confirm booking discounts and any mid-stay allowances are correct. | Compruebe que los descuentos de la reserva y las bonificaciones aplicadas durante la estancia sean correctos. | kamra/sop.py |
| Confirm discounts & vouchers | Confirmar descuentos y cupones | kamra/sop.py |
| Confirm F&B and minibar lines with the guest before collecting. | Revise con el huésped los consumos de alimentos, bebidas y minibar antes de cobrar. | kamra/sop.py |
| Confirm which charges bill to the company vs the guest (alcohol always guest). | Confirme qué cargos paga la empresa y cuáles el huésped. Las bebidas alcohólicas siempre se cobran al huésped. | kamra/sop.py |
| Confirmation | Confirmación | components/BookingDialog.tsx; screens/AuditPack.tsx; screens/EndOfDayWizard.tsx |
| Copy link | Copiar enlace | Clave de compatibilidad del diccionario |
| Country | País | lib/money.ts; lib/phone.ts; screens/BookingEngine.tsx; otras ubicaciones |
| Cover count | Número de comensales | Clave de compatibilidad del diccionario |
| Credit | Crédito | components/BookingDialog.tsx; components/CheckOutDialog.tsx; components/CompanyExtras.tsx; otras ubicaciones |
| Currency Desk | Cambio de moneda | lib/apps.ts; lib/searchIndex.ts; screens/CurrencyDesk.tsx |
| Cycle open bills | Alternar entre cuentas abiertas | screens/POS.tsx |
| Damages | Daños | components/CheckOutDialog.tsx; screens/BanquetFunction.tsx |
| Database | Base de datos | kamra/health.py |
| Debit | Débito | screens/AuditPack.tsx; screens/Ledgers.tsx |
| Deep Clean | Limpieza profunda | screens/configs.ts |
| Deliver & post to Room {n} | Entregar y cargar a la habitación {n} | Clave de compatibilidad del diccionario |
| Delivery | Entrega a domicilio | screens/BanquetDocument.tsx; screens/Kitchen.tsx; screens/POS.tsx; otras ubicaciones |
| Demand pricing (hurdle rates) | Tarifas según demanda y ocupación | screens/settings/cards.tsx |
| Departure | Salida | components/CustomizeToday.tsx; screens/AuditPack.tsx; screens/configs.ts; otras ubicaciones |
| Departures not checked out | Salidas pendientes de registrar | screens/EndOfDayWizard.tsx |
| Departures not checked out exist. Check them out or extend the stay. | Hay salidas pendientes de registrar. Registre la salida de los huéspedes o extienda sus estancias. | screens/EndOfDayWizard.tsx |
| Departures still in house | Huéspedes con salida prevista que siguen alojados | kamra/night_audit.py; kamra/settings.py |
| Departures still in house block the audit | Las salidas pendientes de registrar bloquean la auditoría | kamra/settings.py |
| Deposit ledger balance | Saldo de depósitos y anticipos | screens/AuditPack.tsx |
| Developers | Desarrolladores | App.tsx; components/CommandPalette.tsx; lib/apps.ts; otras ubicaciones |
| Difference | Diferencia | screens/AuditPack.tsx; screens/EndOfDayWizard.tsx |
| Dine In | Consumo en el local | screens/POS.tsx; screens/pos/OrderHistory.tsx |
| Discount % | Descuento (%) | Clave de compatibilidad del diccionario |
| Discounts | Descuentos | components/CheckOutDialog.tsx |
| Disk space | Espacio en disco | kamra/health.py |
| Double | Doble | components/CheckInDialog.tsx; components/RoomChangeDialog.tsx; components/RoomDrawer.tsx; otras ubicaciones |
| Driving License | Licencia de conducir | components/GuestDocuments.tsx; lib/money.ts |
| Early Check-in | Entrada anticipada | components/BillingRulesEditor.tsx; components/RoomStayPanels.tsx; screens/configs.ts; otras ubicaciones |
| Emirates ID | Emirates ID | kamra/localization/uae.py |
| End of day | Cierre del día | lib/apps.ts |
| Enquiry | Consulta | components/ResourceScreen.tsx; lib/api.ts; screens/Banquet.tsx; otras ubicaciones |
| Enter 1-99%, or a {cur} amount under the line's {cur}{amount} (before GST). | Ingrese un porcentaje entre 1 y 99 %, o un importe en {cur} inferior al total de la línea ({cur}{amount}, antes del GST). | Clave de compatibilidad del diccionario |
| Entire place - checks in as one unit | Alojamiento completo: se registra la entrada como una sola unidad | Clave de compatibilidad del diccionario |
| Entire place - checks in as one unit ({rooms}) | Alojamiento completo: se registra la entrada como una sola unidad ({rooms}) | Clave de compatibilidad del diccionario |
| Entries | Asientos | components/CheckOutDialog.tsx; lib/accents.ts; screens/AuditPack.tsx; otras ubicaciones |
| EOD | Cierre del día | lib/apps.ts |
| Error | Error | App.tsx; components/BookingDialog.tsx; components/BookingRequests.tsx; otras ubicaciones |
| ETA | Hora prevista de llegada | components/RoomDrawer.tsx; lib/api.ts; screens/AuditPack.tsx; otras ubicaciones |
| Every arrival is checked in. | Todas las llegadas tienen su entrada registrada. | screens/EndOfDayWizard.tsx |
| Every departure is checked out. | Todas las salidas están registradas. | screens/EndOfDayWizard.tsx |
| Every outlet bill is settled. | Todas las cuentas de los puntos de venta están liquidadas. | screens/EndOfDayWizard.tsx |
| Every room night posted so far matches its booked rate. | Todas las noches de habitación registradas hasta ahora coinciden con la tarifa reservada. | screens/EndOfDayWizard.tsx |
| Every room night was posted at its booked rate. | Todas las noches de habitación se registraron con la tarifa reservada. | screens/AuditPack.tsx |
| Every till for the business date should be counted and closed. | Todas las cajas de esta fecha operativa deben tener su arqueo realizado y estar cerradas. | screens/EndOfDayWizard.tsx |
| Every till is closed. | Todas las cajas están cerradas. | screens/EndOfDayWizard.tsx |
| Exit POS - back to the PMS | Salir del punto de venta y volver al PMS | Clave de compatibilidad del diccionario |
| Experiences | Experiencias | lib/apps.ts; screens/configs.ts; screens/PublicBooking.tsx |
| Exposure | Exposición crediticia | screens/EndOfDayWizard.tsx |
| Extra | Extra | components/BillingRulesEditor.tsx; components/BookingDialog.tsx; components/CheckInDialog.tsx; otras ubicaciones |
| Extra Guests | Huéspedes adicionales | components/BillingRulesEditor.tsx; screens/configs.ts |
| Extras | Extras | components/CheckInDialog.tsx; components/CheckOutDialog.tsx; components/CompanyExtras.tsx; otras ubicaciones |
| F&B | Alimentos y bebidas | components/BillingRulesEditor.tsx; components/ResourceScreen.tsx; components/StayInstructions.tsx; otras ubicaciones |
| F&B Dashboard | Panel de alimentos y bebidas | lib/apps.ts |
| F&B revenue | Ingresos de alimentos y bebidas | screens/AuditPack.tsx |
| Failed | Fallido | screens/SystemHealth.tsx; screens/WhatsAppChat.tsx; screens/settings/cards.tsx; otras ubicaciones |
| FAQ | Preguntas frecuentes | lib/apps.ts; screens/BookingEngine.tsx |
| Fee | Cargo | components/CheckOutDialog.tsx; screens/AuditPack.tsx; screens/configs.ts |
| Filter | Filtrar | components/ResourceScreen.tsx; lib/resource.ts; screens/Agents.tsx; otras ubicaciones |
| Finalize | Finalizar | kamra/night_audit.py |
| Fire KOT | Enviar comanda a preparación | Clave de compatibilidad del diccionario |
| Flag in-house folios owing more than | Marcar los folios de huéspedes alojados cuyo saldo supere | kamra/settings.py |
| Folio History | Historial del folio | lib/apps.ts; screens/FolioHistory.tsx |
| Food & Beverage | Alimentos y bebidas | components/BillingRulesEditor.tsx; components/RoomStayPanels.tsx; screens/configs.ts; otras ubicaciones |
| for foreign nationals, Form C to the immigration authorities | para huéspedes extranjeros, el formulario C dirigido a las autoridades migratorias | i18n/notice/bn.json; i18n/notice/hi.json; i18n/notice/kn.json; otras ubicaciones |
| Frappe Desk | Escritorio de Frappe | lib/apps.ts |
| from {day} | desde {day} | Clave de compatibilidad del diccionario |
| Front desk hours | Horario de recepción | Clave de compatibilidad del diccionario |
| Front office | Recepción | screens/EndOfDayWizard.tsx |
| Front office and the room board agree. | Los datos de recepción coinciden con el panel de habitaciones. | screens/EndOfDayWizard.tsx |
| Function Diary | Agenda de eventos | lib/apps.ts |
| Function prospecting, quotations and event orders - plus room blocks and pickup. | Consultas, cotizaciones y órdenes de servicio para eventos, junto con bloqueos de habitaciones y seguimiento de las reservas del grupo. | lib/apps.ts |
| GCC ID | Documento de identidad del CCG | kamra/localization/saudi.py; kamra/localization/uae.py |
| Group bookings | Reservas de grupo | kamra/banquet.py |
| Groups & Blocks | Grupos y bloqueos | components/LinkedRecords.tsx; lib/apps.ts; screens/configs.ts |
| GST {rate}% | GST {rate}% | Clave de compatibilidad del diccionario |
| GSTIN | GSTIN | lib/money.ts; screens/AccountingExport.tsx; screens/BanquetDocument.tsx; otras ubicaciones |
| Guardrails | Límites de tarifas | lib/apps.ts; screens/configs.ts; screens/RateCalendar.tsx; otras ubicaciones |
| Guest in house, room board shows Vacant | Huésped alojado con habitación marcada como desocupada en el panel | kamra/night_audit.py |
| Guest ledger detail | Detalle de cuentas de huéspedes | screens/AuditPack.tsx |
| Guest privacy | Privacidad de los huéspedes | kamra/privacy.py |
| guest registration with the Shomoos security system | registro de huéspedes en el sistema de seguridad Shomoos | kamra/localization/saudi.py |
| Guest request | Solicitud de huésped | components/CancelPanel.tsx; components/RoomChangeDialog.tsx; components/RoomDrawer.tsx; otras ubicaciones |
| Guest Requests | Solicitudes de huéspedes | lib/apps.ts |
| Guest requests and ops workflows. | Solicitudes de huéspedes y flujos de operación. | lib/apps.ts |
| Guest requests with SLA - Urgent 15m · High 30m · Medium 1h · Low 4h | Plazos de atención de solicitudes: urgente 15 min · alta 30 min · media 1 h · baja 4 h | Clave de compatibilidad del diccionario |
| Halls & Venues | Salones y espacios para eventos | lib/apps.ts; screens/Banquet.tsx; screens/configs.ts |
| Has task | Con tarea asignada | screens/HousekeepingBoard.tsx |
| High | Alta | components/RoomStayPanels.tsx; screens/configs.ts; screens/HkApp.tsx; otras ubicaciones |
| High balances in house | Saldos elevados de huéspedes alojados | kamra/night_audit.py |
| Hold | Mantener en espera | components/RoomDrawer.tsx; lib/occupancy.ts; screens/BanquetFunction.tsx; otras ubicaciones |
| Hold and alert | Detener y avisar | kamra/folio.py; kamra/night_audit.py; kamra/settings.py |
| Hold late arrivals until the next audit | Mantener las reservas de llegada tardía hasta la próxima auditoría | kamra/settings.py |
| Hotel Admin | Administrador del hotel | AppShell.tsx; components/BookingDialog.tsx; components/BookingRequests.tsx; otras ubicaciones |
| Hotel Admin (GM) | Administrador del hotel (gerente general) | screens/Login.tsx |
| Hotel local clock - night audit and timestamps. Updates the site time zone too. | Hora local del hotel para la auditoría nocturna y los registros. También actualiza la zona horaria del sitio. | Clave de compatibilidad del diccionario |
| Hotel Profile | Perfil del hotel | lib/apps.ts; screens/BookingEngine.tsx |
| House Use | Uso interno | components/RoomDrawer.tsx; screens/configs.ts |
| House use | Uso interno | components/RoomDrawer.tsx |
| How was your stay with us? Is there anything we could have done better? | ¿Cómo fue su estancia con nosotros? ¿Hay algo que podríamos haber hecho mejor? | kamra/sop.py |
| IGST ({rate}%) | IGST ({rate}%) | Clave de compatibilidad del diccionario |
| Import {n} booking{s} | Importar {n} reserva{s} | Clave de compatibilidad del diccionario |
| In balance | Cuadrado | Clave de compatibilidad del diccionario |
| In Process | En proceso | components/CheckOutDialog.tsx; screens/HkLaundry.tsx; screens/Laundry.tsx; otras ubicaciones |
| In Progress | En curso | components/OpenTasksCard.tsx; components/ResourceScreen.tsx; components/RoomDrawer.tsx; otras ubicaciones |
| In-house folios | Folios de huéspedes alojados | screens/EndOfDayWizard.tsx; screens/GoLiveImport.tsx |
| In-house folios over the high-balance threshold and balances left on departed stays. | Folios de huéspedes alojados que superan el límite de saldo y saldos pendientes de estancias finalizadas. | screens/EndOfDayWizard.tsx |
| Info | Información | AppShell.tsx; components/CheckInDialog.tsx; components/CustomizeToday.tsx; otras ubicaciones |
| info | información | AppShell.tsx; components/CheckInDialog.tsx; components/CheckOutDialog.tsx; otras ubicaciones |
| Inspection | Inspección | screens/configs.ts; screens/HkApp.tsx |
| Installed apps | Aplicaciones instaladas | kamra/health.py |
| Instructions | Instrucciones | components/StayInstructions.tsx; screens/BanquetDocument.tsx; screens/ReservationDetail.tsx |
| Invite a short review of the stay. It keeps the farewell warm and useful. | Pida al huésped una breve opinión sobre su estancia para despedirlo de forma cercana y recoger sus comentarios. | kamra/sop.py |
| Iqama | Iqama | kamra/localization/saudi.py |
| is live. Bring your existing bookings over - paste a CSV, or let the AI migration assistant do the mapping via MCP. | ya está en funcionamiento. Importe sus reservas mediante un CSV o use el asistente de migración con IA para relacionar los campos mediante MCP. | Clave de compatibilidad del diccionario |
| Issue | Incidencia | components/CheckOutDialog.tsx; components/GuestDocuments.tsx; screens/BanquetFunction.tsx; otras ubicaciones |
| Journal by cashier and transaction code | Diario por cajero y código de transacción | screens/AuditPack.tsx |
| JPG/PNG/WebP · under 1 MB | JPG, PNG o WebP · menos de 1 MB | components/ResourceScreen.tsx |
| Kamra Agent | Agente Kamra | AppShell.tsx; components/BookingRequests.tsx; components/HelpPanel.tsx; otras ubicaciones |
| Key numbers | Indicadores principales | components/CustomizeToday.tsx |
| Keyboard shortcuts | Atajos de teclado | Clave de compatibilidad del diccionario |
| King | King | components/RoomTypeMedia.tsx; screens/configs.ts; screens/MenuImport.tsx |
| Kitchen Inventory | Inventario de cocina | lib/apps.ts; screens/configs.ts |
| Late Checkout | Salida tardía | components/BillingRulesEditor.tsx; components/CheckOutDialog.tsx; components/RoomStayPanels.tsx; otras ubicaciones |
| Ledger | Libro contable | App.tsx; lib/apps.ts; screens/AccountingExport.tsx; otras ubicaciones |
| Legal name | Razón social | kamra/settings.py |
| Lost & Found | Objetos perdidos y encontrados | lib/apps.ts; screens/configs.ts |
| Low | Baja | components/BookingDialog.tsx; components/CancelPanel.tsx; components/CheckOutDialog.tsx; otras ubicaciones |
| Maintenance | Mantenimiento | components/RoomChangeDialog.tsx; components/RoomDrawer.tsx; components/RoomStayPanels.tsx; otras ubicaciones |
| Manage direct booking setup, property profile, photo gallery, FAQs, and SEO rules. | Configure las reservas directas, el perfil del alojamiento, la galería de fotos, las preguntas frecuentes y el posicionamiento en buscadores. | lib/apps.ts |
| Manage End of Day | Gestionar cierre del día | screens/EndOfDay.tsx; screens/EndOfDayWizard.tsx |
| Manage Users | Administrar usuarios | kamra/assistant.py |
| Manager's flash | Resumen gerencial | screens/AuditPack.tsx |
| Mark no-shows | Marcar huéspedes no presentados | kamra/settings.py |
| Meal Plan | Plan de comidas | components/BillingRulesEditor.tsx; lib/apps.ts; screens/configs.ts; otras ubicaciones |
| Meal Plans | Planes de comidas | lib/apps.ts; screens/configs.ts; screens/Setup.tsx |
| Medium | Media | components/RoomStayPanels.tsx; screens/configs.ts; screens/Tickets.tsx |
| Menus & Services | Menús y servicios | lib/apps.ts |
| Minibar | Minibar | components/BillingRulesEditor.tsx; components/RoomStayPanels.tsx; screens/configs.ts; otras ubicaciones |
| Misc | Varios | components/BillingRulesEditor.tsx; components/RoomStayPanels.tsx; screens/configs.ts; otras ubicaciones |
| Month Availability | Disponibilidad mensual | lib/apps.ts |
| Municipality fee | Tasa municipal | kamra/settings.py; kamra/localization/saudi.py; kamra/localization/uae.py |
| National ID | Documento nacional de identidad | kamra/localization/saudi.py; kamra/localization/__init__.py |
| Navigate | Navegar | App.tsx; AppShell.tsx; components/BookingDialog.tsx; otras ubicaciones |
| NC | Sin cargo | lib/eodFixes.ts; lib/thermal.ts; screens/CancellationLetter.tsx; otras ubicaciones |
| Needs attention | Requiere atención | screens/Inventory.tsx; screens/SystemHealth.tsx |
| New bill | Nueva cuenta | screens/POS.tsx |
| New order | Nuevo pedido | Clave de compatibilidad del diccionario |
| New Property | Nuevo alojamiento | lib/apps.ts |
| Night audit & no-shows | Auditoría nocturna y no presentados | kamra/no_show.py; kamra/settings.py |
| Night audit checklist | Lista de comprobaciones de auditoría nocturna | kamra/night_audit.py; kamra/settings.py |
| Night Auditor | Auditor nocturno | lib/apps.ts |
| No balances on departed stays. | No hay saldos pendientes de estancias finalizadas. | screens/EndOfDayWizard.tsx |
| No bills on this day. | No hay cuentas para este día. | Clave de compatibilidad del diccionario |
| No cancellations. | No hay cancelaciones. | screens/AuditPack.tsx; screens/PosDashboard.tsx |
| No cashier sessions on this business date. | No hay sesiones de caja para esta fecha operativa. | screens/AuditPack.tsx; screens/EndOfDayWizard.tsx |
| No city ledger accounts. | No hay cuentas por cobrar a empresas. | screens/AuditPack.tsx |
| No company is over its credit limit. | Ninguna empresa supera su límite de crédito. | screens/EndOfDayWizard.tsx |
| No deposits held. | No hay depósitos ni anticipos retenidos. | screens/AuditPack.tsx |
| No free room of this type for these dates - check the tape chart for a move or an upgrade. | No hay habitaciones disponibles de este tipo para estas fechas. Revise el calendario de ocupación para cambiar de habitación o mejorar la categoría. | Clave de compatibilidad del diccionario |
| No guests in house. | No hay huéspedes alojados. | screens/AuditPack.tsx |
| No in-house folio is over the threshold. | Ningún folio de huésped alojado supera el límite. | screens/EndOfDayWizard.tsx |
| No no-show fee on OTA bookings | No aplicar cargos por no presentación a reservas de agencias en línea | kamra/settings.py |
| No no-shows. | No hay huéspedes no presentados. | screens/AuditPack.tsx |
| No outlet bills were posted to rooms today. | Hoy no se cargaron cuentas de puntos de venta a habitaciones. | screens/EndOfDayWizard.tsx |
| No outlet has tables yet. List them on the outlet (e.g. T1:4, T2) to get a code per table. | Ningún punto de venta tiene mesas configuradas. Agréguelas al punto de venta, por ejemplo T1:4, T2, para generar un código por mesa. | Clave de compatibilidad del diccionario |
| No Show | No presentado | components/ResourceScreen.tsx; screens/configs.ts; screens/GuestJourney.tsx; otras ubicaciones |
| No transactions yet this session. | Aún no hay transacciones en esta sesión de caja. | Clave de compatibilidad del diccionario |
| No vacant rooms. | No hay habitaciones desocupadas. | screens/EndOfDayWizard.tsx |
| No zero-rate rooms tonight. | No hay habitaciones con tarifa cero para esta noche. | screens/EndOfDayWizard.tsx |
| No-show fee waived on {n} OTA booking(s). | Se exoneró el cargo por no presentación en {n} reservas de agencias en línea. | Clave de compatibilidad del diccionario |
| No-show policy | Política de no presentación | screens/EndOfDayWizard.tsx |
| No-shows and cancellations | No presentados y cancelaciones | screens/AuditPack.tsx |
| Noise / complaint | Ruido o queja | components/RoomChangeDialog.tsx |
| None held. | No hay reservas mantenidas por llegada tardía. | screens/AuditPack.tsx |
| None. | Ninguno. | screens/AuditPack.tsx |
| Not fired | Sin enviar a preparación | Clave de compatibilidad del diccionario |
| Not on the bill yet. Post it to the room, or the guest pays for it at the outlet. | Aún no está en la cuenta. Cárguelo a la habitación o cobre al huésped en el punto de venta. | Clave de compatibilidad del diccionario |
| Not ready to deliver yet | Aún no está listo para entregar | Clave de compatibilidad del diccionario |
| Not sent for {mins} min | Sin enviar desde hace {mins} min | Clave de compatibilidad del diccionario |
| Note | Nota | components/CancelPanel.tsx; components/CheckInDialog.tsx; components/ChildAges.tsx; otras ubicaciones |
| Occupancy & revenue | Ocupación e ingresos | screens/AuditPack.tsx |
| OK | Correcto | AppShell.tsx; screens/Inventory.tsx; screens/Kitchen.tsx; otras ubicaciones |
| One day later | Un día después | kamra/no_show.py; kamra/settings.py; kamra/kamra/doctype/property/property.json |
| Online check-in not sent | Enlace de registro en línea sin enviar | Clave de compatibilidad del diccionario |
| Online check-in sent, not filled | Enlace de registro en línea enviado, formulario sin completar | Clave de compatibilidad del diccionario |
| Open balance | Saldo pendiente | screens/AuditPack.tsx |
| Open cashier tills | Cajas de cajeros abiertas | kamra/night_audit.py |
| Open GRC | Abrir ficha de registro | Clave de compatibilidad del diccionario |
| Open order | Pedido abierto | Clave de compatibilidad del diccionario |
| Open outlet bills block the audit. Eyeball every bill posted to a room for a wrong-room posting. | Las cuentas abiertas de los puntos de venta bloquean la auditoría. Revise cada cuenta cargada a una habitación para comprobar que se asignó a la habitación correcta. | screens/EndOfDayWizard.tsx |
| Open restaurant bills | Cuentas de restaurante abiertas | kamra/night_audit.py; kamra/settings.py |
| Open restaurant bills block the audit | Las cuentas de restaurante abiertas bloquean la auditoría | kamra/settings.py |
| Open tills block the audit | Las cajas abiertas bloquean la auditoría | kamra/settings.py |
| Opened | Abierto | components/BookingDialog.tsx; components/CheckInDialog.tsx; components/CheckOutDialog.tsx; otras ubicaciones |
| Operations | Operaciones | lib/apps.ts; lib/searchIndex.ts; screens/OpsSLA.tsx; otras ubicaciones |
| Or jump to any screen. | O vaya directamente a cualquier pantalla. | Clave de compatibilidad del diccionario |
| Or pick another room | O seleccione otra habitación | Clave de compatibilidad del diccionario |
| OTA Room Mappings | Correspondencia de tipos de habitación con agencias en línea | lib/apps.ts; screens/configs.ts |
| Other | Otro | components/BookingDialog.tsx; components/CancelPanel.tsx; components/CheckOutDialog.tsx; otras ubicaciones |
| Other reason | Otro motivo | components/RoomDrawer.tsx |
| Other revenue | Otros ingresos | screens/AuditPack.tsx |
| Out of balance | Descuadrado | Clave de compatibilidad del diccionario |
| Out of order (repairs) | Fuera de servicio (reparaciones) | components/RoomDrawer.tsx |
| Out of order room has an in-house guest | Habitación fuera de servicio con un huésped alojado | kamra/night_audit.py |
| Outlet bills charged to rooms | Cuentas de puntos de venta cargadas a habitaciones | lib/eodFixes.ts |
| Outlets and room postings | Puntos de venta y cargos a habitaciones | kamra/night_audit.py |
| Over by | Exceso de | screens/EndOfDayWizard.tsx |
| Owner | Propietario | components/RoomDrawer.tsx; screens/configs.ts; screens/POS.tsx; otras ubicaciones |
| Owner stay | Estancia del propietario | components/RoomDrawer.tsx |
| PAN | PAN | components/GuestDocuments.tsx; lib/money.ts; screens/BanquetDiary.tsx |
| Part to move (percent, or {cur} before GST) | Importe a trasladar (porcentaje o importe en {cur} antes del GST) | Clave de compatibilidad del diccionario |
| Passed | Aprobado | screens/SystemHealth.tsx |
| Passport | Pasaporte | components/GuestDocuments.tsx; lib/money.ts |
| Pending | Pendiente | components/CheckOutDialog.tsx; components/ResourceScreen.tsx; lib/api.ts; otras ubicaciones |
| Pending Payment | Pago pendiente | components/ResourceScreen.tsx; screens/configs.ts; screens/PublicBooking.tsx |
| Per-item prices the app quotes and bills from. Blank express = 1.5× the normal rate. | Tarifas por prenda para cotizar y facturar. Si la tarifa exprés está en blanco, se aplica 1,5 veces la tarifa normal. | Clave de compatibilidad del diccionario |
| Pet Charge | Cargo por mascota | components/RoomStayPanels.tsx; screens/configs.ts; screens/FolioView.tsx |
| Phone App | Aplicación móvil | lib/apps.ts |
| Physical rooms - number, type, floor and live status. | Habitaciones físicas: número, tipo, piso y estado actual. | screens/configs.ts |
| Pickup requested, nothing collected yet: there is nothing to bill. | Se solicitó la recogida, pero aún no se han recibido prendas. No hay nada que facturar. | Clave de compatibilidad del diccionario |
| PIN code | Código postal | Clave de compatibilidad del diccionario |
| Placed | Registrado | kamra/checkout.py; kamra/night_audit.py; kamra/pos.py; otras ubicaciones |
| Policies | Políticas | lib/apps.ts; screens/BookingEngine.tsx; screens/PublicBooking.tsx; otras ubicaciones |
| Policy outcome | Resultado de la política | screens/AuditPack.tsx |
| posted {n} room night{s} ({amount}), opened {folios} folio{s2}, flagged {noShows} no-show{s3}. | se registraron {n} noche{s} de habitación ({amount}), se abrieron {folios} folio{s2} y se marcaron {noShows} no presentado{s3}. | Clave de compatibilidad del diccionario |
| Posts tonight's room charges for every in-house guest and flags no-shows. Runs automatically at 3 AM; run it manually anytime. | Registra los cargos de habitación de esta noche para los huéspedes alojados y marca a los no presentados. Se ejecuta automáticamente a las 3 a. m. y también puede iniciarlo manualmente. | Clave de compatibilidad del diccionario |
| Pre-checks and exceptions | Comprobaciones previas e incidencias | screens/AuditPack.tsx |
| Prepare End of Day | Preparar cierre del día | kamra/night_audit.py |
| Preparing | Preparando | screens/EndOfDayWizard.tsx; screens/pos/OrderHistory.tsx |
| Preview import | Vista previa de la importación | Clave de compatibilidad del diccionario |
| Print final reports | Imprimir informes finales | kamra/night_audit.py |
| Print KOT | Imprimir comandas | screens/POS.tsx |
| Print sheet | Imprimir hoja | Clave de compatibilidad del diccionario |
| Proceed to pay | Continuar con el pago | Clave de compatibilidad del diccionario |
| Property kind | Tipo de alojamiento | kamra/property_presets.py; kamra/settings.py |
| Property name | Nombre del alojamiento | screens/Setup.tsx |
| Property setup, inventory, users, audit and the Marketplace. | Configuración del alojamiento, inventario, usuarios, auditoría y catálogo de integraciones. | Clave de compatibilidad del diccionario |
| QR codes | Códigos QR | kamra/localization/saudi.py; kamra/zatca/__init__.py |
| Qty | Cant. | components/BookingDialog.tsx; lib/thermal.ts; screens/BanquetCatalogue.tsx; otras ubicaciones |
| Queen | Queen | screens/configs.ts |
| Rate check | Verificación de tarifas | kamra/night_audit.py |
| Rate Plans | Planes tarifarios | lib/apps.ts; lib/searchIndex.ts; screens/configs.ts |
| Rate variance | Diferencia de tarifa | screens/AuditPack.tsx |
| Rate variance tolerance | Tolerancia de diferencia de tarifa | kamra/settings.py |
| Rates, seasons, offers and the partners who sell you. | Tarifas, temporadas, ofertas y socios que comercializan su alojamiento. | lib/apps.ts |
| Registers | Registros | App.tsx; lib/apps.ts; screens/BanquetRegisters.tsx |
| Registration | Registro de huéspedes | App.tsx; components/CheckInDialog.tsx; components/RoomDrawer.tsx; otras ubicaciones |
| Release non-guaranteed arrivals at | Liberar las reservas de llegada sin garantía a las | kamra/settings.py |
| Released | Liberado | screens/configs.ts |
| Requested | Solicitado | components/ResourceScreen.tsx; lib/api.ts; screens/BanquetFunction.tsx; otras ubicaciones |
| Reset | Restablecer | components/CustomizeToday.tsx; screens/settings/AccessPages.tsx; screens/settings/ModulePage.tsx |
| Resolved | Resuelto | components/RoomDrawer.tsx; components/RoomStayPanels.tsx; screens/OpsSLA.tsx; otras ubicaciones |
| Restaurant | Restaurante | components/CheckInDialog.tsx; components/CheckOutDialog.tsx; lib/apps.ts; otras ubicaciones |
| Restaurant POS, kitchen display, the menu and kitchen stock. | Punto de venta del restaurante, pantalla de cocina, menú e inventario de cocina. | lib/apps.ts |
| Restaurant tables | Mesas del restaurante | Clave de compatibilidad del diccionario |
| Revenue controls | Controles de ingresos | Clave de compatibilidad del diccionario |
| Revenue Reports | Informes de ingresos | lib/apps.ts; screens/RevenueReports.tsx |
| Revenue today | Ingresos de hoy | Clave de compatibilidad del diccionario |
| Review the bill | Revisar la cuenta | kamra/sop.py |
| RevPAR {amount} | RevPAR {amount} | screens/Today.tsx |
| Room assignment | Asignación de habitación | Clave de compatibilidad del diccionario |
| Room board shows Occupied, no guest in house | Habitación marcada como ocupada en el panel, sin huésped alojado | kamra/night_audit.py |
| Room Levy | Tasa de alojamiento | screens/configs.ts |
| Room levy % | Tasa de alojamiento (%) | kamra/kamra/doctype/property/property.json |
| Room levy name | Nombre de la tasa de alojamiento | kamra/settings.py; kamra/kamra/doctype/property/property.json |
| Room nights posted off the booked rate, and rooms at zero rate. | Noches de habitación registradas con una tarifa distinta de la reservada y habitaciones con tarifa cero. | screens/EndOfDayWizard.tsx |
| Room number | Número de habitación | screens/configs.ts; screens/Rooms.tsx; screens/Setup.tsx |
| Room rate variances | Diferencias de tarifas de habitación | kamra/night_audit.py |
| Room Service | Servicio a la habitación | components/RoomStayPanels.tsx; screens/configs.ts; screens/Kitchen.tsx; otras ubicaciones |
| Room status | Estado de la habitación | lib/apps.ts; screens/Setup.tsx |
| Room status board, lost & found, and the phone app. | Panel de habitaciones, objetos perdidos y encontrados y aplicación móvil. | Clave de compatibilidad del diccionario |
| Room status discrepancies | Diferencias en el estado de habitaciones | kamra/night_audit.py |
| Room Types | Tipos de habitación | lib/apps.ts; screens/configs.ts; screens/Setup.tsx |
| Room {num} | Habitación {num} | Clave de compatibilidad del diccionario |
| Room {num} is assigned | Habitación {num} asignada | Clave de compatibilidad del diccionario |
| Rooms where the front office and the room board disagree. | Habitaciones cuyos datos de recepción no coinciden con el panel de habitaciones. | screens/EndOfDayWizard.tsx |
| Run and report exceptions | Ejecutar y registrar incidencias | kamra/folio.py; kamra/night_audit.py; kamra/settings.py |
| Run night audit | Ejecutar auditoría nocturna | Clave de compatibilidad del diccionario |
| Running… | Ejecutando… | Clave de compatibilidad del diccionario |
| Scan for in-room dining | Escanee para pedir servicio a la habitación | Clave de compatibilidad del diccionario |
| Scan to see the menu and order | Escanee para ver el menú y hacer un pedido | Clave de compatibilidad del diccionario |
| Scheduled | Programado | screens/BanquetFunction.tsx; screens/EndOfDayWizard.tsx |
| Scheduled 03:00 audit when checks block | Acción de la auditoría automática de las 03:00 si hay bloqueos | kamra/settings.py |
| Scheduler | Programador de tareas | kamra/folio.py; kamra/group_blocks.py; kamra/health.py; otras ubicaciones |
| Search a guest, phone, booking, invoice - or jump to any screen… | Busque un huésped, teléfono, reserva o factura, o vaya directamente a cualquier pantalla… | Clave de compatibilidad del diccionario |
| Search reservations, guests, rooms… | Buscar reservas, huéspedes, habitaciones… | Clave de compatibilidad del diccionario |
| Seasons | Temporadas | lib/apps.ts; lib/searchIndex.ts; screens/configs.ts; otras ubicaciones |
| Seats | Asientos | screens/configs.ts |
| Select… | Seleccionar… | Clave de compatibilidad del diccionario |
| Send and print | Enviar e imprimir | Clave de compatibilidad del diccionario |
| Send round | Enviar ronda | Clave de compatibilidad del diccionario |
| Send to kitchen | Enviar a cocina | Clave de compatibilidad del diccionario |
| SEO | SEO | lib/apps.ts; screens/BookingEngine.tsx; screens/PublicBooking.tsx |
| Sessions | Sesiones | App.tsx; lib/apps.ts; screens/CashierBoard.tsx; otras ubicaciones |
| Settle / post to room | Liquidar o cargar a la habitación | Clave de compatibilidad del diccionario |
| Settle bill | Liquidar cuenta | Clave de compatibilidad del diccionario |
| Severity | Gravedad | lib/eod.ts; screens/AuditPack.tsx; screens/EndOfDayWizard.tsx |
| SGST ({rate}%) | SGST ({rate}%) | Clave de compatibilidad del diccionario |
| Shared playground - not your hotel. Data is wiped every night. | Entorno de demostración compartido. Los datos se borran cada noche. | Clave de compatibilidad del diccionario |
| Shift Handover | Entrega de turno | lib/apps.ts; screens/configs.ts |
| Shifts | Turnos | Clave de compatibilidad del diccionario |
| Show closed | Mostrar cerrados | Clave de compatibilidad del diccionario |
| Show menus / exit full screen | Mostrar menús o salir de pantalla completa | Clave de compatibilidad del diccionario |
| Simplified Tax Invoice - municipality fees appear as a separate line where applicable. This is a computer-generated invoice. | Factura fiscal simplificada. Las tasas municipales aparecen en una línea separada cuando corresponda. Esta factura se generó electrónicamente. | Clave de compatibilidad del diccionario |
| Single | Individual | lib/auth.tsx; screens/configs.ts; screens/TapeChart.tsx |
| SLA Report | Informe de plazos de atención (SLA) | lib/apps.ts |
| Spa | Spa | components/BillingRulesEditor.tsx; components/CheckOutDialog.tsx; components/CommandPalette.tsx; otras ubicaciones |
| Split bill | Dividir cuenta | Clave de compatibilidad del diccionario |
| Start / accept | Iniciar o aceptar | Clave de compatibilidad del diccionario |
| Stayover Clean | Limpieza durante la estancia | screens/configs.ts |
| Still Due In. The next night audit marks them no-show if they have not checked in. | La llegada sigue pendiente de registrar. La próxima auditoría nocturna marcará al huésped como no presentado si aún no ha registrado su entrada. | Clave de compatibilidad del diccionario |
| Submit | Enviar | components/BookingRequests.tsx; components/HelpPanel.tsx; components/PinPad.tsx; otras ubicaciones |
| Submitted | Enviado | lib/api.ts; screens/PublicCheckin.tsx; screens/Today.tsx |
| Success | Correcto | App.tsx; screens/Agents.tsx; screens/BookingEngine.tsx; otras ubicaciones |
| System Admin | Administrador del sistema | screens/Login.tsx |
| Table | Mesa | lib/thermal.ts; screens/Agents.tsx; screens/AuditPack.tsx; otras ubicaciones |
| Table ordering and in-room dining codes for {property}. Drawn on this device - no outside QR service. | Códigos para pedidos desde mesas y habitaciones de {property}. Se generan en este dispositivo sin usar un servicio externo de códigos QR. | Clave de compatibilidad del diccionario |
| Takeaway | Para llevar | screens/Kitchen.tsx; screens/POS.tsx; screens/pos/OrderHistory.tsx |
| Tap menu items to add. | Toque los artículos del menú para agregarlos. | Clave de compatibilidad del diccionario |
| Tape Chart | Calendario de ocupación | components/RoomDrawer.tsx; lib/apps.ts |
| Tasks | Tareas | components/OpenTasksCard.tsx; lib/api.ts; lib/apps.ts; otras ubicaciones |
| Tax applies to the levy | Aplicar impuesto a la tasa de alojamiento | kamra/settings.py |
| Thank the guest, hand over any deposit refund, and wish them a safe journey. | Agradezca la visita al huésped, entregue el reembolso del depósito que corresponda y deséele buen viaje. | kamra/sop.py |
| Thank you for staying with us, safe travels, and we hope to welcome you again. | Gracias por alojarse con nosotros. Le deseamos buen viaje y esperamos recibirle nuevamente. | kamra/sop.py |
| the Data Protection Board of India | la Junta de Protección de Datos de la India | i18n/notice/bn.json; i18n/notice/hi.json; i18n/notice/kn.json; otras ubicaciones |
| the Saudi Data & AI Authority (SDAIA) | la Autoridad Saudí de Datos e Inteligencia Artificial (SDAIA) | kamra/localization/saudi.py |
| the UAE Data Office | la Oficina de Datos de los Emiratos Árabes Unidos | kamra/localization/uae.py |
| This blocks the audit. Resolve it, or acknowledge it with a reason - your name and the time are recorded on the audit. | Esto bloquea la auditoría. Resuélvalo o confirme la revisión indicando el motivo. Su nombre y la hora quedarán registrados en la auditoría. | Clave de compatibilidad del diccionario |
| This change re-prices the stay from {from} to {to}. Confirm the new price? | Este cambio modifica el total de la estancia de {from} a {to}. ¿Confirma el nuevo precio? | Clave de compatibilidad del diccionario |
| This is a computer-generated tax invoice under the GST Act. | Esta factura fiscal se generó electrónicamente conforme a la ley del GST. | kamra/localization/india/__init__.py |
| Time zone | Zona horaria | screens/Setup.tsx |
| Today's and past orders | Pedidos de hoy y anteriores | Clave de compatibilidad del diccionario |
| Transactions | Transacciones | screens/AuditPack.tsx; screens/EndOfDayWizard.tsx |
| Transfer | Transferencia | lib/money.ts; screens/BanquetFunction.tsx; screens/CityLedgerPayment.tsx; otras ubicaciones |
| Travel Agents | Agencias de viajes | lib/apps.ts; screens/configs.ts |
| Trial balance | Balance de comprobación | screens/AuditPack.tsx |
| Twin | Dos camas individuales | screens/configs.ts |
| Unknown | Desconocido | components/CheckInDialog.tsx |
| Update stay | Actualizar estancia | Clave de compatibilidad del diccionario |
| Upgrade | Mejora de categoría | components/CheckInDialog.tsx; components/RoomChangeDialog.tsx |
| Urgent | Urgente | components/RoomStayPanels.tsx; screens/configs.ts; screens/HkApp.tsx; otras ubicaciones |
| Vacant rooms | Habitaciones desocupadas | kamra/night_audit.py |
| Veg only | Solo vegetariano | Clave de compatibilidad del diccionario |
| Venue | Espacio para eventos | App.tsx; components/EventLinks.tsx; lib/api.ts; otras ubicaciones |
| Verified | Verificado | components/RoomDrawer.tsx; lib/api.ts; screens/configs.ts; otras ubicaciones |
| Verify restaurant & minibar charges | Verificar consumos de restaurante y minibar | kamra/sop.py |
| Version | Versión | screens/Login.tsx |
| VIP Hold | Bloqueo VIP | components/RoomDrawer.tsx; screens/configs.ts |
| VIP hold | Bloqueo VIP | components/RoomDrawer.tsx |
| Void line | Anular línea | Clave de compatibilidad del diccionario |
| Voter ID | Documento de identidad electoral | components/GuestDocuments.tsx; lib/money.ts |
| Walk the guest through every open folio: room nights, extras, and credits. | Revise con el huésped cada folio abierto: noches de alojamiento, extras y abonos. | kamra/sop.py |
| warn | advertir | components/BookingDialog.tsx; components/CheckInDialog.tsx; components/CheckOutDialog.tsx; otras ubicaciones |
| Warning | Advertencia | components/CheckOutDialog.tsx; screens/AuditPack.tsx |
| Website | Sitio web | screens/BookingEngine.tsx; screens/banquet/shared.tsx |
| Were there any restaurant or minibar charges we should check? | ¿Hay algún consumo de restaurante o minibar que debamos revisar? | kamra/sop.py |
| When a captain sends an order, the kitchen ticket prints immediately and the order shows on the kitchen display as started. Leave this off if the kitchen must press Start. | Cuando el jefe de servicio envía un pedido, la comanda se imprime de inmediato y aparece como iniciada en la pantalla de cocina. Desactive esta opción si el personal de cocina debe pulsar «Iniciar». | Clave de compatibilidad del diccionario |
| Wish farewell | Despedir al huésped | kamra/sop.py |
| Wrong email or password. | Correo electrónico o contraseña incorrectos. | Clave de compatibilidad del diccionario |
| {guest} · open registration | {guest} · abrir ficha de registro | Clave de compatibilidad del diccionario |
| {n} A4 pages | Páginas A4: {n} | Clave de compatibilidad del diccionario |
| {n} booking{s} imported{history} | {n} reserva{s} importada{s}{history} | Clave de compatibilidad del diccionario |
| {n} codes | Códigos: {n} | Clave de compatibilidad del diccionario |
| {n} due | Pendientes de pago: {n} | Clave de compatibilidad del diccionario |
| {n} overdue | Vencidos: {n} | screens/Today.tsx |
| {type} · settled | {type} · liquidado | screens/FolioView.tsx |
