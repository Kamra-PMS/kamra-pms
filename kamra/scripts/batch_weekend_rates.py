from kamra.api import set_room_rate

def batch_set_rates(property, room_type, start_date, end_date, weekday_rate, weekend_rate, reason="Batch rate setup"):
	"""Helper function to set weekday and weekend rates for a date range in one operation."""
	# 1. Set Weekday Rate (Mon-Fri)
	weekday_res = set_room_rate(
		property=property,
		room_type=room_type,
		start_date=start_date,
		end_date=end_date,
		rate=weekday_rate,
		reason=reason,
		days_of_week="weekday"
	)
	
	# 2. Set Weekend Rate (Sat-Sun)
	weekend_res = set_room_rate(
		property=property,
		room_type=room_type,
		start_date=start_date,
		end_date=end_date,
		rate=weekend_rate,
		reason=reason,
		days_of_week="weekend"
	)
	
	return {
		"weekday": weekday_res,
		"weekend": weekend_res
	}
