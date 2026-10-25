# Motor de reservas: su página de reservas directas

El motor de reservas es la página de reservas propia de su hotel. Los
huéspedes abren `/book`, eligen fechas, ven los precios en tiempo real y
reservan sin crear una cuenta. Cada reserva entra en Kamra como cualquier
otra, con **Sitio web** como origen. Los gestores de ingresos y los
administradores del hotel lo configuran en la aplicación **Motor de
reservas**.

![La página de reservas de Kamra Demo Palace: fechas y huéspedes arriba, y después cada tipo de habitación con su precio para la estancia](/img/booking-engine/book.png)

## Antes de empezar

1. **Active la página.** **Motor de reservas → Configuración**: active
   **Página pública de reservas activa** y elija un **Modo de reserva**.
   La casilla **Motor activo** de la consola hace lo mismo.
2. **Complete el perfil del hotel.** **Motor de reservas → Perfil del
   hotel**: nombre, descripción, datos de contacto, dirección y posición
   en el mapa, e indicaciones para llegar en coche. Haga clic en
   **Guardar cambios** abajo.

   ![La consola del motor de reservas: Motor activo, Vista previa de la página y el formulario del perfil del hotel](/img/booking-engine/console.png)

3. **Agregue fotos.** **Motor de reservas → Fotos**: **Logotipo**,
   **Imagen principal de presentación**, la galería de fotos y el **Color
   destacado** que usa la página. Los archivos se guardan solos.
4. **Redacte las políticas.** **Motor de reservas → Políticas**: horas de
   entrada y salida, el plazo de cancelación gratuita, el cargo por
   cancelación tardía y por no presentación, el depósito, y las normas de
   la casa y las políticas de mascotas, niños y camas supletorias.
   Aparecen en la página y se indican en cada reserva.

   ![La sección Políticas: horas de entrada y salida, plazo y cargo de cancelación, cargo por no presentación, depósito y normas de la casa](/img/booking-engine/policies.png)

5. **Opcional:** **Comodidades** (una por línea), **Preguntas
   frecuentes** (preguntas y respuestas), **SEO** (**Título para
   buscadores**, **Descripción para buscadores**, imagen para compartir).
6. Los tipos de habitación, precios, planes de comidas y cupones vienen de
   [Ingresos](/es/revenue). Asigne a un tipo de habitación un
   **Identificador de la URL pública** para darle su propia página.

Haga clic en **Vista previa de la página** para abrir `/book` en una
pestaña nueva.

## Elija cómo se confirman las reservas

**Motor de reservas → Configuración → Modo de reserva**:

- **Inmediata**: la reserva se crea al momento. Si no hay nada que pagar
  ahora, queda **Confirmado**. Si se debe un anticipo, queda en **Pago
  pendiente** y la habitación se retiene durante 2 horas
  (**Configuración → Recepción → Mantener reservas sin confirmar
  durante**). Una retención que no se paga a tiempo se libera.
- **Solicitar reserva**: el huésped envía una solicitud. No retiene
  ninguna habitación hasta que usted la acepta. Abra la reserva y haga
  clic en **Aceptar** (Kamra vuelve a comprobar la disponibilidad y le
  asigna una habitación) o en **Rechazar** con un motivo (cancelada, sin
  cargo). Consulte [Reservas](/es/reservations).

![Configuración del motor de reservas: la página está activa, modo de reserva Inmediata, los huéspedes pagan en el hotel](/img/booking-engine/settings.png)

## Elija qué pagan los huéspedes en línea

**Motor de reservas → Pagos → Cobro al reservar** (o **Los huéspedes
pagan** en Configuración):

| Opción | Qué paga el huésped al reservar |
| --- | --- |
| **Pago en hotel** | Nada. Toda la estancia se paga en el hotel. |
| **Porcentaje de anticipo** | El **Porcentaje de anticipo** del total; el resto en el hotel. |
| **Cargo de registro** | Un importe fijo; el resto en el hotel. |
| **Pago total en línea** | Toda la estancia. El botón dice **Confirmar y pagar**. |

![La sección Pagos con Cobro al reservar en Pago en hotel, y la nota sobre la pasarela de pago](/img/booking-engine/payments.png)

