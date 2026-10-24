/** How a property's pet charge reads next to its price - one wording for
 * the booking dialog and both public pages. */
export function petChargeBasis(
  basis: string | null | undefined,
  translate: (source: string) => string = (source) => source,
) {
  return basis === "Per night"
    ? translate("per pet per night")
    : translate("per pet per stay")
}
