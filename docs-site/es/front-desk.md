# Recepción - llegadas, registro de entrada y salida

La aplicación Recepción es donde la recepción gestiona el día: quién llega,
quién se va, quién está en cada habitación y los trámites entre medias. La
ven los usuarios de Recepción, Auditor nocturno y Administrador del hotel.
Crear reservas se explica en [Reservas](/es/reservations).

![La pantalla Hoy: recuentos de llegadas, salidas, alojados, ocupación, ingresos y tareas abiertas; las listas de llegadas y salidas a la izquierda; el panel de habitaciones por planta a la derecha](/img/front-desk/today.png)

## Antes de empezar

1. **Fije sus horas de entrada y salida.** **Configuración → Políticas de estancia →
   Entrada y salida**. Se imprimen en la ficha de registro y en la página
   de registro en línea del huésped.
2. **Decida cómo se envían los enlaces de autorregistro.** **Configuración → Recepción →
   Llegadas**. Deje **Enviar automáticamente enlaces de registro previo** desactivado para copiar
   cada enlace a mano, o actívelo para enviarlos cada mañana (consulte
   [Enviar el enlace de autorregistro](#enviar-el-enlace-de-autorregistro)).
3. **Abra su caja antes de cobrar.** Un huésped sin reserva previa que paga en
   recepción, o un anticipo, pasa por su sesión de caja: **Finanzas →
   Cajero → Mi caja**. Consulte [Facturación](/es/billing).

## Leer la pantalla Hoy

**Recepción → Hoy** es la pantalla de inicio. Se actualiza sola cada 30
segundos.

- Los seis recuentos de arriba: **Llegadas**, **Salidas**,
  **Alojados**, **Ocupación**, **Ingresos** (con RevPAR) y **Tareas abiertas**
  de limpieza. Cada uno abre lo que hay detrás: los tres primeros abren
  [Alojados](#ver-a-todos-los-huespedes-alojados) en esa pestaña, Ocupación el
  panel de habitaciones, Ingresos el panel de ingresos, Tareas abiertas la limpieza.
- Debajo, la fila de dinero: **Cobrado hoy**, **Saldo pendiente**, **Folios
  abiertos** y, del mes en curso, **ADR**, **RevPAR** y **Ocupación**, cada uno un
  enlace al panel de cajas, las cuentas, la facturación o el informe.
- **Ocupación** son las habitaciones ocupadas ahora sobre las que puede vender
  (sin contar las fuera de servicio). Bajo las tarjetas, **Ocupación reservada,
  próximos 90 días** muestra una celda por noche, más oscura cuanto más llena,
  con las medias de 30, 60 y 90 días. Las habitaciones **Retenidas para grupos**
  (las de un bloqueo de grupo que aún no tienen reserva con nombre) se suman
  encima de las reservadas en un tono más claro; cuando pasa la fecha límite
  del bloqueo se liberan y desaparecen. Pase el cursor por una celda para ver
  las habitaciones reservadas y retenidas esa noche y la ocupación sin y con
  retenciones, o abra **Por semana** para ver una tabla con una columna de
  retenidas. Consúltelo antes de aceptar una reserva grande.
- Los ingresos y la fila de dinero son para Finanzas, Ingresos, el auditor
  nocturno y los gerentes. Un recepcionista ve **Llegadas**, **Salidas**,
  **Alojados**, **Ocupación**, la previsión de 90 días y **Tareas abiertas**,
  nunca ingresos, ADR, RevPAR, cobros ni saldos pendientes. El panel de
  ingresos y el Resumen gerencial siguen cerrados para él, y el informe de
  ocupación no le muestra sus columnas de dinero.
- **Llegadas** y **Salidas** muestran las estancias de hoy. Cada fila muestra el
  origen (Sitio web, Teléfono, OTA, Agente de IA…), una etiqueta de pago (**Pagado**,
  **Pendiente ₹…** o **Sin pagar**) y **Registro previo completado** cuando el huésped ha rellenado
  el formulario en línea. "via Priya (Assistant)" significa que otra persona reservó en
  nombre del huésped; pase el cursor por encima para ver el teléfono de quien reservó.
- **Panel de habitaciones** muestra todas las habitaciones por planta. Pulse una habitación ocupada (verde
  oscuro) para ver un menú: **Registrar salida**, **Folio y facturación**, **Solicitudes de
  huéspedes**, **Ficha de registro** o **Detalles de la habitación**. Una habitación cuyo huésped
  llega hoy muestra **Llegando**; púlsela para **Registrar entrada**. Pulse cualquier
  otra habitación para avanzar un paso su estado de limpieza: Sucia → Limpia →
  Inspeccionada → Fuera de servicio → Sucia. **Abrir vista completa** abre la pantalla
  [Habitaciones](/es/rooms).
- **Huéspedes alojados** muestra a todos los que se alojan, su saldo y cuándo
  se van. Pulse una fila para ver la ficha de registro.

![La lista de llegadas: cada huésped con etiquetas de origen y pago, la habitación, las noches y el número de personas, los accesos directos a la ficha de registro y al enlace de registro, y un botón Registrar entrada](/img/front-desk/arrivals.png)

## Ver a todos los huéspedes alojados

**Recepción → Alojados** reúne los huéspedes del día en una sola lista, con tres
pestañas: **Llegadas**, **Huéspedes alojados** y **Salidas**, cada una con su recuento.
Cambie la fecha con las flechas (pulse la fecha para volver a hoy). Una
fila abre la estancia; sus botones registran la entrada de las llegadas de hoy, registran la salida
o abren el folio. **Ver todo** en las listas de Hoy abre la misma página.

![Alojados: las pestañas Llegadas, Huéspedes alojados y Salidas con recuentos, y los huéspedes en una tabla con su habitación, estancia, origen, importe pendiente y acciones](/img/front-desk/in-house.png)

## Elegir qué muestra Hoy

Cada persona puede elegir qué paneles muestra Hoy y en qué orden. Pulse
**Personalizar** (junto a la fecha).

1. Toque un panel para mostrarlo u ocultarlo: **Indicadores principales**, **Solicitudes de reserva**,
   **Llegadas**, **Salidas**, **Panel de habitaciones**, **Huéspedes alojados**,
   **Limpieza** y **Tareas abiertas** (habitaciones con trabajo de limpieza aún
   abierto, y quién lo tiene).
2. Use las flechas arriba y abajo para cambiar el orden, y la flecha doble para
   mover un panel entre la columna estrecha y la ancha.
3. Pulse **Guardar mi diseño**. Su diseño se guarda en el servidor, así que le sigue
   a cualquier ordenador o tableta en el que inicie sesión.

**Utilice el valor predeterminado del hotel** descarta su propio diseño. Un Administrador del hotel también ve
**Valor predeterminado del hotel**: **Usar esta configuración como predeterminada del hotel** fija lo que ven todos en el
hotel hasta que personalicen su propio Hoy, y **Restablecer el valor predeterminado del hotel**
vuelve al diseño estándar. Si nadie personaliza nada,
Hoy se ve como siempre (Tareas abiertas empieza oculto).

## Registrar la entrada de un huésped

El registro de entrada es una lista corta de pasos, una pantalla cada uno, en el orden que fijó su
alojamiento. Los mismos pasos se abren desde cualquier botón **Registrar entrada**: la
llegada en **Hoy**, la reserva en **Reservas**, una estancia en el
**Calendario de ocupación**, una llegada en **Cierre del día** y un huésped sin reserva previa.

1. En **Hoy**, busque al huésped en **Llegadas** y pulse **Registrar entrada**.
2. Siga los pasos de la parte superior del panel. Cada paso dice qué
   hacer. Un paso **Obligatorio** no tiene botón **Saltar**. Un paso **Opcional**
   sí lo tiene.
3. Pulse **Listo, continuar** cuando termine un paso. Kamra lo comprueba: por
   ejemplo, no pasa de **Huésped y documentos de identidad** mientras falte un documento.
4. En la última pantalla, lea el resumen y pulse **Registrar la entrada en la habitación 205**
   (el botón indica la habitación). Un paso en rojo en el resumen es obligatorio y
   aún no está hecho: pulse **Vaya al paso** para terminarlo.

![El panel de registro de entrada de Nikhil Rao: los pasos en la parte superior, abierto en Huésped y documentos de identidad](/img/front-desk/checkin-sheet.png)

La habitación pasa a ocupada, se abre el folio del huésped y cualquier anticipo cobrado
antes de la llegada pasa a la cuenta de la estancia. La última pantalla enlaza con la
ficha de registro para imprimirla.

### Los pasos

| Paso | Qué hace | Obligatorio por defecto |
| --- | --- | --- |
| **Huésped y documentos de identidad** | Compruebe el nombre y el teléfono, y luego el documento de identidad del huésped y de todos los que se alojan. Hay una tarjeta por cada persona de la reserva (adultos y niños): tome la **Foto** de cada persona, una **Foto de la identificación** y los datos del documento, o pulse **Escanear identificación** para rellenarlos con un escáner. Todo adulto necesita documento; un niño, solo cuando el registro de su país lo pide. Si el huésped hizo el registro en línea, verá **Hecho en línea**: compare lo que envió con la persona. | Sí |
| **Quién paga** | Elija quién paga: la OTA (ya pagado, o el huésped paga aquí), el huésped, la empresa o el grupo. Verá el total de la estancia, lo pagado y lo pendiente. | Sí |
| **Habitación** | Mantenga la habitación asignada o elija una habitación libre del tipo reservado. Las habitaciones limpias aparecen primero. **Mejora de categoría u otro tipo de habitación** muestra el nuevo precio antes de confirmar. | Siempre |
| **Depósito de garantía y anticipo** | Cobre el depósito de garantía, o exímalo indicando un motivo, y cualquier anticipo aún pendiente. Solo aparece cuando su alojamiento pide un depósito o la reserva debe un anticipo. | Sí |
| **Ficha de registro** | Abra la ficha para mostrarla o imprimirla. El huésped firma en la pantalla o en la ficha impresa. | Sí en India, opcional en otros países |
| **Llaves** | Anote cuántas llaves entregó y, si quiere, los números de las tarjetas. | No |
| **Wifi e información de la estancia** | Indique al huésped el wifi, el horario del desayuno y la hora de salida. Pulse **Imprimir** o **Enviar por WhatsApp**. Aparece cuando rellena **Configuración → Recepción → Información al huésped durante la llegada**. | No |
| **¿Necesita algo?** | Toque lo que pide el huésped: cama adicional, llamada despertador, traslado al aeropuerto, necesidades alimentarias, ocasión especial. Cada petición se convierte en una tarea para el equipo correspondiente. | No |
| **Cargos a la habitación** | Permita o bloquee los cargos a la habitación. Si están bloqueados, el restaurante, la lavandería y el minibar no pueden cargar nada a esta habitación, y el huésped paga en el punto de venta. Para una estancia prepagada por OTA sin nada retenido para extras, Kamra sugiere bloquearlos. | Sí |

Kamra registra quién hizo cada paso y cuándo. La reserva muestra quién asignó
la habitación, quién entregó las llaves y quién registró la entrada del huésped, y cada paso
queda en el **Registro de actividad**.

### Elegir qué pasos son obligatorios

**Configuración → Recepción → Pasos del registro de entrada** (Administrador del hotel). Marque
**Obligatorio** en cada paso que su personal no debe saltar nunca. **Habitación** siempre es
obligatorio. Un paso obligatorio no se puede saltar en recepción, y Kamra no
registra la entrada del huésped hasta que esté hecho, lo pida quien lo pida: la recepción, la API o un
agente de IA.

### Detalles del día a día en recepción

- **Llegadas previstas de varios días:** en **Alojados**, la pestaña Llegadas
  tiene una fecha **Hasta**: elija hasta dos semanas por delante para ver a
  todos los que llegan.
- **Segmento de mercado:** una reserva puede llevar su segmento (Corporativo,
  Vacaciones, Grupo, MICE, Gobierno, Boda, Estancia larga, Tripulación aérea,
  De cortesía, Uso interno). Una reserva de empresa es Corporativo salvo que
  elija otro.
- **Peticiones con precio:** en el registro de entrada, una cama adicional, un
  traslado al aeropuerto o una ocasión especial pueden llevar un precio; va a
  la cuenta del huésped (el traslado al aeropuerto como **Taxi**). Una llamada
  despertador o una nota alimentaria nunca se cobran.
- **Cambio de habitación** muestra el tipo de habitación en la que está ahora
  el huésped y el tipo al que pasa.
- **Folio:** cuando el huésped ha pagado más de lo cargado hasta ahora, el
  folio lo muestra como **Anticipo**, no como saldo negativo.
- **Los números de reserva** vuelven a empezar cada ejercicio fiscal: en India
  en abril (RES-2026-… va de abril de 2026 a marzo de 2027), en los demás
  países en enero.

### Escanear un documento de identidad

**Escanear identificación** rellena los datos del huésped desde el propio
documento, así nadie teclea un número de pasaporte.

- **Pasaporte o documento de identidad**: las dos o tres líneas de letras y `<`
  al pie de la página con la foto. Kamra comprueba los dígitos de control, así
  que una línea mal leída se rechaza en lugar de guardarse mal.
- **Aadhaar** (alojamientos en India): el código QR de la tarjeta o del
  e-Aadhaar impreso. Solo se guardan los 4 últimos dígitos del número Aadhaar.

Cualquier escáner USB o Bluetooth que funcione en **modo teclado** (la mayoría
de los lectores de códigos 2D, y los lectores de pasaportes con ajuste de
teclado) funciona sin controlador: pulse **Escanear identificación** y escanee.
En una tableta o un Mac, **Usar cámara** lee el QR con la cámara. Compare
siempre lo leído con la persona que tiene delante, y tome igualmente la
**Foto de la identificación** cuando su registro necesite una copia.

### Registrar la entrada de un grupo completo

Abra el grupo en **Grupos y bloqueos**. En la **Lista de huéspedes del grupo**,
pulse **Registrar entrada del grupo** y confirme. Todas las habitaciones que
llegan hoy entran a la vez; a una habitación aún sin asignar se le da una
habitación libre del tipo reservado. Si no queda habitación libre para alguien,
aparece en una lista y los demás entran igualmente.

Los documentos, los depósitos y la ficha de registro se pueden terminar después
habitación por habitación con **Finalizar** en cada fila, mientras el grupo ya
sube a sus habitaciones.

## Registrar la entrada de un huésped sin reserva previa

Para un huésped que está en el mostrador sin reserva, use **Sin reserva previa** en
la barra superior. Una sola pantalla reserva la estancia, registra el documento, asigna la habitación
y cobra. Los pasos del registro de entrada se abren justo después.

1. Pulse **Sin reserva previa** (o cambie **Nueva reserva** a **Sin reserva previa**).
2. Escriba el **Nombre del huésped**. Si el huésped ya se alojó antes, elíjalo de
   la lista para que la estancia se una a su perfil. Añada el **Teléfono**.
3. Elija el **Tipo de documento de identidad**, escriba el **Número de documento de identidad** y compruebe la
   **Nacionalidad**. Los tipos de documento vienen del paquete de su país.
4. Elija el **Tipo de habitación** y luego la **Habitación**. La lista muestra las habitaciones libres
   esta noche, las limpias primero.
5. Fije las **Noches** y el número de personas. Para una estancia de pocas horas, cambie
   **Durante la noche** a **Uso diurno** y fije la franja horaria.
6. En **Pago**, elija cómo paga el huésped y el **Importe cobrado**.
   Empieza en el total; bájelo para un pago parcial, o póngalo en 0
   para cargarlo todo a la cuenta.
7. Pulse **Cobre ₹2,940 y continúe con el registro de entrada** (o **Continuar con el registro de
   entrada** cuando no se cobra nada).
8. Se abren los pasos del registro de entrada. **Quién paga**, la **Habitación** y el documento que escribió
   ya están hechos; termine el resto y pulse **Registrar la entrada en la habitación 105**.

![La pantalla de huésped sin reserva previa rellenada: huésped, teléfono, documento Aadhaar, habitación Standard 105, una noche, pago en efectivo y la cotización en directo a la derecha](/img/front-desk/walkin.png)

Si la habitación se acaba de ocupar, o su caja está cerrada, no se guarda nada y
la pantalla le dice por qué. Si cierra los pasos del registro de entrada antes del final,
la reserva queda reservada con su habitación: pulse **Finalizar el registro de entrada**, o registre
la entrada del huésped desde **Hoy**.

## Enviar el enlace de autorregistro

Los huéspedes pueden rellenar su registro antes de llegar: tipo y
número de documento, una foto del documento, dirección, hora de llegada y una firma en la
ficha de registro.

- **A mano:** en **Hoy**, pulse **copiar enlace de registro de entrada** en la fila
  de la llegada y péguelo en su mensaje al huésped. Pase antes el cursor por el enlace:
  le indica si enviarlo al huésped, a quien reservó o a ambos. El
  enlace aparece en las llegadas confirmadas que aún no han rellenado el formulario.
- **Automáticamente:** active **Configuración → Recepción → Llegadas → Enviar
  automáticamente enlaces de registro previo**. Cada mañana Kamra envía el enlace a
  los huéspedes que llegan dentro de **Días de anticipación para enviar enlaces** (2 días por defecto).

![La página de registro en línea del huésped en un teléfono: resumen de la estancia, tipo y número de documento, foto del documento, comprobante de domicilio, datos de contacto, normas de la casa y un recuadro para la firma](/img/front-desk/precheckin.png)

Cuando el huésped envía el formulario, la llegada muestra **Registro previo completado**.
Antes de entregar la llave, compare el documento con la persona: abra la
reserva (**Reservas** → púlsela) y pulse **Verificar identidad** en la
tarjeta **Identidad**. Después, el huésped ya no puede cambiar lo que
envió.

## Completar la ficha de registro

Cada estancia tiene una ficha de registro del huésped (GRC) que se puede imprimir. Ábrala desde
**GRC** en una fila de llegada, desde una habitación del panel de habitaciones, desde un
huésped alojado o con **Ficha de registro** en la reserva.

![La ficha de registro de Priya Nair: datos del huésped y de la estancia en la ficha imprimible, y a la derecha la lista de verificación del registro, los documentos y el dinero](/img/front-desk/grc.png)

1. Recorra la **Lista de verificación del registro de entrada** de la derecha: **Documento de identidad del huésped
   registrado**, **Comprobante de domicilio** (opcional), **Ocupantes registrados** y
   **Firma**.
2. En **Documentos**, pulse **Capturar** junto a **Documento de identidad del huésped** o
   **Comprobante de domicilio**. En una tableta o un teléfono esto abre la cámara.
3. Para corregir la nacionalidad del huésped, pulse **editar** junto a
   **Nacionalidad**.
4. Si el huésped llegó o se fue a una hora distinta de la prevista, pulse
   **editar** junto a **Hora real de entrada** o **Hora real de salida**.
5. Debajo de la ficha, rellene el **Registro de ocupantes**: una fila por persona en
   la habitación, con su propio documento. Pulse **Agregar ocupante** para más filas, y luego
   **Guardar registro**. Cuando una fila está guardada, **Capturar documento** en esa fila captura
   el documento del ocupante. La fila de un niño pide solo nombre y edad, salvo que el
   registro de su país también pida documentos de los niños.

   Los huéspedes que comparten habitación no siempre llegan juntos. Cada fila
   tiene su propia hora de **Llegó**: en el registro de entrada, todos los que
   ya están en el registro reciben la hora de entrada, y un huésped añadido
   durante la estancia recibe la hora en que se guardó. Corríjala en la fila,
   o pulse **Llegó ahora**. Cuando un huésped se va antes que los demás, fije
   **Se fue** (o **Se fue ahora**). La ficha de registro imprime la llegada de
   cada huésped, y la tarjeta **Estancia** de la reserva muestra quién está en
   la habitación.
6. Pulse **Imprimir ficha de registro** y pida al huésped que firme. Un huésped que firmó en línea
   ya tiene su firma en la ficha.

![El registro de ocupantes: nombre completo, edad, sexo, nacionalidad, tipo y número de documento de cada persona, con Agregar ocupante y Guardar registro](/img/front-desk/grc-occupants.png)

El recuadro **Resumen de pagos** muestra los cargos, los pagos y el saldo; **Abrir cuenta**
lleva al folio.

## Cambiar a un huésped de habitación

1. Abra el cambio desde cualquiera de estos sitios:
   - **Cambiar de habitación** en la ficha de registro,
   - **Cambiar de habitación** (o **Asignar habitación**) en la tarjeta **Habitación** de la reserva,
   - la barra del huésped en el [calendario de ocupación](/es/reservations#mover-una-estancia-en-el-calendario-de-ocupacion).
2. Elija una habitación. **Mismo tipo** muestra habitaciones del tipo reservado; **Todos los tipos
   (mejora de categoría)** muestra todos los tipos. Las habitaciones libres y limpias aparecen primero; las reservadas
   aparecen en gris.
3. Si cambia a otro tipo de habitación, elija el precio en **Tarifa**:
   - **Tarifa de la nueva habitación**: la estancia se cobra al precio del nuevo tipo.
   - **Mantener el precio actual**: el huésped mantiene la tarifa que reservó, por
     ejemplo en una mejora de categoría gratuita.
   - **Introducir una tarifa**: escriba una tarifa por noche acordada con el huésped. Solo
     Responsable de ingresos y Administrador del hotel ven esta opción.

   La línea de precio de abajo muestra la diferencia y el nuevo total
   antes de cambiar nada. El folio factura el precio que eligió.
4. Elija un motivo (**Solicitud de huésped**, **Mejora de categoría**, **Mantenimiento**, **Ruido
   o queja**, **Otro**), añada una nota si quiere y pulse **Cambiar a la
   habitación 303**.

![La ventana Cambiar de habitación con Todos los tipos seleccionado, la habitación 303 elegida y la línea de precio que indica que la Suite cuesta ₹10,395 más](/img/front-desk/change-room.png)

Si el huésped ya está alojado, la habitación anterior se marca como Sucia para
limpieza. Cada cambio queda en el registro de actividad con su motivo.

## Registrar la salida de un huésped

La salida es una hoja guiada corta. Ábrala desde cualquiera de estos sitios:

- **Hoy → Salidas**: **Registrar salida** en la fila del huésped.
- **Hoy → Habitaciones**: toque una habitación ocupada y luego **Registrar salida**.
- **Calendario de ocupación**: pulse la estancia y luego **Registrar salida**.
- El panel de detalle de la reserva: **Registrar salida**.
- La paleta de comandos (Ctrl+K o Cmd+K): escriba **check out** y el número de
  habitación o el nombre del huésped.

![La lista de salidas con un botón Registrar salida en cada fila](/img/front-desk/departures.png)

La hoja muestra solo los pasos que necesita esta estancia, en este orden. Un
huésped que se va antes de la fecha reservada empieza por **Salida anticipada**:

0. **Salida anticipada.** Muestra cuántas noches reservadas no usará el
   huésped y lo que su **Cargo por salida anticipada** hace con ellas: **Sin
   cargo**, **Una noche** o **Todas las noches sin usar**, cada opción con su
   importe (la tarifa de esas noches). Escriba el motivo y pulse **Acortar la
   estancia**. La estancia termina ahora hoy, por el mismo camino que cambiar
   las fechas de la reserva: la habitación vuelve a la venta, se avisa al
   channel manager y el precio se recalcula para las noches alojadas. La
   salida factura entonces solo esas noches, más una línea **Salida
   anticipada** por el cargo, en la cuenta que paga la habitación (la de la
   empresa, cuando paga la habitación). Cada noche sin usar lleva el impuesto
   que habría llevado su cargo de habitación, así que las noches en tramos de
   impuesto distintos dan una línea por tipo. La línea es su propio tipo de
   cargo, **Salida anticipada** (código de transacción 1220, grupo de ingresos
   Otros): aparece como otros ingresos en el Resumen gerencial y en los informes del día,
   nunca como noche de habitación, así que la ocupación, el ADR y el RevPAR
   cuentan solo las noches que el huésped se alojó. Finanzas y los
   Administradores del hotel pueden elegir otro cargo para esta estancia; los
   demás aplican la política del alojamiento. La fecha reservada y el motivo
   quedan en la reserva y aparecen en el informe **Salidas anticipadas**. Con
   la política en **Todas las noches sin usar** puede **Saltar** el paso y
   todas las noches reservadas siguen en la cuenta, como antes; con cualquier
   otra política hay que acortar la estancia antes de la salida.

![La hoja de salida de Priya Nair en el paso Cuenta: quién paga, por qué este total y el resumen de la estancia](/img/front-desk/checkout-sheet.png)

1. **Cuenta.** Todos los folios de la estancia con sus líneas, tal como quedarán en
   la salida: se incluyen las noches que la auditoría nocturna aún no ha cargado.
   Los pedidos del restaurante o del servicio a la habitación y la lavandería que aún no están en el folio
   aparecen aquí, cada uno con una línea sobre qué hacer:
   - una cuenta del restaurante: **Cargar a la habitación** la añade a la cuenta; **Liquidar
     por separado** la cobra en el punto de venta.
   - la ropa que sigue en la lavandería (Recogida o En proceso) aún no se puede
     facturar. Cuando la bolsa vuelva a recepción, pulse **Prendas devueltas: marcar como
     listas** y luego **Devolver y cargar a la habitación**.
   - la ropa que está Lista: **Devolver y cargar a la habitación** marca cada
     prenda como devuelta y la añade a la cuenta.

   Las cuentas abiertas nunca detienen la salida. Si alguna sigue abierta en el
   paso **Registrar salida**, la hoja la muestra en **Aún no está en la cuenta**:
   si se carga más tarde, va al folio de la estancia ya cerrada y hay que
   cobrarla por separado. Mover la ropa de lavandería corresponde a Recepción y
   Limpieza; a un rol que no puede hacerlo se le indica quién puede.
2. **Salida tardía.** Solo cuando el huésped se va después de su hora de
   salida. Introduzca el cargo que cobra su hotel y pulse **Agregar cargo por salida
   tardía**, o **Saltar** para eximirlo. Kamra nunca sugiere un importe.
3. **Cuenta de la empresa.** Solo cuando una empresa con crédito paga parte de la
   estancia. Muestra qué folio pasa a la cuenta de la empresa (las cuentas
   por cobrar a empresas) y la comprobación de crédito de la empresa. Marque la casilla cuando el huésped
   esté de acuerdo. Si el crédito de la empresa está bloqueado, Finanzas o un Administrador del hotel
   pueden escribir un motivo para anularlo; el motivo queda registrado con su nombre.
   Si la empresa cambió, pulse aquí **Cambiar empresa** (o en **Quién
   paga**, en el primer paso); consulte
   [Facturar a una empresa](/es/billing#facturar-a-una-empresa).
4. **Pago.** Solo cuando todavía se debe dinero en un sentido u otro.
   - El huésped debe dinero: elija el medio de pago, añada una referencia si
     quiere y pulse **Cobrar**.
   - El huésped pagó de más: Kamra muestra de dónde sale el dinero (un
     depósito de garantía retenido, o un pago superior a la cuenta) y el medio por el que
     se devuelve (el mismo por el que entró). Mantenga o cambie el motivo y
     pulse **Reembolso**. Un depósito de garantía se devuelve mediante el reembolso
     propio del depósito, para que se liberen el registro del depósito y su cuenta.
   - ¿Daños en la habitación? **Retener por daños** retiene antes una parte del
     depósito.

   El dinero pasa por su caja. Si está cerrada, la hoja muestra **Su caja
   está cerrada**: cuente el efectivo del cajón, introdúzcalo como
   **Fondo inicial de caja** (0 si está vacío) y pulse **Abrir mi caja**. Usted
   sigue en la hoja. Recepción, Finanzas y los Administradores del hotel pueden abrir su
   propia caja; la cierra al final de su turno en **Finanzas →
   Cajero**. Se pide el PIN de cajero cuando su hotel lo exige.
5. **Atención al huésped.** La rutina de salida de su hotel (pedir opinión, despedirse).
   Marque cada punto, o **Saltar**.
6. **Registrar salida.** Pulse **Registrar salida**. Recepción y los Administradores del hotel pueden
   registrar la salida de un huésped. Finanzas puede liquidar la cuenta en esta hoja, pero el
   botón **Registrar salida** sigue desactivado para ellos e indica quién puede pulsarlo.
7. **Factura.** Pulse **Cerrar y generar factura** en cada folio (o
   **Generar todas las facturas**) y luego **Ver o imprimir**. La factura va
   después de la salida a propósito: la salida aún puede cargar la última noche y
   mover la parte de la empresa, y un folio facturado antes de eso queda congelado.
   Emitir una factura también requiere su caja abierta; la misma tarjeta **Abrir mi caja**
   aparece aquí cuando está cerrada.

Si algo detiene un paso, el motivo aparece dentro de la hoja junto a ese
paso, con lo que hay que hacer (abrir la caja, abrir el folio). Un paso fallido
no cambia nada, y la hoja vuelve a cargar la cuenta después de cada acción.

En un grupo, la hoja registra la salida de una habitación cada vez y muestra los demás
huéspedes del grupo que siguen alojados, cada uno con su propio **Registrar
salida**.

Después de la salida, la habitación se marca como Desocupada y Sucia, y limpieza recibe
una limpieza de salida de prioridad alta. Cada paso (pago, reembolso, salida,
factura) queda en el registro de actividad con el nombre de la persona que lo
hizo.

### Deshacer una salida

¿Registró la salida de la habitación equivocada, o el huésped se queda al
final? Abra la estancia, pulse **Deshacer salida** e indique el motivo. El
huésped vuelve a estar alojado en la misma habitación:

- la factura emitida en la salida se cancela y se conserva en el registro de
  facturas canceladas (donde el país lo exige, se emite una nota de crédito);
  la siguiente salida recibe un número nuevo
- una cuenta que pasó a la cuenta de la empresa sale de ella
- la habitación vuelve a estar ocupada y se elimina la limpieza de salida

Funciona hasta que se ejecuta la auditoría nocturna. Se rechaza si hay otra
persona en la habitación, o si la empresa ya pagó parte de la cuenta; esos
casos los corrige Finanzas en la cuenta de la empresa.

## Buscar un huésped

**Recepción → Huéspedes** muestra todos los huéspedes con sus reservas, estancias,
noches, valor total y última estancia. Busque por nombre o teléfono, y pulse un
huésped para abrir su historial.

- **Columnas** elige qué columnas se muestran. Su elección se guarda en este
  navegador.
- **Exportar** descarga la lista como archivo CSV con las columnas que ve.
  La lista muestra hasta 200 huéspedes, así que busque primero si la lista es más larga.

![La lista de huéspedes con teléfono, reservas, estancias, noches, valor total y última estancia](/img/front-desk/guests.png)

El historial muestra cada estancia y cada evento, con:

- **Reservar una estancia** para empezar una reserva ya vinculada a este huésped,
- **Notas y preferencias** y la casilla **VIP** (los huéspedes VIP tienen una estrella en
  todas las pantallas),
- **Acciones del perfil**: **Agregar huésped a la lista de bloqueo**, **Fusionar un duplicado**,
  **Anonimizar perfil** y **Exportar datos del huésped**.

![El historial de un huésped: estancias anteriores, totales, notas y preferencias, VIP y acciones del perfil](/img/front-desk/guest-journey.png)

## Cambiar la tarifa de un huésped alojado

Alargar una estancia puede cambiar su tarifa: cinco noches pueden alcanzar un
descuento por estancia larga que cuatro no alcanzaban. Kamra nunca vuelve a
tarifar una noche ya cargada en el folio. El ajuste de cambio de tarifa de su
alojamiento decide qué pasa con esas noches:

- **Mantener las noches cargadas** (por defecto): las noches cargadas
  conservan su tarifa; solo las noches que quedan toman la nueva. El total de
  la reserva y el folio siguen iguales. Cuando cambia las fechas en el
  calendario de ocupación, la línea de precio indica cuánto se habría ahorrado
  el huésped en las noches cargadas; puede devolvérselo con una
  [bonificación](/es/billing#corregir-un-cargo) y un motivo.
- **Abonar la diferencia**: cuando la nueva tarifa es más baja, Kamra registra
  un abono **Rate Adjustment** por cada noche cargada, con fecha de hoy, en el
  folio al que fue la noche. El abono lleva el impuesto de la tarifa original
  de la noche, aunque la tarifa más baja caiga en un tramo de impuesto
  inferior: corrige la venta original. Una tarifa más alta nunca se suma a una
  noche ya cargada. Los ajustes de tarifa cuentan como ingresos de habitación
  (ADR, RevPAR, Resumen gerencial) pero no como habitaciones vendidas.
- **Corregir tarifas de fechas pasadas**: las fechas cambian igual que con
  Mantener. Después, Finanzas o un Administrador del hotel pueden corregir las
  noches cargadas desde el folio; consulte
  [Corregir noches cargadas](/es/billing#corregir-noches-cargadas).

## Configuración

| Ajuste | Dónde | Valor por defecto | Qué hace |
| --- | --- | --- | --- |
| Hora de entrada / Hora de salida | Configuración → Políticas de estancia | 14:00 / 11:00 | Se imprime en la ficha de registro y en la página de registro en línea. |
| Enviar automáticamente enlaces de registro previo | Configuración → Recepción → Llegadas | Desactivado | Envía cada mañana el enlace de autorregistro a las próximas llegadas. |
| Días de anticipación para enviar enlaces | Configuración → Recepción → Llegadas | 2 días | Con cuánta antelación a la llegada se envía el enlace automático. |
| Exigir registro previo antes de dar instrucciones de acceso | Configuración → Recepción → Llegadas | Desactivado | Retiene las **Instrucciones de acceso** (códigos de puerta, wifi) hasta que el huésped haya hecho el registro en línea. |
| Conservación de documentos de huéspedes | Configuración → Privacidad y datos | Verificar y eliminar | Verificar y eliminar oculta los números de documento salvo los 4 últimos dígitos y borra las fotos de los documentos en la salida. Conservar los guarda. |
| Cuando cambia la tarifa de una estancia con noches ya cargadas | Configuración → Políticas de estancia → Cambios de tarifa durante la estancia | Mantener las noches cargadas | Consulte [Cambiar la tarifa de un huésped alojado](#cambiar-la-tarifa-de-un-huesped-alojado). |
| Depósito de garantía | Configuración → Políticas de estancia → Anticipos y depósitos de garantía | 0 | Un importe reembolsable que se retiene durante la estancia. Si se fija, el registro de entrada tiene un paso **Depósito de garantía y anticipo**. Mientras está retenido, la reserva le avisa antes de la salida. |
| Pasos del registro de entrada | Configuración → Recepción → Pasos del registro de entrada | Consulte [Los pasos](#los-pasos) | Qué pasos del registro de entrada son obligatorios. Los pasos obligatorios no se pueden saltar y bloquean el registro de entrada hasta que se completan. |
| Cargo por salida anticipada | Configuración → Políticas de estancia → Cancelación y no presentación | Todas las noches | Lo que paga por las noches sin usar un huésped que se va antes de la fecha reservada: Ninguno, Una noche o Todas las noches (tarifa de la habitación). Finanzas o un Administrador del hotel pueden cambiarlo para una estancia, con un motivo. |
| Enviar un WhatsApp al huésped cuando se carga algo a la habitación | Configuración → Recepción → Avisos al huésped | Desactivado | Envía la plantilla de cargo a la habitación (consulte [WhatsApp](/whatsapp)) cuando un cargo del restaurante, la lavandería, el minibar o recepción llega a la cuenta de un huésped alojado. |
| Nombre de la red wifi, Contraseña Wi-Fi, Horario del desayuno, Número de emergencia, Información adicional para huéspedes | Configuración → Recepción → Información al huésped durante la llegada | Vacío | Se muestra en el paso **Wifi e información de la estancia**, para decirlo, imprimirlo o enviarlo por WhatsApp. La contraseña nunca se escribe en el registro de actividad. |

## Conviene saber

- El registro de entrada espera a los pasos que su alojamiento marca como **Obligatorio**. Con los
  valores por defecto, eso incluye el documento del huésped y de todos los que se alojan.
- Un huésped sin reserva previa siempre llega hoy. Para una fecha futura, cree una reserva
  normal.
- Una reserva necesita una habitación antes del registro de entrada. Las estancias de villa completa registran la entrada como
  una sola unidad.
- El saldo en **Hoy** incluye las noches que la auditoría nocturna aún no ha cargado,
  así que coincide con lo que el huésped debe en la salida.
- Una habitación cuyo huésped debe salir hoy pero sigue alojado no se ofrece
  para un registro de entrada ni para un huésped sin reserva previa hasta que ese huésped registre su salida.
- **Agregar huésped a la lista de bloqueo** es para Administradores del hotel. Hace falta un motivo tanto para añadirlo
  como para quitarlo, y queda en el registro de actividad.

## Solución de problemas

**"Cannot check out: … is still owed."** Use el botón **Registrar salida**:
su paso **Pago** cobra el importe. Para una empresa que paga más tarde,
transfiera el saldo a las cuentas por cobrar a empresas desde el folio.

**"Invoice … is issued, its charges are frozen"** en la salida. El folio
se facturó antes de cargar todas las noches. La hoja de salida lo indica en
su primer paso: abra el folio, anule la factura y luego registre la salida. La
hoja emite la factura por usted después.

**"Complete primero estos pasos de llegada: …"** Falta un paso obligatorio.
Abra el registro de entrada desde **Hoy** y termine los pasos que indica el mensaje.
Para cambiar qué pasos son obligatorios, consulte
[Elegir qué pasos son obligatorios](#elegir-que-pasos-son-obligatorios).

**"… es obligatorio en este alojamiento y no se puede omitir."** Solo los pasos opcionales
tienen **Saltar**. Haga el paso, o pida a un Administrador del hotel que lo haga opcional.

**"Room 204 cannot take charges to the room (set at check-in)."** Recepción
bloqueó los cargos a la habitación. Cobre en el punto de venta, o abra los
pasos del registro de entrada de la reserva y permita los cargos en **Cargos a la habitación**.

**"Asigne una habitación antes de registrar la entrada."** La reserva no tiene habitación. Use **Asignar
habitación** en la reserva o en la ficha de registro, o registre la entrada desde **Hoy**, donde elige
la habitación en el mismo paso.

**"NO_OPEN_SESSION: open your till under Finance → Cashier first."** Intentó
cobrar sin una caja abierta. Las hojas de registro de entrada, de huésped sin reserva previa y de
salida muestran **Su caja está cerrada** con un botón **Abrir mi caja**
en su lugar: introduzca el fondo inicial y púlselo. También puede abrirla
en **Finanzas → Cajero → Mi caja**, o poner en 0 el **Importe
cobrado** de un huésped sin reserva previa. Un establecimiento pequeño sin cajón de efectivo puede desactivar las cajas:
**Configuración → Finanzas → Controles de caja → Gestionar dinero mediante
cajas**. Los pagos y reembolsos se registran entonces sin caja; los pagos de caja,
las retiradas de efectivo, la caja chica y el cambio de divisa siguen necesitándola.

**El botón Cobrar, Reembolso o Continuar aparece en gris.** El motivo está
escrito al lado: abra su caja, marque la confirmación de la empresa, escriba
un motivo de anulación, o cobre (o exima) el depósito.

**"Su rol no permite abrir una caja."** Su rol (por ejemplo Limpieza o
Ingresos) no cobra dinero. Pida ayuda a Recepción, Finanzas o un Administrador del hotel.

**"Solo Recepción o un administrador del hotel pueden registrar la entrada."** Finanzas y
otros roles pueden ver una llegada, pero no registrar su entrada.

**Una bolsa de lavandería muestra "Aún en lavandería".** No se puede facturar hasta que
vuelva. Pulse **Prendas devueltas: marcar como listas** cuando esté en recepción y luego
**Devolver y cargar a la habitación**. Si el huésped se va antes, registre la salida
igualmente: cargue la bolsa más tarde desde **Lavandería** y cóbrela por separado.

**"Room … is still occupied by … Check them out first, or choose another
room."** El huésped anterior sigue alojado en esa habitación. Registre su salida
en **Hoy** (en **Salidas**), o elija otra habitación.

**El panel de registro de entrada dice "No hay habitaciones disponibles de este tipo para estas fechas".**
Todas las habitaciones del tipo están ocupadas. Abra el [calendario de ocupación](/es/reservations#mover-una-estancia-en-el-calendario-de-ocupacion)
para mover otra estancia o mejorar la categoría de esta.

## Para desarrolladores

Los pasos del registro de entrada son `kamra.checkin.checkin_flow` y un endpoint por
paso (`save_guest_details`, `confirm_billing`, `assign_checkin_room`,
`sign_registration_card`, `issue_keys`, `log_checkin_requests`,
`set_room_charges`, `complete_checkin_step`, `skip_checkin_step`), y después
`kamra.api.check_in`, que se niega mientras haya un paso obligatorio abierto
(`kamra.checkin.check_in_readiness` indica lo que falta). Los pasos y
cuáles son obligatorios están en el procedimiento de registro de entrada del alojamiento (`kamra.sop`). El
huésped sin reserva previa es `kamra.api.walk_in` (`defer_check_in=1` reserva y pasa a
los pasos); la salida es `kamra.api.check_out` (con `early_reason` /
`early_fee` acorta primero una salida anticipada); la salida anticipada por
sí sola es `kamra.api.early_departure` y su plan es `early_departure` en
`kamra.api.checkout_context`; los cambios de
habitación usan `kamra.api.movable_rooms`, `kamra.api.room_move_preview` y
`kamra.api.move_reservation`. El diseño de Hoy es
`kamra.today_layout.get_today_layout`, `save_today_layout`,
`reset_today_layout` y `save_today_layout_default` (Administrador del hotel). Los agentes de IA usan las herramientas `front_desk_today`,
`check_in_readiness`, `check_in`, `check_out`, `early_departure`, `move_room`, `guest_lookup`, `guest_journey` y
`update_occupants`. Consulte [MCP tools](/mcp-tools) y la
[referencia de la API](/api-reference).