El pago en línea usa la pasarela de **Configuración → Pagos**, cuando el
paquete de su país ofrece una. Hasta que se conecte una pasarela, el
anticipo queda registrado como pendiente y la recepción lo cobra. Cada
reserva conserva las condiciones de pago con las que se hizo; un cambio
posterior solo afecta a las reservas nuevas.

## Qué hace el huésped

1. Abre `/book`, elige **Registro de entrada**, **Salida**, **Adultos** y
   **Niños**, y hace clic en **Consultar disponibilidad**.
2. Elige una habitación y hace clic en **Reservar ahora**. (En un
   alquiler de corta estancia el botón dice **Reservar esta opción**; en
   el modo Solicitar reserva, **Solicitar una reserva**).
3. Introduce **Nombre completo** y **Teléfono**; **Correo electrónico
   (opcional)**.
4. Elige un **Plan de comidas**, o **Solo habitación**.
5. Opcional: **Agregar experiencias**, un cupón en **¿Tienes un
   código?** y **Solicitudes especiales**.
6. Hace clic en **Reservar ahora**. La página muestra el número de
   reserva y lo que se paga ahora y en el hotel.

![Un huésped reserva una habitación Deluxe para dos noches en /book, agrega Yoga at Dawn y recibe un número de reserva](/img/booking-engine/guest-booking.gif)

![Cada tipo de habitación con su capacidad, sus comodidades, el total de la estancia y el depósito](/img/booking-engine/rooms.png)

![Complete su reserva: nombre y teléfono, plan de comidas y diez experiencias para agregar, con Yoga at Dawn agregada](/img/booking-engine/booking-sheet.png)

![Reserva confirmada: el número de reserva y el total, a pagar en el hotel](/img/booking-engine/confirmed.png)

Las fechas y el número de huéspedes forman parte de la dirección, por
ejemplo `/book/2026-11-18/2026-11-20/2/0`, así que puede enlazar
directamente a una estancia.

## Ofrezca experiencias

Las experiencias son extras como un ritual de spa, un safari o una cena
a la luz de las velas. Agréguelas y edítelas en **Ingresos →
Experiencias** (consulte [Ingresos](/es/revenue)). Cada una tiene un
nombre, una categoría, un precio, una duración, una descripción y una
foto. Marque **Mostrar en la página pública de reservas** para ofrecerla
en `/book`. El huésped solo elige cuántas; el precio siempre lo pone
usted. Las experiencias se agregan a la cuenta del huésped en el hotel.

## Páginas de alojamiento (/stay)

Un tipo de habitación con un **Identificador de la URL pública** tiene
su propia página en `/stay/<slug>`, por ejemplo `/stay/deluxe`: fotos,
capacidad, un mapa y un cuadro de reserva con **Consultar
disponibilidad** y **Reservar**.

![La página de Deluxe: detalles de la habitación, mapa y el cuadro de reserva con el precio para dos noches](/img/booking-engine/stay-room.png)

Para villas y casas particulares (tipo de alojamiento **Alquiler de
corta estancia**), cada página es un lugar: una habitación o la casa
entera. Reservar la casa entera retira sus habitaciones de la venta. Las
cotizaciones suman la tarifa de limpieza y muestran el depósito
reembolsable.

![La página del alojamiento completo de Kamra Lakeside Villa, con el precio para dos noches](/img/booking-engine/stay-villa.png)

Cuando un alojamiento tiene una sola página con identificador, `/book`
va directamente a su página `/stay`.

## Varios alojamientos en una página de reservas

Cuando más de un alojamiento en el mismo Kamra tiene su página de
reservas activa, `/book` muestra primero **Alojamientos**: una tarjeta
por alojamiento con su foto, ciudad, tipo, descripción y precio base más
bajo por noche. El huésped hace clic en **Ver y reservar →** para abrir
la página de ese alojamiento, y se conservan las fechas que ya estén en
la dirección.

![Alojamientos: tarjetas de Kamra Beach Homestay y Kamra Demo Palace, cada una con su ciudad, tipo y precio desde por noche, e iniciales donde no hay foto](/img/booking-engine/properties.png)

