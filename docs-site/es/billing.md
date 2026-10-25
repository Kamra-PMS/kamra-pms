# Facturación: folios, pagos y la caja

Cada estancia tiene un folio: la cuenta abierta donde se cargan las noches
de habitación, las cuentas del restaurante y los extras, y donde se
registran los pagos. Esta página trata del folio, la caja del cajero, los
depósitos, las facturas, las cuentas de empresa y los libros contables.
Aquí trabaja el personal de Recepción y de Finanzas; las notas de crédito,
los pagos de empresas y la exportación contable son para Finanzas y el
Administrador del hotel.

![Un folio de huésped: la barra de acciones arriba, la cuenta provisional con cada cargo, su impuesto y su total, un resumen por tipo de cargo y el resumen de impuestos](/img/billing/folio.png)

Los importes, los tipos de impuesto y los modos de pago de esta página
vienen del hotel de ejemplo en la India. Los suyos vienen de su paquete de
país: consulte [Country setup](/country-setup).

## Antes de empezar

1. **Abra su caja.** Los pagos, los reembolsos y las facturas se rechazan
   hasta que tenga una sesión de caja abierta: consulte [Abrir y cerrar su caja](#abrir-y-cerrar-su-caja).
2. **Decida si usa un PIN de caja.** **Configuración → Finanzas → Controles de caja →
   Exigir PIN de caja para operaciones de dinero**. Si está activado, cada persona define un
   PIN la primera vez que cobra dinero, y las operaciones de dinero lo vuelven a pedir
   cuando termina el tiempo de desbloqueo. Está desactivado por defecto.
3. **Conecte una pasarela de pago** si quiere enviar enlaces de pago:
   **Configuración → Pagos**. Las pasarelas disponibles dependen de su paquete
   de país.
4. **Configure la facturación a empresas** si tiene empresas con crédito:
   **Configuración → Finanzas → Facturación a empresas** (consulte
   [Folios de empresa](#facturar-a-una-empresa)).

## Buscar un folio

Abra **Finanzas → Facturación**. La lista **Folios** muestra todos los folios del
alojamiento, del más reciente al más antiguo, con su estado, número de factura, total, importe pagado y
saldo. Pulse una fila para abrir el folio. También puede llegar al folio de una estancia
desde la reserva.

**Finanzas → Historial del folio** muestra las cuentas y facturas cerradas. Busque por
huésped, factura o folio, filtre por estado, o indique **Cerrado desde** y
**A** para ver las cuentas cerradas en un rango de fechas.

![La pantalla de Facturación: accesos directos a Cierre del día y Mi caja, y la lista de folios con sus saldos](/img/billing/billing-list.png)

El folio se abre solo al registrar la entrada. Hasta que se liquida, es una
**Cuenta provisional** sin número de factura.

## Registrar un cargo

1. Abra el folio y baje hasta **Registrar un cargo**.
2. Elija el tipo de cargo (**Alimentos y bebidas**, **Minibar**, **Lavandería**,
   **Spa**, **Entrada anticipada**, **Salida tardía**, **Cargo por mascota**,
   **Descuento** o **Varios**).
3. Escriba una descripción y el importe sin impuestos.
4. Elija el tipo de impuesto. Para cargos de comida, bebida y minibar no hay
   elección: el formulario muestra el tipo de alimentos y bebidas de su paquete de país, por
   ejemplo **GST 5% (F&B rate)**. Marque **Alcohol** para las bebidas con
   alcohol; estas llevan el tipo que usted elija. El nombre del impuesto (GST, IVA…) depende de
   su paquete de país.
5. Pulse **Registrar**.

![Las tarjetas Registrar un cargo y Registrar un pago bajo la cuenta: un cargo de minibar muestra el tipo fijo de GST 5% para alimentos y bebidas, con la fila de bonificación debajo](/img/billing/post-charge.png)

Las noches de habitación, los planes de comidas y las tasas de alojamiento no se registran a mano: la
[auditoría nocturna](/es/night-audit) los registra cada noche. Las cuentas del restaurante
cargadas a una habitación llegan desde el [punto de venta](/es/fnb).

## Cobrar un pago

1. Abra el folio y baje hasta **Registrar un pago**.
2. Elija qué es el dinero:
   - **Pago**: a cuenta de la factura.
   - **Anticipo**: se cobra antes de la entrada o al registrarla. Paga la estancia.
   - **Depósito de garantía**: se retiene y es reembolsable, no es ingreso. Consulte
     [Depósitos de garantía](#cobrar-y-devolver-un-deposito-de-garantia).
3. Elija el modo (efectivo, tarjeta y los demás modos de su paquete de país).
   El importe se rellena con el saldo; cámbielo para un pago parcial.
4. Añada una referencia (comprobante de tarjeta, número de transferencia) si la tiene.
5. Pulse **Registrar**. El saldo al pie de la cuenta se actualiza.

![Registro de un pago UPI por el saldo de un folio, y el saldo que baja a cero](/img/billing/take-payment.gif)

Cada pago también entra en su sesión de caja, así que el
[informe de turno](#contar-el-efectivo-y-cerrar-la-caja) y los libros contables lo incluyen.

**Envíe un enlace de pago.** Cuando el folio tiene saldo y hay una
pasarela conectada, **Enlace de pago** en la barra de acciones crea un enlace
por el saldo y lo copia, listo para pegarlo al huésped (o a quien reservó,
si la reserva indica contactar a esa persona). Cuando el huésped paga, el
pago se registra solo en el folio.

**Reembolsar dinero.** En la salida no lo necesita: el paso **Pago** de la hoja de salida
calcula el reembolso, sugiere el modo por el que entró el dinero
y devuelve el depósito de garantía retenido con el reembolso propio del
depósito (consulte [Recepción](/es/front-desk)). Para cualquier otro reembolso, bajo la
lista de pagos, **Reembolsar dinero (devolución de depósito o cobro en exceso)** abre una
fila de reembolso: importe, modo y un motivo, y luego **Reembolso**. No puede reembolsar
más de lo cobrado en el folio, y un folio cerrado no admite
reembolsos. Cada reembolso queda en el registro de actividad con su nombre.

## Corregir un cargo

**Anular** elimina una línea errónea (importe equivocado, duplicado, huésped equivocado):

1. En la línea del cargo, pulse **Anular**.
2. Escriba el motivo. Es obligatorio y queda registrado.
3. Pulse **Confirmar anulación**.

![Anulación de un cargo de lavandería: el cuadro del motivo y el botón Confirmar anulación en la línea](/img/billing/void.png)

**Aplique una bonificación** cuando el cargo era correcto pero usted devuelve
dinero (compensación por un mal servicio, una reclamación): bajo **Registrar un cargo**, rellene la
fila **Aplicar una bonificación** con el importe, el tipo de impuesto del cargo que
compensa y un motivo, y pulse **Permitir**. La línea original sigue en la
cuenta y la bonificación aparece como una línea en negativo, así el historial queda claro.

Las anulaciones solo funcionan en un folio abierto. Cuando el folio ya está facturado, use una
[nota de crédito](#anular-una-factura-o-emitir-una-nota-de-credito).

## Dividir o trasladar cargos a otro folio

Una estancia puede tener más de un folio: el folio de **Huésped**, un folio de **Empresa**,
folios de **Extra** y, para grupos, un folio de **Grupo**. Aparecen como
pestañas sobre la cuenta, cada una con su saldo.

1. Marque las líneas que quiere trasladar, o pulse **Mover** en una línea.
2. Para trasladar solo una parte de una línea, escriba un porcentaje (`30%`) o un
   importe sin impuestos (`1500`) en el cuadro junto a **solo trasladar**.
3. En **Enviar … a**, elija el folio, o **+ Nuevo folio de empresa** /
   **+ Nuevo folio de extras** para crear uno y trasladar las líneas a él.

![Una línea de spa seleccionada, 50% escrito en el cuadro de traslado parcial, y los botones para enviarla a un nuevo folio de empresa o de extras](/img/billing/move-charges.png)

**Dividir folio** en la barra de acciones añade un folio vacío a la estancia (primero un
folio de empresa, después folios de extras). Un folio de empresa o de extras vacío
se puede eliminar con la **×** de su pestaña.

## Facturar a una empresa

Cuando una estancia se reserva para una empresa, Kamra envía cada cargo al
folio correcto en el momento de registrarlo:

- Las **reglas de facturación** propias de la empresa deciden qué tipos de cargo paga
  (se definen en la empresa en **Ingresos → Empresas**, donde también se marca **Crédito
  permitido (cuentas por cobrar a empresas)**).
- Una empresa con crédito sin reglas usa **Configuración → Finanzas → Facturación
  a empresas**. La opción por defecto, **Habitación y alimentos y bebidas (alcohol a cargo del huésped)**, factura a la empresa la
  noche de habitación, su plan de comidas, las tasas, la entrada anticipada o salida tardía,
  el cargo de limpieza y la comida; lavandería, minibar, spa y varios
  quedan a cargo del huésped. **Nada (paga el huésped salvo que las reglas indiquen otra cosa)** desactiva
  la opción por defecto.
- El alcohol nunca va a un folio de empresa ni de grupo. Kamra se niega a registrarlo
  o trasladarlo allí.

En la salida, el huésped liquida su propio folio. Lo que debe la empresa
pasa solo a su cuenta de **cuentas por cobrar a empresas**, si la empresa
tiene crédito permitido.

**Registrar el pago de una empresa** (Finanzas y Administrador del hotel):

1. Abra **Finanzas → Libros contables**. **Antigüedad de cuentas por cobrar a empresas** muestra el saldo de cada empresa
   por antigüedad (0-30, 31-60, 61-90, más de 90 días) y el saldo a favor sin aplicar.
2. Pulse **Registrar pago** en la fila de la empresa.
3. Indique el **Importe recibido**, el **Modo** y la **Referencia (UTR /
   n.º de cheque)**. Por defecto, el pago salda primero las facturas más antiguas;
   también puede escribir el importe de cada factura.
4. Pulse **Revisar pago**, compruebe lo que salda y luego pulse **Confirmar**.

El dinero sobrante queda en la cuenta como saldo a favor sin aplicar y paga la
siguiente factura de la empresa de forma automática.

## Cobrar y devolver un depósito de garantía

Un depósito reembolsable por daños (villas, estancias largas) se retiene para el huésped
y no cuenta como ingreso. El panel **Depósito de garantía** está en el
panel lateral de la reserva de una estancia próxima o en curso. El importe que espera el alojamiento
se define en **Configuración → Políticas de estancia → Anticipos y depósitos de garantía → Depósito de garantía**
(0 significa que no se pide).

![El panel Depósito de garantía: importes requerido, retenido, descontado y reembolsado, y los botones Cobrar un importe adicional, Retener por daños y Reembolsar depósito de garantía](/img/billing/security-deposit.png)

- **Cobrar depósito de garantía**: importe, modo de pago y, si quiere, un comprobante de tarjeta o
  una referencia de transferencia. Pasa por la caja como cualquier pago.
- **Exonerar depósito de garantía**: no se cobra dinero; el motivo es obligatorio.
- **Retener por daños**: registra un cargo por daños en el folio con su
  motivo; el depósito retenido lo paga.
- **Reembolsar depósito de garantía**: devuelve lo que sigue retenido, antes de la salida.

Un depósito cobrado desde el formulario **Registrar un pago** del folio (tipo
**Depósito de garantía**) aparece en el mismo panel.

Los **anticipos de reserva** (un pago adelantado antes de la llegada) se cobran desde el panel
**Anticipo de reserva** de la reserva: consulte [Reservas](/es/reservations).

## Cerrar el folio e imprimir la factura

1. Asegúrese de que el saldo es cero: cobre lo que se debe, reembolse un
   pago en exceso o deje que la parte de la empresa pase a cuentas por cobrar a empresas.
2. Pulse **Cerrar y generar factura**. Kamra asigna el siguiente número de factura
   de la serie del alojamiento y la cuenta pasa a ser una **Factura
   fiscal**.
3. Pulse **Imprimir factura**, o elija **Guardar como PDF** en el cuadro de impresión.

El título de la factura, las líneas de impuestos y el texto vienen del paquete de país. En
Arabia Saudí, una cuenta liquidada se imprime como *factura simplificada* con el
código QR de ZATCA; configure los datos del vendedor una vez en **Configuración → Facturación
electrónica ZATCA** ([Country setup](/country-setup)).

![Un folio cerrado impreso como Factura fiscal con su número de factura, líneas, resumen y resumen de impuestos](/img/billing/tax-invoice.png)

Otros botones de la barra de acciones:

- **Imprimir folio** imprime la cuenta provisional de un folio abierto.
- **Proforma** guarda una copia proforma de la cuenta tal como está y la imprime.
- **Facturar por adelantado** registra ahora las noches de habitación que faltan de la estancia,
  antes de la auditoría nocturna (para un huésped que quiere pagar todo por
  adelantado).
- **Liquidar y continuar estancia** aparece cuando un folio abierto está totalmente pagado.
  Emite una factura parcial por lo que contiene y abre un folio nuevo para
  el resto de la estancia: la forma habitual de liquidar cada pocos días en estancias largas.
  La pestaña del folio liquidado muestra entonces **Huésped ·** seguido de su número de
  factura; la pestaña del folio nuevo es **Huésped**.
- **Folio del grupo** (estancias de grupo) abre una única cuenta de empresa consolidada para
  todas las habitaciones del grupo.

## Anular una factura o emitir una nota de crédito

**Anular factura** (en un folio cerrado): escriba el motivo y pulse
**Confirmar cancelación**. El número de factura pasa al registro de
facturas anuladas, la cuenta anterior se puede seguir imprimiendo y el folio se reabre para que pueda
corregirlo y cerrarlo de nuevo con un número nuevo. Donde el país no
permite anular (Arabia Saudí), el paquete emite una nota de crédito
en su lugar.

**Nota de crédito** (Finanzas y Administrador del hotel, en un folio facturado): indique el
importe y el motivo. Kamra numera la nota de crédito con referencia a la factura
original. En una estancia de empresa que ya pasó a cuentas por cobrar a empresas, el
crédito reduce el saldo de la empresa.

## Abrir y cerrar su caja

Cada cajero tiene una sesión de caja por fecha operativa.

1. Abra **Finanzas → Mi caja**.
2. Indique el **Fondo inicial de caja** (el efectivo del cajón) y pulse
   **Abrir sesión de caja**.

![La tarjeta para abrir caja en Mi caja, con el fondo inicial y el botón Abrir sesión de caja](/img/billing/open-till.png)

Mientras la sesión está abierta, **Mi caja** muestra el fondo, el efectivo, la tarjeta y
otros cobros, los egresos, las entregas a caja central, la caja chica y el **Efectivo esperado** en
el cajón, con las transacciones recientes de la sesión debajo.

![Mi caja con una sesión abierta: fondo, efectivo recibido, tarjeta, egresos, caja chica y efectivo esperado, los formularios Egreso de caja y Entrega de efectivo a caja central, y Cerrar caja](/img/billing/my-till.png)

- **Egreso de caja**: efectivo que sale del cajón para un huésped o un proveedor. Importe y
  motivo, y luego **Registrar**.
- **Entrega de efectivo a caja central**: lleva efectivo a la caja fuerte. Importe, y luego **Entregar efectivo a caja central**.

## Contar el efectivo y cerrar la caja

1. En **Cerrar caja**, escriba el efectivo que ha contado. Kamra muestra la
   **Variación** frente al efectivo esperado mientras escribe.
2. Pulse **Cerrar sesión**.

Finanzas y el auditor nocturno también pueden cerrar la caja de otra persona, en el
paso **Cierre de caja** del [Cierre del día](/es/night-audit). **Finanzas →
Sesiones** muestra todas las sesiones con su fondo, el efectivo esperado y el contado,
y la variación.

El **Informe de turno** (**Informes → Informe de turno**) muestra cada sesión de una
fecha operativa con su efectivo, tarjeta y variación, y un diario de las
transacciones del día por tipo y modo. Indique la segunda fecha para abarcar varias
fechas operativas (hasta 92 días).

![El Informe de turno: la sesión de un cajero y el diario por tipo y modo](/img/billing/shift-report.png)

## Pagar gastos menores con caja chica

1. Abra **Finanzas → Caja chica** (o **Caja chica →** en Mi caja).
2. Rellene el **Beneficiario**, el **Importe**, una categoría (**Suministros**,
   **Mantenimiento**, **Transporte**, **Bienestar del personal**, **Varios**)
   y el **Motivo**.
3. Pulse **Registrar vale**. El efectivo sale de su caja abierta.

![La pantalla Caja chica con el formulario de vale nuevo y un vale registrado](/img/billing/petty-cash.png)

## Cambiar moneda extranjera

1. Abra **Finanzas → Cambio de moneda**.
2. Elija la moneda y la operación: **Compra (el huésped vende divisas)** o
   **Venta (el huésped compra divisas)**, y el importe en moneda extranjera.
3. Pulse **Calcular** para ver el tipo de cambio y el importe en moneda local, y luego **Registrar
   cambio de moneda**. El efectivo local pasa por su caja.

![Cambio de moneda: la calculadora con 100 USD al tipo de compra, la tabla de tipos y los cambios de hoy](/img/billing/currency-desk.png)

Finanzas y el Administrador del hotel definen los tipos de compra y venta en **Establecer tipo de cambio**
(moneda, compra, venta, y luego **Guardar**).

## Revisar los libros contables

**Finanzas → Libros contables** muestra los cuatro libros de folios de una fecha: **Huésped**
(lo que deben los huéspedes alojados), **Anticipo de reserva** (anticipos y depósitos de garantía
retenidos), **AR** (lo que deben las empresas, cuentas por cobrar) y **Paquete**. Debajo están el
diario por código de transacción y la antigüedad de cuentas por cobrar a empresas.

![La pantalla Libros contables: el aviso verde que indica que los libros coinciden con los folios, los cuatro libros, el diario por código de transacción y la antigüedad de cuentas por cobrar a empresas](/img/billing/ledgers.png)

El aviso de arriba compara los libros con los folios de la
fecha operativa actual. **Los libros coinciden con los folios** significa que los libros de Huésped y de
Anticipo de reserva suman lo que tienen los folios. Los débitos superan a los
créditos en lo que deben los huéspedes; es lo esperado. Si un folio no coincide,
el aviso se pone ámbar y lo muestra (consulte
[Solución de problemas](#solucion-de-problemas)). Para cualquier otra fecha solo muestra los totales.

Cada cargo, pago, anulación, traslado y bonificación genera un asiento en el libro.
Una anulación o un traslado no borra el historial: registra un asiento inverso.

## Códigos de transacción y códigos de motivo

**Finanzas → Códigos de transacción** es el catálogo de códigos de cargo y de pago
del folio (grupo de ingresos, impuesto por defecto, indicador de alcohol). Si el alojamiento está en blanco, el código vale para todos
los alojamientos. Kamra crea códigos por defecto; añada uno solo cuando su contabilidad lo necesite.
Desactívelo en lugar de eliminarlo si el diario ya lo usó.

**Finanzas → Códigos de motivo** guarda motivos codificados para anulaciones, reembolsos,
bonificaciones, cambios de tarifa y egresos de caja. Kamra incluye motivos por defecto; añada aquí
los códigos propios del alojamiento. Un código marcado como **Requiere supervisor** necesita
a Finanzas o al Administrador del hotel cuando se usa.

Las dos pantallas también están enlazadas desde **Configuración → Finanzas**.

## Revisar anulaciones y bonificaciones

**Informes → Anulaciones y bonificaciones**
muestra cada anulación, bonificación y factura anulada del alojamiento: cuándo,
en qué folio, quién lo hizo y el motivo. Lo ven los usuarios de Finanzas y el
Administrador del hotel.

1. Indique las fechas. Al principio muestra los últimos 30 días.
2. Pulse **Anular**, **Bonificación** o **Factura anulada** para ver un solo tipo;
   **Todos** los muestra todos, con el número de cada uno.
3. Busque por folio, nombre del empleado o motivo. Pulse un folio para abrirlo.
4. Pulse **Imprimir** para obtener una copia en papel.

![Anulaciones y bonificaciones: el rango de fechas, los filtros con sus cifras y cada anulación, bonificación y factura anulada con su folio, quién lo hizo y el motivo](/img/billing/voids-allowances.png)

## Configuración

| Opción | Dónde | Valor por defecto | Qué hace |
| --- | --- | --- | --- |
| Gestionar dinero mediante cajas | Configuración → Finanzas → Controles de caja | Activado | El personal abre su caja (con un fondo inicial) antes de cobrar o devolver dinero, y la cierra con un recuento de efectivo. Las hojas de entrada, de llegada sin reserva y de salida ofrecen **Abrir mi caja** en el momento. Desactivado, para un establecimiento pequeño sin cajón de efectivo: los pagos y reembolsos se registran sin caja; los egresos, las entregas a caja central, la caja chica y el cambio de moneda siguen necesitando una. |
| Exigir PIN de caja para operaciones de dinero | Configuración → Finanzas → Controles de caja | Desactivado | Los pagos, las facturas, las bonificaciones, las anulaciones, los reembolsos y las acciones de caja piden el PIN del cajero. Los agentes de IA están exentos; sus acciones quedan registradas. |
| Bloquear un PIN después de | Configuración → Finanzas → Controles de caja | 5 intentos fallidos | Bloquea el PIN tras este número de intentos fallidos. |
| Duración del bloqueo / desbloqueo | Configuración → Finanzas → Controles de caja | 15 min | Cuánto tiempo sigue bloqueado un PIN bloqueado, y cuánto tiempo siguen desbloqueadas las operaciones de dinero tras un PIN correcto. |
| Cuando una empresa con crédito no tiene reglas de facturación | Configuración → Finanzas → Facturación a empresas | Habitación y alimentos y bebidas (alcohol a cargo del huésped) | Qué cargos paga una empresa con crédito cuando no tiene reglas propias. |
| Pasarela de pago | Configuración → Pagos | Ninguno | La pasarela y las claves que se usan para los enlaces de pago. |

## Conviene saber

- **Un folio solo se cierra en cero.** Kamra no cierra un folio mientras
  se deba dinero, ni mientras se deba un reembolso al huésped.
- **Los impuestos son una regla del hotel, no del cajero.** Los cargos de comida, bebida y
  minibar llevan el tipo de alimentos y bebidas de su paquete de país, así que el formulario
  muestra ese tipo en lugar de una elección. Un cargo debe ser un importe positivo
  con uno de los tipos de impuesto de su paquete; para reducir una cuenta, anule o aplique una
  bonificación.
- **Toda anulación, bonificación y anulación de factura necesita un motivo** y queda
  registrada con quién la hizo. Finanzas puede verlas todas en
  [Anulaciones y bonificaciones](#revisar-anulaciones-y-bonificaciones).
- **Los cargos solo se trasladan dentro de una estancia** (o dentro de un grupo), y solo
  entre folios abiertos.
- **Un folio de Huésped o de Grupo no se puede eliminar**, ni tampoco ningún folio con cargos
  o pagos.
- **El tiempo de desbloqueo es por persona.** Tras un PIN correcto, las
  operaciones de dinero de esa persona siguen abiertas durante el tiempo de desbloqueo en cualquier pantalla.

## Solución de problemas

**"NO_OPEN_SESSION: open your till under Finance → Cashier first."** Abra
su caja en **Finanzas → Mi caja** y vuelva a intentarlo.

**"Cannot close the folio: … is still owed."** Cobre el saldo, o
traslade la parte de la empresa a su folio para que pase a cuentas por cobrar a empresas en
la salida.

**No aparece el botón Enlace de pago.** Solo aparece en un folio abierto
con saldo, en un país cuyo paquete tenga pasarelas de pago. Si al pulsarlo
indica que no hay ninguna pasarela configurada, configure una en **Configuración → Pagos**.

**"Alcohol cannot be billed to a company folio."** Registre o traslade la bebida
al folio propio del huésped.

**El aviso de Libros contables dice "Ledger differs from folios".** El aviso
comprueba que los libros de Huésped y de Anticipo de reserva coinciden con el saldo de cada folio,
para la fecha operativa actual. Si no coinciden, muestra cada
folio con diferencias, con el saldo del folio y el saldo del libro: un
registro llegó al folio pero no al libro, o al revés.
Abra el folio desde el enlace y compare sus líneas con el diario.
Que los débitos superen a los créditos no es un problema por sí solo: es lo que
los huéspedes aún deben.

## Para desarrolladores

Las acciones del folio son herramientas MCP para agentes de IA (`get_folio`,
`add_folio_charge`, `record_payment`, `void_charge`, `apply_allowance`,
`move_charges`, `split_folio_charge`, `close_folio`, `send_payment_link`,
`collect_security_deposit` y más): consulte [MCP tools](/mcp-tools#billing).
Los endpoints REST están en `kamra.api` (folios, pagos, depósitos),
`kamra.cashier` (sesiones de caja, caja chica, informe de turno) y
`kamra.ledger` (libros contables, cuentas por cobrar a empresas, notas de crédito, proforma, cambio de moneda). La
pantalla **Anulaciones y bonificaciones** lee `kamra.reports.void_allowance_report`
(Finanzas, Administrador del hotel). Consulte la
[API reference](/api-reference#core-front-desk-folios-guests-rooms) y
[Ledgers](/api-reference#ledgers-trial-balance-city-ledger-ar-fx-desk).
