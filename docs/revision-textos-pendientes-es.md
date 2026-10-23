# Textos adicionales de la interfaz hotelera en español

Fecha: 23 de octubre de 2026. Base de comparación: `e79a161c`.

## Resultado

- Se agregaron **2.387 entradas** al recurso español: pasó de 2.809 a **5.196**.
- Las 2.809 traducciones españolas previas conservaron sus claves y valores.
- Las **2.151 traducciones árabes** conservaron sus claves y valores; `ar.json` no se modificó.
- Se conectaron al traductor textos de interfaz que estaban escritos directamente en inglés, además de etiquetas procedentes de listas y mensajes conocidos del servidor.
- Se eliminó la función provisional `spanish()` / `localize()`. La traducción utiliza el sistema existente `t()`, `tn()` y `useT()`.

El usuario autorizó que las etiquetas recién conectadas utilicen las traducciones árabes existentes cuando estén disponibles. Por ello, algunas etiquetas que antes aparecían en inglés dentro del modo árabe ahora pueden aparecer en árabe. Las claves que no tienen traducción conservan el texto de origen.

## Áreas revisadas

| Área | Cambios principales |
| --- | --- |
| Recepción y reservas | Etiquetas, solicitudes especiales, persona que reserva, relación con el huésped, reservas de varias habitaciones, disponibilidad y ayudas de formularios. |
| Habitaciones y calendario | Textos de disponibilidad, ventanas de detalle, accesibilidad, nombres de meses y días de la semana en español. |
| Caja, folios y contabilidad | Encabezados, medios de pago, estados, crédito de empresas, cuentas por cobrar, informes y ayudas. |
| Restaurante y cocina | Pedidos, comandas, preparación, servicio a la habitación, pedidos para llevar y a domicilio, jefe de servicio y comensales. |
| Banquetes | Eventos, cotizaciones, documentos, montaje, camerino, asistentes, cobros, costos de recetas y requisiciones de cocina. |
| Limpieza y lavandería | Órdenes, servicios, tarifas, recuento de prendas y comprobantes. |
| Inventario | Entradas y salidas de existencias, recuentos, compras, unidades y registros de movimientos. |
| Administración | Configuración, permisos, integraciones, mensajes de error, importaciones y pasos del asistente. |
| Páginas de huéspedes | Etiquetas de reserva y registro de entrada, estados y mensajes de la interfaz pública. |
| Impresión térmica | Encabezados de cuentas, comandas anuladas, reimpresión, cortesía, importes y comprobantes de lavandería. |

## Ejemplos y criterios hoteleros

| Texto de origen | Español | Contexto |
| --- | --- | --- |
| `Captain: {name}` | Jefe de servicio: {name} | Responsable del servicio de restaurante. |
| `{diners} guests` | Comensales: {diners} | Personas atendidas en restaurante/cocina. |
| `Green room` | Camerino | Banquetes y eventos. |
| `Kitchen indent` | Requisición de cocina | Necesidades de ingredientes para un evento. |
| `Room and F&B` | Habitación y alimentos y bebidas | Cargos que paga una empresa. |
| `{n} billable` | Personas facturables: {n} | Asistentes por los que se cobra el evento. |
| ` · {n} guaranteed` | · garantizadas: {n} | Cantidad garantizada de asistentes. |
| ` · {n} actual` | · asistentes reales: {n} | Recuento efectivo del evento. |
| `LAUNDRY DOCKET` | COMPROBANTE DE LAVANDERÍA | Documento de prendas recibidas. |
| `Counted with the guest. Billed to the room.` | Prendas contadas con el huésped. Cargo a la habitación. | Control y cobro de lavandería. |
| `*** VOID *** KOT #{number}` | *** ANULADA *** COMANDA N.º {number} | Anulación de una comanda de cocina. |
| `COMPLIMENTARY - NO CHARGE` | DE CORTESÍA: SIN CARGO | Cuenta o servicio de cortesía. |
| `TAKEAWAY` / `DELIVERY` | PARA LLEVAR / A DOMICILIO | Destino del pedido. |
| `Qty` / `Amt` | Cant. / Importe | Columnas de una cuenta impresa. |
| `Store` | Conservar | Retención de imágenes de documentos de identidad. |