Para enlazar directamente a un alojamiento, use `/book?property=<slug>`
o `/stay/<slug>`. El identificador es el **Prefijo de la ruta pública**
en **Motor de reservas → SEO** o, si está vacío, el nombre del
alojamiento en minúsculas con guiones (por ejemplo `kamra-demo-palace`).

## Registro de entrada en línea (/checkin)

Cada reserva recibe un enlace privado de registro de entrada,
`/checkin/<code>`. La recepción lo copia desde la lista de llegadas en
**Hoy** (**copiar enlace de registro de entrada**, consulte
[Recepción](/es/front-desk)) y se lo envía al huésped.

En esa página, el huésped introduce el tipo y número de su documento de
identidad (los tipos que acepta el paquete de su país), puede agregar una
foto del documento y un justificante de domicilio, completa el correo
electrónico, la nacionalidad, la dirección y la hora de llegada, firma la
tarjeta de registro y hace clic en **Firma y completa el registro de
entrada**. La recepción ve los datos tal como se enviaron y los verifica
a la llegada.

![La página de registro de entrada en línea: resumen de la estancia, tipo y número de documento, foto del documento, justificante de domicilio, datos de contacto y el cuadro de firma](/img/booking-engine/checkin.png)

## Configuración

| Ajuste | Dónde | Valor predeterminado | Qué hace |
| --- | --- | --- | --- |
| Página pública de reservas activa | **Configuración → Motor de reservas** | activado | Muestra u oculta `/book` y `/stay` para este alojamiento. |
| Modo de reserva | **Configuración → Motor de reservas** | Inmediata | Inmediata o Solicitar reserva. |
| Los huéspedes pagan | **Configuración → Motor de reservas** | Pago en hotel | Lo que se cobra en línea. |
| Anticipo | **Configuración → Motor de reservas** | 0% | Se usa con Porcentaje de anticipo. |
| Cargo de registro | **Configuración → Motor de reservas** | 0 | Se usa con Cargo de registro. |
| Mantener reservas sin confirmar durante | **Configuración → Recepción** | 120 min | Cuánto tiempo retiene su habitación una reserva en Pago pendiente. |

## Conviene saber

- Los precios de la página salen de los mismos precios que usa la
  recepción: se aplican temporadas, precios por demanda, planes de
  comidas y cupones. Los planes tarifarios no; consulte
  [Ingresos](/es/revenue).
- Un huésped solo puede agregar las experiencias que usted marcó con
  **Mostrar en la página pública de reservas** y que no están
  desactivadas, a su precio.
- Kamra guarda la foto del documento del huésped de forma privada. Con
  el ajuste de conservación **Verificar y eliminar**, se borra al
  registrar la salida.

## Solución de problemas

**`/stay/...` dice "Listing not found."** Compruebe que el tipo de
habitación tiene ese **Identificador de la URL pública**, que no está
desactivado y que la página de reservas de su alojamiento está activa.
`/stay/<slug>` también acepta el identificador de un alojamiento, pero
solo si su página de reservas está activa.

**La reserva sigue en Pago pendiente.** Se debe un anticipo y ninguna
pasarela lo cobró. Cóbrelo en la recepción y confirme la reserva, o se
liberará cuando venza la retención.

**Una habitación dice "Sin disponibilidad para estas fechas".** Todas las
habitaciones de ese tipo están ocupadas al menos una noche de la
estancia, o bloqueadas. **Reservar ahora** sigue desactivado hasta que el
huésped elija otras fechas.

**Falta un tipo de habitación en la página.** Está desactivado o
pertenece a otro alojamiento.

## Para desarrolladores

Las páginas públicas llaman a endpoints para huéspedes en
`kamra/public_api.py` (`catalog_index`, `showcase`, `search_stay`,
`book`, `check_voucher`, `precheckin_info`, `precheckin_submit`); los
identificadores de `/stay` se resuelven en `kamra/booking_slugs.py`.
Consulte la
[API reference](/api-reference#public-no-auth-booking-page-check-in) y,
para aceptar solicitudes, las [MCP tools](/mcp-tools) `booking_requests`
y `accept_booking_request`.
