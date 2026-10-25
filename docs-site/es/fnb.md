# Alimentos y bebidas: punto de venta del restaurante y cocina

El módulo de Alimentos y bebidas gestiona sus restaurantes, bares y
servicio a la habitación: los jefes de sala toman pedidos en el **Punto
de venta del restaurante**, la cocina trabaja con la **Pantalla de
cocina** y las **impresoras de cocina**, y las cuentas se liquidan en el
punto de venta o se cargan a la habitación del huésped. El personal de
Recepción y Finanzas puede usar el punto de venta; Administrador del
hotel y Finanzas lo configuran.

![El punto de venta del restaurante: las cuentas abiertas arriba, el menú por categoría en el centro y la cuenta en curso de la mesa T2 a la derecha](/img/fnb/pos-bill.png)

## Antes de empezar

1. **Active el módulo.** **Configuración → Alimentos y bebidas → Módulo
   activado**. Cuando está desactivado, se ocultan las pantallas de
   Alimentos y bebidas y sus herramientas para agentes de IA.
2. **Agregue sus puntos de venta.** **Alimentos y bebidas → Puntos de
   venta → Nuevo**: un nombre, el tipo (Restaurante, Servicio a la
   habitación, Bar, Spa, Otro), el tipo de impuesto y las mesas. Escriba
   una mesa por línea como `name:seats` (nombre:asientos), y agrúpelas con una zona
   entre corchetes:

   ```
   [Main Hall]
   T1:2
   T2:4
   [Patio]
   P1:2
   ```

   ![La ficha de un punto de venta con su tipo, tipo de impuesto, mesas y el ajuste Comanda al enviar](/img/fnb/outlet-form.png)

3. **Defina las listas del menú (una sola vez).** **Configuración →
   Alimentos y bebidas → Listas del menú**: alérgenos y etiquetas
   alimentarias (Huevo, Lácteos, Frutos secos…), estaciones de
   preparación, tiempos del menú y sugerencias de categoría. Edite las
   listas aquí; todos los formularios de **Nuevo menú** y la pantalla de
   cocina las usan. Agregue Huevo, Jain, Sin gluten o lo que necesite su
   cocina, sin cambiar código.

4. **Cree el menú.** **Alimentos y bebidas → Menú**. Cada plato tiene un
   precio, un punto de venta, una categoría, vegetariano o no, una foto,
   un **tiempo del menú**, una **estación de preparación** y **etiquetas
   de alérgenos** de la lista del menú. La estación decide qué impresora
   de cocina recibe el plato y con qué filtro de estación aparece en la
   pantalla de cocina. Para cargar un menú completo de una vez, use
   **Importación en lote** en la pantalla Menú: suba una hoja de cálculo,
   revise la vista previa y ejecútela.

   ![La lista del menú con fotos, precios, puntos de venta y estaciones](/img/fnb/menu.png)

