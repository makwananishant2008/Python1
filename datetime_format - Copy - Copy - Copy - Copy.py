# Topic: Formatting date and time
from datetime import datetime
now = datetime.now()
print(now.strftime("%d-%m-%Y"))  # day-month-year
print(now.strftime("%H:%M:%S"))  # hour:min:sec
print(now.year, now.month, now.day)
