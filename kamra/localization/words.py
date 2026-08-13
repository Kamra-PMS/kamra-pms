"""Amounts in words - the line every invoice in India ends with, and most
of the rest of the world expects too.

Two scales, because they genuinely differ: the Indian system groups after
the first thousand in twos (lakh = 10^5, crore = 10^7), the international
one in threes (million, billion). "Rupees One Lakh Twenty Thousand Only"
and "One Hundred Twenty Thousand" are the same number written by two
different conventions, and a hotel in Bengaluru billing a guest expects
the first.

Deliberately self-contained rather than frappe.utils.money_in_words: that
reads the site's number format and the Currency master's fraction records,
which a fresh site may not carry - and an invoice line that silently comes
out empty is worse than one that's slightly plain.
"""

from decimal import ROUND_HALF_UP, Decimal

ONES = ("", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight",
        "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen",
        "Sixteen", "Seventeen", "Eighteen", "Nineteen")
TENS = ("", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy",
        "Eighty", "Ninety")

# currency code -> (main unit, fractional unit). Anything unlisted falls
# back to the bare code, which still reads correctly: "USD Twelve Only".
CURRENCY_WORDS = {
	"INR": ("Rupees", "Paise"),
	"USD": ("Dollars", "Cents"),
	"EUR": ("Euros", "Cents"),
	"GBP": ("Pounds", "Pence"),
	"AED": ("Dirhams", "Fils"),
	"THB": ("Baht", "Satang"),
	"IDR": ("Rupiah", "Sen"),
	"MYR": ("Ringgit", "Sen"),
	"SGD": ("Dollars", "Cents"),
	"LKR": ("Rupees", "Cents"),
	"NPR": ("Rupees", "Paisa"),
}


def _under_hundred(n: int) -> str:
	if n < 20:
		return ONES[n]
	tens, ones = divmod(n, 10)
	return TENS[tens] + (f" {ONES[ones]}" if ones else "")


def _under_thousand(n: int) -> str:
	hundreds, rest = divmod(n, 100)
	parts = []
	if hundreds:
		parts.append(f"{ONES[hundreds]} Hundred")
	if rest:
		parts.append(_under_hundred(rest))
	return " ".join(parts)


def _grouped(n: int, groups) -> str:
	"""Walk the scale from the top down. `groups` is (divisor, name) largest
	first; whatever is left over at the end is the last three digits."""
	parts = []
	for divisor, name in groups:
		count, n = divmod(n, divisor)
		if count:
			# a lakh can itself be "One Hundred Twenty" lakh
			parts.append(f"{_grouped(count, groups) if count > 999 else _under_thousand(count)} {name}")
	if n:
		parts.append(_under_thousand(n))
	return " ".join(p for p in parts if p.strip())


INDIAN_GROUPS = ((10_000_000, "Crore"), (100_000, "Lakh"), (1_000, "Thousand"))
INTERNATIONAL_GROUPS = ((1_000_000_000_000, "Trillion"), (1_000_000_000, "Billion"),
                        (1_000_000, "Million"), (1_000, "Thousand"))


def number_in_words(n: int, indian: bool = True) -> str:
	"""A whole number spelled out. 0 is a word too - a nil invoice still
	has to print something."""
	n = int(n)
	if n == 0:
		return "Zero"
	if n < 0:
		return "Minus " + number_in_words(-n, indian)
	return _grouped(n, INDIAN_GROUPS if indian else INTERNATIONAL_GROUPS).strip()


def amount_in_words(amount, currency: str = "INR", indian: bool = True) -> str:
	"""The full invoice line: "Rupees Three Thousand Five Hundred Only", or
	with paise when the amount isn't whole."""
	value = Decimal(str(amount or 0)).quantize(Decimal("0.01"),
	                                           rounding=ROUND_HALF_UP)
	negative = value < 0
	value = abs(value)
	whole = int(value)
	fraction = int((value - whole) * 100)

	main, sub = CURRENCY_WORDS.get(
		(currency or "").upper(), ((currency or "").upper(), None))
	words = f"{main} {number_in_words(whole, indian)}".strip()
	if fraction and sub:
		words += f" and {number_in_words(fraction, indian)} {sub}"
	elif fraction:
		words += f" point {fraction:02d}"
	if negative:
		words = "Minus " + words
	return f"{words} Only"
