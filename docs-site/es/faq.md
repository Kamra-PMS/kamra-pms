# Preguntas frecuentes

## ¿Hay algo reservado para un plan de pago?

**No.** Todas las funciones son de código abierto y están incluidas en
todas partes. Las opciones de pago son trabajos de implantación, soporte y
configuración (pasarela de WhatsApp, pasarela de pago). Son servicios, no
funciones bloqueadas. Los archivos de exportación GSTR-1 son gratuitos para
todos.

## ¿Por qué no hay precio por habitación?

Añadir habitaciones no hace que el software cueste más, así que cobrar por
habitación es un impuesto a su crecimiento. Instalarlo en su propio
servidor es gratis con cualquier tamaño; el precio en la nube solo depende
del servidor que necesite su alojamiento.

## ¿Cuáles son las credenciales de acceso por defecto?

No hay. Después de `bench new-site … --admin-password <password>`, abra
`/kamra` e inicie sesión como **Administrator** o **admin@example.com**
con esa contraseña. Si la olvidó:
`bench --site <site> set-admin-password <new-password>` (en Docker, añada
delante `docker compose exec backend`). Después, cada miembro del personal
debe tener su propio acceso con su correo electrónico.

## ¿Qué hace falta de verdad para instalarlo en mi propio servidor?

Un VPS de 2 vCPU / 4 GB / 40 GB (~₹549-$24 al mes), un dominio y una
tarde. Consulte las [guías](/self-hosting/). Usted se encarga de las
actualizaciones y las copias de seguridad; cada una es un solo comando.

## ¿Puedo pasar de la nube a mi propio servidor y al revés?

Sí, en ambas direcciones. Es Frappe estándar: `bench backup` genera un
archivo completo con la base de datos y los ficheros que se restaura en
cualquier sitio.

## ¿La IA fija alguna vez precios o impuestos?

No. Las tarifas, los impuestos, la disponibilidad y los cargos de las
políticas son código determinista, verificado por un conjunto de pruebas
automáticas en CI. Los agentes de IA llaman a herramientas controladas
como usuarios con permisos verificados y no pueden saltárselas.

## ¿Qué versión de Frappe necesita Kamra?

Frappe **v16** (con la aplicación `payments`). Instale desde la rama `main`
para la versión estable; `develop` es el canal nocturno.

## ¿Cómo instalo Kamra desde Frappe Cloud Marketplace?

Cree un bench Frappe v16 **privado** (no un sitio de prueba compartido),
añada [Kamra desde el marketplace](https://frappecloud.com/marketplace/apps/kamra),
despliegue, instálelo en el sitio y después abra `/kamra/setup`. Paso a
paso: [Instalar con Frappe Cloud](/self-hosting/frappe-cloud). ¿Prefiere su
propio VPS? Use las [guías de instalación en su servidor](/self-hosting/):
es el mismo software.

## ¿Kamra del Marketplace incluye ERPNext o RR. HH.?

**No.** Kamra se instala solo con `payments`. La contabilidad de la empresa
(ERPNext) y las nóminas (Frappe HR) son aplicaciones opcionales en el
**mismo sitio** cuando las quiera, en Frappe Cloud o en su propio servidor.
Consulte [ERPNext y Frappe HR](/self-hosting/erpnext-hr).

## ¿Cómo numera Kamra sus propias versiones?

**Primero parches.** Las funciones pequeñas y las correcciones se publican
como `2.6.1`, `2.6.2`, etc. Un salto mayor tipo `2.7.0` solo ocurre cuando
los mantenedores lo deciden a propósito, no de forma automática con cada
commit `feat:`. Consulte el
[registro de cambios](https://github.com/Kamra-PMS/kamra-pms/blob/main/CHANGELOG.md)
y las [notas de publicación](https://github.com/Kamra-PMS/kamra-pms/blob/main/RELEASING.md)
en el repositorio.

## ¿Puedo volver a una versión anterior después de probar una más nueva?

**No desde un botón en `/kamra`.** Estado del sistema solo explica cómo
actualizar; no cambia la instalación. En un sitio Docker en su propio
servidor, vuelva a fijar la versión que quiera:

```bash
sudo KAMRA_TAG=v2.6.16 /opt/kamra/install.sh update
```

Use la etiqueta que tenía antes. Las actualizaciones siempre hacen primero
una copia de seguridad; si la migración ya ha avanzado la base de datos,
restaure esa copia cuando la imagen anterior no funcione bien. Detalles:
[Going back (downgrade)](/quickstart#going-back-downgrade).

## ¿Cómo informo de un error o pido una función?

[Issues de GitHub](https://github.com/Kamra-PMS/kamra-pms/issues) para
errores y peticiones, y las discusiones para preguntas. Informes de
seguridad: consulte `SECURITY.md` y no abra issues públicos para ellos.

## ¿Quién desarrolla Kamra?

[HeyKoala](https://heykoala.ai). El PMS es nuestra base de código abierto;
ganamos dinero alojándolo y creando personal de hotel con IA sobre él, no
bloqueando funciones.