5. **Decida cómo llegan las comandas a la cocina.** Consulte
   [Impresoras de cocina](#impresoras-de-cocina) y
   [Aceptar e imprimir automáticamente](#aceptar-e-imprimir-comandas-automaticamente)
   más abajo. Sin nada configurado, la cocina trabaja con la pantalla de
   cocina y cada caja puede imprimir sus propias comandas.

## Tome un pedido y envíelo a la cocina

1. Abra **Alimentos y bebidas → Punto de venta del restaurante** y elija
   el punto de venta en la parte superior.
2. Pulse **Nueva cuenta** (o **F2**). Elija **Consumo en el local**,
   **Servicio a la habitación**, **Para llevar** o **Entrega a
   domicilio** arriba a la derecha.
3. Para consumo en el local, elija la mesa (en el plano de mesas o en la
   lista **Mesa...**) y el número de comensales. Para llevar y entrega a
   domicilio, introduzca el nombre y el teléfono del cliente, y la
   dirección para la entrega.
4. Toque los platos para agregarlos. Use **+** / **−** en una línea para
   cambiar la cantidad, y agregue una indicación a una línea ("menos
   picante") si hace falta.
5. Pulse **Enviar a cocina** (o **F6**). El pedido recibe un número de
   comanda, aparece en la pantalla de cocina y se imprime donde estén
   configuradas sus impresoras.

![Toma de un pedido para consumo en el local en la mesa T7 y envío a la cocina](/img/fnb/send-order.gif)

La barra bajo el menú muestra lo ocurrido: *"Comanda 4 enviada a Cocina
principal"*, o *"Comanda 4 impresa y en la pantalla de cocina"* cuando la
imprime la caja.

**Otra ronda** en una cuenta abierta: abra la cuenta (toque su recuadro,
o **F3** para recorrer las cuentas abiertas), agregue los platos y pulse
**Enviar ronda**. Solo las líneas nuevas van a la cocina.

**Deje una cuenta pendiente** sin enviarla (**F5**) cuando los clientes
aún están decidiendo. Queda en **Cuentas abiertas → Abierto, no enviado a
la cocina**, con el tiempo que lleva esperando. Después de 15 minutos
(puede cambiarlo en **Configuración → Alimentos y bebidas**), la cuenta
se pone roja en la caja y aparece un punto rojo en **Pedidos**, para que
un pedido olvidado se envíe o se cancele. El Cierre del día la muestra
como *abierta, no enviada a la cocina*.

## El plano de mesas

Cada recuadro de mesa muestra su estado: **Desocupada**, **En servicio**
(cuenta abierta, sin enviar), **En la cocina**, **Listo**, **Reservada**
o **Limpieza**, con el total en curso, los comensales y los minutos desde
el pedido. Filtre por zona (Salón principal, Patio…) o busque una mesa.

- **Varias cuentas en una mesa.** Dos grupos que comparten mesa tienen
  cada uno su propia cuenta: abra la mesa y pulse **+ cuenta**.
- **Mesas temporales.** **+ Mesa temporal** crea una mesa en el momento
  (un cliente sin reserva en el jardín). Aparece como recuadro hasta que
  se liquida.
- **Reservas.** **+ Reservar** reserva una mesa con huésped, teléfono,
  número de personas y hora. El recuadro muestra "Res 19:30" desde una
  hora antes (puede cambiar ese margen en **Configuración → Alimentos y
  bebidas**), con las acciones **Asignar mesa ahora**, **No presentado**
  y **Cancelar**.
- **Limpieza.** Una mesa liquidada pasa a **Limpieza** hasta que alguien
  la marca como limpia o pasan 30 minutos.

## Liquide una cuenta

1. Abra la cuenta y pulse **Liquidar** (o **F4**).
2. Elija cómo paga el cliente: **Efectivo**, **Tarjeta** o **UPI**. O
   cárguela a la habitación de un huésped alojado con **Cargo a
   habitación**.
3. **Imprimir cuenta** imprime la cuenta en la impresora de la caja, con
   el desglose de impuestos que usa su país.

- Los **cargos a habitación** necesitan un huésped con entrada registrada
  en esa habitación. Una habitación sin nadie alojado se rechaza: cobre
  la cuenta como cliente de paso. La cuenta se carga al folio del huésped
  cuando se entrega; el alcohol siempre va al folio propio del huésped,
  nunca a una empresa que paga la habitación.
- **Cargos a habitación bloqueados en el registro de entrada.** Si la
  recepción desactivó los cargos a habitación para una estancia, la
  habitación muestra *(sin cargos a habitación)* en todas las listas de
  habitaciones y no se puede elegir, y el panel del huésped lo indica.
  Cobre en el punto de venta. El servidor también rechaza el cargo, así
  que ninguna caja puede saltárselo.
- **Dividir** mueve los artículos elegidos a una cuenta nueva,
  conservando su estado en cocina. Los totales siempre suman el
  original.
- **Descuentos**: **Agregar descuento** resta un importe de la cuenta.
- **De cortesía** (NC, sin cargo) necesita el nombre de quien lo
  autorizó, y admite una referencia opcional (la ocasión, una queja). La
  comanda y la cuenta imprimen "NC - NO CHARGE", y la cuenta se cierra en
  cero sin tocar ningún folio.
- Una cuenta de consumo en el local o para llevar no se puede cerrar sin
  pagar, y servirla no la liquida. Para cerrar una cuenta que nadie va a
  pagar, anúlela (más abajo).

## Anule una cuenta, quite o anule un artículo

Lo que puede deshacer depende de lo que ya tiene la cocina. Cada línea de
la cuenta indica **no enviado**, **En la cocina** o **Preparado**.

| La cuenta | Qué hace | Quién |
| --- | --- | --- |
| Nada enviado a la cocina | **Cancelar** con un motivo. La mesa queda libre al momento. | El jefe de sala |
| Una línea aún no enviada | El icono de papelera de la línea la quita. No hace falta motivo: no se cocinó nada. | El jefe de sala |
| Líneas que ya tiene la cocina | **Anular** la línea, o **Cancelar** la cuenta, con un motivo de anulación y la aprobación de un supervisor. | Un supervisor |
| Pagada, cargada a una habitación o NC | Cerrada. Corríjala en el folio o haga un reembolso. | Finanzas |

**Aún no se envió nada.** Abra la cuenta, pulse **Cancelar**, escriba el
motivo ("los clientes se fueron antes de pedir") y pulse **Anular
cuenta**. La cuenta se cierra como cancelada, el motivo y su nombre
quedan en ella, y la mesa vuelve a estar desocupada.

**La cocina ya tiene artículos.** La comida que la cocina ya empezó nunca
se borra. Cuando cancela la cuenta, o anula una línea con el icono de
cruz:

1. Elija un motivo de anulación (la misma lista que usa la recepción para
   anular cargos del folio) y agregue detalles si quiere.
2. Un supervisor lo aprueba. Un usuario Administrador del hotel o
   Finanzas elige su nombre y escribe su propio PIN de cajero en su caja.
   Un supervisor con sesión iniciada en la caja aprueba con su teclado de
   PIN.
3. Las líneas quedan en la cuenta, tachadas, con quién las anuló y quién
   lo aprobó. Se imprime un aviso de **ANULACIÓN** donde se imprimió la
   comanda (consulte [Configuración](#configuracion)), y la pantalla de
   cocina conserva la comanda, marcada como cancelada, hasta que el
   cocinero confirma cada línea. La comida cocinada que se anula cuenta
   como merma en el inventario de cocina.

Un PIN de supervisor incorrecto se rechaza y cuenta para el bloqueo de
PIN de ese supervisor. Los supervisores definen su PIN la primera vez que
una acción con dinero se lo pide.

Cada cancelación y cada anulación aparece en **Informes → Anulaciones y
bonificaciones** como *POS bill cancelled* o *POS void*, con quién la
hizo, quién la aprobó y por qué, y también en el panel de Alimentos y
bebidas.

## Lista de pedidos

Pulse **Pedidos** en la parte superior de la caja. Un panel se desliza
sobre la caja, así que nunca sale del punto de venta.

- **Hoy de forma predeterminada**, de la más reciente a la más antigua,
  con la mesa o habitación de cada cuenta, para quién era, importe, hora,
  número de comanda y estado: **No enviado**, **En la cocina**,
  **Pagado**, **Cargado a la habitación**, **De cortesía**, **Cerrado** o
  **Cancelado** (con su motivo).
- **Las cuentas aún abiertas de días anteriores** aparecen arriba en la
  lista de hoy, marcadas con el día en que se abrieron.
- **Buscar** por número de cuenta, número de comanda, mesa, habitación,
  nombre o teléfono del cliente, o nombre del huésped alojado. Toque un
  estado para ver solo esas cuentas.
- **Elija otro día** con el cuadro de fecha.
- **Toque una cuenta.** Una cuenta abierta se abre en la caja. Una
  cerrada se abre en modo de solo lectura, con sus líneas, anulaciones y
  quién las aprobó, y **Reimprimir cuenta**.

La lista solo muestra las cuentas de este punto de venta.

## Para quién es la cuenta: el panel del huésped

La línea bajo el nombre de la mesa en la cuenta indica para quién es la
cuenta. Tóquela para abrir el panel **Huésped**.

**Huésped alojado** (servicio a la habitación, o una cuenta de consumo en
el local cargada a una habitación):

- nombre y estrella VIP, número de habitación y fechas de estancia
- si la estancia admite cargos a habitación, según se decidió en el
  registro de entrada
- las notas del huésped (preferencias, alergias) y la nota de alergias de
  la cuenta
- lo que consumió antes en este punto de venta, con fechas e importes

**Cliente de paso o visitante externo:** escriba un número de teléfono o
un nombre.

- Las coincidencias salen de los mismos registros de huéspedes que usa la
  recepción. Cada una muestra los últimos dígitos del teléfono, cuántas
  cuentas tiene aquí y si está alojado ahora. Toque una para vincularla a
  la cuenta.
- **Añadir un nuevo cliente** guarda solo un nombre y un teléfono. Un
  teléfono que ya existe (escrito con o sin prefijo de país o espacios)
  reutiliza ese huésped en lugar de crear otro.
- Una vez vinculado, el panel muestra sus notas y sus visitas y cuentas
  anteriores aquí. **Eliminar de la cuenta** quita al cliente.

La caja solo muestra lo que necesita el servicio. Los números de teléfono
muestran sus cuatro últimos dígitos (los supervisores ven el número
completo). Los documentos de identidad, el correo electrónico, la
dirección, la fecha de nacimiento y la nacionalidad nunca aparecen en el
punto de venta. Un huésped solo es visible donde lo permite el acceso por
alojamiento del hotel.

## Use la pantalla de cocina

Abra **Alimentos y bebidas → Pantalla de cocina** en una pantalla del
pase. Cada pedido enviado aparece como una comanda, y la más reciente
suena (desactive el sonido con **Sonido activado**).

![La pantalla de cocina con tres comandas: una en preparación y dos esperando a empezar](/img/fnb/kitchen-display.png)

1. Filtre por punto de venta y por estación (**Cocina**, **Horno
   tandoor**, **Bar** …) para que cada partida vea solo sus platos.
2. Pulse **Iniciar** cuando la cocina tome una comanda. Hasta entonces la
   comanda muestra **EN ESPERA**, y el reloj del cocinero corre desde el
   momento en que se envió el pedido.
3. Pulse **Marcar listo** en cada plato, o **Todo listo** para la
   comanda. El recuadro del punto de venta pasa a **Listo** para que el
   jefe de sala sepa que debe recogerlo.
4. ¿Marcó un plato demasiado pronto? Abra la comanda y pulse
   **recuperar**; vuelve a la pantalla.

![Inicio de una comanda y marcado como lista en la pantalla de cocina](/img/fnb/kitchen-flow.gif)

Las comandas cambian de verde a ámbar y a **CON RETRASO** según su
antigüedad. Cada tarjeta muestra la mesa, los comensales, el jefe de
sala, las estaciones implicadas y las indicaciones en rojo. Si el pedido
tiene una nota de alergias, se resaltan los platos cuyos alérgenos
coinciden; tómelo como un recordatorio, no como una garantía. Una línea
anulada después de enviarse muestra un aviso en la comanda.

Si un pedido se envía tiempo a tiempo (un agente de IA o la API pueden
hacerlo con un tiempo del menú), los tiempos retenidos aparecen en la
comanda con un botón **Enviar principales a preparación** (o entrantes,
postres) para que la cocina los envíe cuando esté lista.

## Aceptar e imprimir comandas automáticamente

Para una cocina con mucho trabajo que no quiere pulsar **Iniciar** en
cada comanda: **Configuración → Alimentos y bebidas → Comandas de cocina
→ Aceptar e imprimir comandas automáticamente**. Cuando un jefe de sala
envía un pedido, la comanda se imprime al momento y aparece en la
pantalla de cocina ya iniciada. Desactivado (el valor predeterminado), la
cocina pulsa **Iniciar** y cada caja decide si imprime con su interruptor
de **impresora de comandas**.

![Configuración → Alimentos y bebidas: aceptar e imprimir comandas automáticamente, y avisos de anulación](/img/fnb/settings-kot.png)

Cada punto de venta puede cambiar esto en **Alimentos y bebidas → Puntos
de venta → Comanda al enviar**:

| Comanda al enviar | Qué pasa al enviar un pedido |
| --- | --- |
| Usar configuración de Alimentos y bebidas (predeterminado) | Sigue Configuración → Alimentos y bebidas |
| Aceptar e imprimir automáticamente | Imprime la comanda y marca la comanda como iniciada |
| Inicio manual en cocina | La cocina acepta cada comanda; el interruptor de impresora de la caja decide si se imprime |

Así, el bar y el servicio a la habitación pueden aceptar
automáticamente mientras el pase del restaurante principal sigue
iniciando cada comanda a mano. Una segunda ronda en la misma cuenta
imprime su propia comanda pero no reinicia la hora de inicio de la
primera.

## Impresoras de cocina

Sin impresoras de cocina, una comanda se imprime en la caja que la envió.
Configure impresoras de cocina para enviar cada comanda a la impresora de
quien la cocina, sea cual sea la caja que envió el pedido: dos
restaurantes pueden compartir una impresora de cocina, las bebidas del
bar pueden imprimirse en el bar y el tandoor puede tener la suya.

![Alimentos y bebidas → Impresoras, con una impresora de cocina principal y una del bar, las dos imprimiendo](/img/fnb/kitchen-printers.png)

### Agregue una impresora

1. **Alimentos y bebidas → Impresoras → Agregar impresora.**
2. Póngale nombre ("Cocina principal") y elija la **Conexión** (ver más
   abajo), el **Ancho del papel** (80 mm o 58 mm) y las **Copias** (1-3).
3. Si quiere, elija una **Impresora alternativa**: adonde van sus
   comandas si falla.
4. En **Imprime comandas para**, marque lo que imprime: **Todas las
   estaciones** de un punto de venta, o estaciones sueltas. Marque el
   mismo punto de venta y estación en dos impresoras para imprimir una
   copia en cada una.
5. **Guardar impresora** y luego **Impresión de prueba**.

![Alta de una impresora de tandoor que imprime los platos de tandoor del restaurante](/img/fnb/printer-setup.gif)

![El formulario de impresora: nombre, conexión, papel, copias, impresora alternativa y la cuadrícula de puntos de venta × estaciones](/img/fnb/printer-form.png)

Cuando se envía un pedido, Kamra lo divide según la estación de cada
plato y envía a cada impresora solo sus líneas, con el punto de venta, la
estación, la mesa y el número de comanda arriba. Las líneas sin impresora
configurada se imprimen en la caja, como antes.

### Conecte la impresora: estación de impresión

Funciona con cualquier impresora (USB, de red LAN/Wi-Fi o Bluetooth) y
con Kamra en la nube.

1. Ponga un dispositivo junto a la impresora (una tableta, un mini-PC o
   un portátil viejo) e instale en él la impresora como su **impresora
   predeterminada**.
2. Inicie Chrome en ese dispositivo con impresión silenciosa (consulte
   [Imprimir sin cuadro de diálogo](#imprimir-sin-cuadro-de-dialogo)).
3. Inicie sesión, abra **Alimentos y bebidas → Pantalla de cocina** y, en
   la cabecera, elija **Imprimir para → Cocina principal**.

![La cabecera de la pantalla de cocina configurada para imprimir para la impresora de la cocina principal](/img/fnb/kitchen-print-for.png)

Esa pantalla imprime ahora las comandas de la impresora en cuanto se
envían, y sigue funcionando como pantalla de cocina. La elección se
guarda en el dispositivo. Un punto verde indica que está imprimiendo;
**Alimentos y bebidas → Impresoras** muestra "Una pantalla de cocina está
imprimiendo para ella".

Un dispositivo imprime para una impresora. Tres impresoras necesitan tres
dispositivos, o tres perfiles de Chrome en un ordenador, cada uno con su
propia impresora predeterminada. Como la pantalla de cocina se conecta
hacia Kamra, la impresora puede estar en cualquier lugar con internet:
una cocina central en otro edificio funciona igual que una al lado.

### Conecte la impresora: IP directa

Cuando Kamra funciona en un servidor **en la propia red del hotel**,
puede enviar la comanda directamente a una impresora térmica de red
(ESC/POS en el puerto 9100). Elija **IP directa** e introduzca la
dirección IP y el puerto de la impresora. Un servidor de Kamra en la nube
no puede llegar a una impresora de una red privada (`192.168.x.x`); use
allí una estación de impresión.

### Cuando falla una impresora

- Una comanda que una impresora no pudo imprimir pasa a su **impresora
  alternativa**, marcada "para Bar". Sin impresora alternativa queda como
  fallida; vuelva a imprimirla desde la cuenta.
- Una comanda que una estación de impresión recibió pero nunca confirmó
  se ofrece de nuevo al cabo de un minuto.
- Los trabajos de impresión terminados se guardan 7 días para
  reimpresiones y reclamaciones, y luego se borran, porque las comandas
  llevan nombres de huéspedes y direcciones de entrega.

## Imprimir sin cuadro de diálogo

Un navegador muestra normalmente un cuadro de diálogo de impresión para
cada comanda. En las cajas y en los dispositivos de estación de
impresión, inicie Chrome con `--kiosk-printing` para que las comandas
vayan directamente a la impresora predeterminada. El punto de venta
muestra un consejo una sola vez si detecta una impresión esperando en un
cuadro de diálogo.

- **Windows:** haga clic derecho en el acceso directo de Chrome →
  **Propiedades**, y agregue ` --kiosk-printing` al final de **Destino**.
  Cierre todas las ventanas de Chrome y vuelva a iniciar Chrome desde ese
  acceso directo.
- **macOS:** cierre Chrome y, en Terminal, ejecute
  `open -a "Google Chrome" --args --kiosk-printing`.
- Configure la impresora térmica como impresora predeterminada del
  sistema, con papel de 80 mm (o 58 mm) y sin márgenes.

## Ingredientes

**Alimentos y bebidas → Ingredientes** es el maestro de la despensa:
nombre, unidad (kg, g, L…), categoría, costo por unidad y si está activo.
Agregue aquí los ingredientes antes de darles existencias o ponerlos en
una receta.

## Inventario de cocina

**Alimentos y bebidas → Inventario de cocina** son las existencias de
cada punto de venta: existencias disponibles, nivel mínimo, **Recibir**,
**Recuento de existencias**, **Mermas** y el **Libro contable**.

![Inventario de cocina: existencias disponibles de cada ingrediente, nivel mínimo y estado, con Recibir, Recuento de existencias y Mermas](/img/fnb/inventory.png)

Cada fila muestra el estado (correcto, bajo, agotado o negativo) frente a
su nivel mínimo. Las recetas se definen en la pantalla **Menú**
(**Recetas**).

- Los ingredientes salen del inventario cuando se envía la comanda
  (cuando empieza la cocción), no cuando se paga la cuenta.
- Una línea anulada después de enviarse cuenta como **mermas**, no como
  devolución: la comida se preparó.
- Una falta de existencias nunca bloquea un pedido. Se informa, y un
  plato nunca se desactiva automáticamente.
- Un recuento de existencias es una entrada intencionada, no una
  sobrescritura silenciosa.

## Panel de alimentos y bebidas

**Alimentos y bebidas → Panel de alimentos y bebidas** muestra el día de
un punto de venta (o ponga la segunda fecha para un periodo de hasta 92
días): ventas brutas, cuenta media, comensales, cuentas abiertas, cuentas
de cortesía, el tiempo medio de la cocina desde el envío hasta listo,
ventas por tipo de pedido y por forma de pago, artículos más vendidos, y
cada cuenta NC, línea anulada y cuenta cancelada con su motivo.

![El panel de alimentos y bebidas](/img/fnb/dashboard.png)

## Configuración

Todo en **Configuración → Alimentos y bebidas** (Administrador del hotel
y Finanzas pueden cambiarlo):

| Ajuste | Valor predeterminado | Qué hace |
| --- | --- | --- |
| Aceptar e imprimir comandas automáticamente | Desactivado | Enviar un pedido imprime la comanda e inicia la comanda en cocina. Los puntos de venta pueden cambiarlo. |
| Imprimir anulaciones en cocina | Activado | Una línea anulada, o una cuenta cancelada, después de enviar su comanda imprime un aviso de ANULACIÓN en la impresora que la tenía. |
| Avisar de una cuenta sin enviar a cocina después de | 15 min | Una cuenta abierta que nadie envió se pone roja en la caja y en la lista de pedidos. |
| Mostrar una reserva desde | 60 min antes | Cuándo empieza a verse una reserva de mesa en el plano de mesas. |
| Seguir mostrándola hasta | 240 min después | Cuándo deja de verse. |
| Impresoras de cocina | No es un interruptor | Se gestionan en **Alimentos y bebidas → Impresoras**. |

## Solución de problemas

**La comanda no se imprimió.**
1. ¿Hay una impresora de cocina configurada para ese punto de venta y la
   estación del plato? La barra bajo el menú indica adónde fue la
   comanda.
2. Estación de impresión: ¿está abierta la pantalla de cocina,
   configurada en **Imprimir para** esa impresora, con un punto verde?
   **Alimentos y bebidas → Impresoras** muestra si una pantalla está
   imprimiendo para ella.
3. ¿Es la impresora la impresora predeterminada de ese dispositivo, y
   tiene papel?
4. Sin impresoras de cocina: ¿está activado el interruptor de **impresora
   de comandas** de la caja, o la aceptación automática?

**Se abre un cuadro de diálogo de impresión cada vez.** Inicie Chrome con
`--kiosk-printing` ([cómo](#imprimir-sin-cuadro-de-dialogo)).

**Los pedidos tardan en llegar a la pantalla de cocina.** Ejecute
**Configuración → Alimentos y bebidas → Comprobación de velocidad del
punto de venta** en la caja lenta. Informa del tiempo de ida y vuelta de
la red, de cuánto tarda el servidor y de si las actualizaciones en
directo llegan al navegador.

![La comprobación de velocidad del punto de venta avisa de que las actualizaciones en directo no llegan al navegador y de que no hay procesos en segundo plano en marcha](/img/fnb/speed-check.png)

| Qué indica | Qué hacer |
| --- | --- |
| Ida y vuelta de red superior a 300 ms | El servidor está lejos del hotel o la conexión es débil. Aloje el servidor en una región cercana al hotel. |
| Trabajo del servidor superior a 300 ms | El servidor está ocupado o es demasiado pequeño. Agregue CPU o workers de gunicorn. |
| No llegan las actualizaciones en directo | socket.io no está en marcha o el servidor web no lo redirige (`/socket.io`). Mientras tanto, la pantalla de cocina comprueba cada 5 segundos. |
| Sin procesos en segundo plano | Inicie los workers del bench; la impresión por IP directa y otras tareas los esperan. |

**"Agregue al menos un artículo disponible."** El plato está marcado como
no disponible en el menú, o pertenece a otro punto de venta.

## Para desarrolladores

El punto de venta y la cocina funcionan con endpoints autorizados en
`kamra/pos.py` y `kamra/printing.py`; los agentes de IA usan las mismas
llamadas como herramientas MCP (`pos_send_order`, `pos_send_round`,
`pos_fire_kot`, `pos_kitchen_queue`, `pos_pay_order`, `pos_orders`,
`pos_cancel_order`, `pos_remove_item` y más). Consulte la
[MCP tool reference](/mcp-tools) y la
[API reference](/api-reference#restaurant-pos-kitchen).

Las reglas de cancelación y anulación están en el servidor, no en la
caja: `kamra.pos.cancel_order` y `void_item` rechazan las líneas que ya
tiene la cocina salvo que un supervisor lo apruebe (`supervisor` +
`supervisor_pin`, comprobado con el PIN de cajero de ese usuario), y
siempre rechazan a un agente. Un agente puede cancelar una cuenta sin
nada enviado (`pos_cancel_order`, queda registrado) y quitar una línea
no enviada, pero nunca anula comida que la cocina ya empezó. La lista de
pedidos (`orders_list`) y el panel del huésped (`guest_panel`,
`find_customer`, `attach_customer`) se limitan al alojamiento del punto
de venta.
