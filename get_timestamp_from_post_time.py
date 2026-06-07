import arrow
from datetime import datetime, UTC, timedelta

def get_timestamp_from_post_time(time_raw):
    time_clean = time_raw.replace('hour ', 'hours ')
    time_clean = time_clean.replace('day ', 'days ')
    time_clean = time_clean.replace('minute ', 'minutes ')
    time_clean = time_clean.replace('week ', 'weeks ')
    time_clean = time_clean.replace('month ', 'months ')
    time_clean = time_clean.replace('second ', 'seconds ')
    time_clean = time_clean.replace('year ', 'years ')
    time_clean = time_clean.replace('(edited)', '')
    time_clean = time_clean.strip()

    timestamp_handler = arrow.utcnow()

    try:
        time_fixed = timestamp_handler.dehumanize(time_clean)
    except ValueError as e:
        print(f'Failed to humanize timestamp: {time_raw}, {time_clean}')
        print(e)

        #set an arbitrary time in the past to not cause issues
        time_fixed = arrow.get(datetime.now(UTC) + timedelta(days=-100))

    return time_fixed.format()