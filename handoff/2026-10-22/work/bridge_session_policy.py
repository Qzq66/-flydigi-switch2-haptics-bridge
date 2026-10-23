"""Explicit host limits; baseline remains 60s, extended candidate is opt-in."""
def session_limits(live_seconds):
    if type(live_seconds) is not int or live_seconds not in (60,120):raise ValueError('Only verified-baseline 60 or candidate 120 seconds supported')
    return dict(live_seconds=live_seconds,host_live_seconds=live_seconds+2,
        arm_latest_seconds=live_seconds-5,ui_deadline_seconds=live_seconds-2,
        discovery_seconds=120,guardian_seconds=200 if live_seconds==60 else 270,
        expected_firmware='v042' if live_seconds==60 else 'v043',
        firmware_boot_seconds=120 if live_seconds==60 else 180)