Se mantiene la distinción revisada de **tarifa** para precios de alojamiento o servicios, **tasa impositiva** para porcentajes fiscales y **tipo de cambio** para divisas. Los encabezados fiscales y de divisas emplean claves específicas para evitar que el significado general de `Rate` se aplique fuera de contexto.

## Uso del traductor existente

- `t(texto, variables)` traduce una etiqueta o frase.
- `tn(cantidad, singular, plural, variables)` elige entre las dos frases indicadas y luego traduce. Se conserva el mecanismo de pluralización existente.
- `useT()` mantiene las etiquetas actualizadas cuando cambia el idioma.
- `translate` y, en dos archivos, `translateUI` son alias de importación de `t`; evitan conflictos con variables o marcadores de extracción llamados `t` o `translate`. No son motores de traducción adicionales.
- Se centralizaron los diccionarios en [`frontend/src/lib/locales.ts`](../frontend/src/lib/locales.ts).
- Para agregar otro idioma se incorpora su JSON al registro de diccionarios y se agrega su entrada al selector de idiomas en `lib/dir.ts`.
- El traductor reconoce plantillas conocidas de etiquetas y mensajes que llegan con números, fechas o monedas ya insertados. Un mensaje desconocido conserva su texto de origen.

[`thermal.ts`](../frontend/src/lib/thermal.ts) importa `t as translate` desde `./i18n`; no utiliza `spanish()` ni `localize()`.

## Datos y compatibilidad

- Se agregaron valores explícitos a **47 opciones** que antes tomaban su valor del texto visible. Así, traducir una opción no cambia el código enviado al servidor. La cantidad de opciones de esos archivos se conservó.
- Se conservaron los identificadores de registros, estados internos, campos de API, encabezados técnicos de CSV y códigos de monedas.
- Se conservaron nombres de personas, empresas y alojamientos, notas y descripciones libres. No se implementó traducción automática del contenido de los usuarios ni de conversaciones generadas por IA.
- Se conservaron marcas, nombres propios, abreviaturas técnicas, ejemplos de identificadores fiscales y medidas de impresoras.
- Se conservaron los títulos legales bilingües y los datos del QR de las facturas.
- El registro de idiomas y la dirección de lectura en `lib/dir.ts` no se modificaron.
- Los formatos de fecha anteriores de inglés y árabe se conservaron; el español usa sus nombres de meses y días.
- No se modificaron archivos Python ni los cálculos de reservas, impuestos o cobros.

## Comprobaciones realizadas

- Revisión de literales de JSX, atributos visibles, listas de etiquetas, textos construidos con variables, recibos y mensajes conocidos del servidor.
- Comparación completa de los recursos contra `e79a161c`: cero claves o valores españoles previos modificados y diccionario árabe idéntico.
- JSON sin claves duplicadas ni traducciones vacías.
- Catálogo con **5.196 claves**, sin duplicados ni celdas vacías en la columna española; las columnas española y árabe coinciden con sus JSON.
- Se conservaron los marcadores de datos. Hay cuatro omisiones gramaticales intencionales: los dos sufijos anteriores `{ord}` y `{ies}`, y los sufijos ingleses de `dish{v1}` y `line{v1}`. Esas traducciones expresan el recuento sin formar plurales a partir del sufijo inglés.
- Búsqueda de llamadas a `spanish()` y `localize()` e importaciones del módulo provisional: sin referencias restantes en el código del frontend.
- `git diff --check`: correcto.
- `cd frontend && npm run build`: correcto, incluidos TypeScript y Vite. Vite informa que el paquete principal supera 500 kB; la compilación concluye correctamente.
- Se regeneraron los archivos de `kamra/public/frontend`, como requiere la plantilla de contribución.

Esta revisión cubre recursos y contextos de código. No incluye un recorrido visual exhaustivo de todas las pantallas ni garantiza traducir mensajes arbitrarios de servicios externos, contenido libre o datos de cada hotel.

## Consulta de los cambios

El texto completo de las traducciones está en [`es.json`](../frontend/src/i18n/locales/es.json). El [`catálogo CSV`](../frontend/src/i18n/catalog.csv) contiene el origen, el español, el árabe y las referencias de código detectadas por el extractor. Su comparación con `e79a161c` permite consultar cada entrada agregada.

Revisiones anteriores: [terminología hotelera](revision-traducciones-es.md) y [usos de «rate»](revision-rate-es.md).
