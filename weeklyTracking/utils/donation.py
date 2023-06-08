from weeklyTracking.models import WeeklyProgress, SettingWeekBaseDonation, SettingDefaultWeekBaseDonation


def get_or_create_week_base_donation(year: int, week_num: int, distance: int) -> SettingWeekBaseDonation:
    try:
        return SettingWeekBaseDonation.objects.get(year=year, week_num=week_num, distance=distance)
    except SettingWeekBaseDonation.DoesNotExist:
        default_setting = SettingDefaultWeekBaseDonation.objects.get(distance=distance)
        return SettingWeekBaseDonation.objects.create(year=year, week_num=week_num, distance=distance,
                                                      base_donation=default_setting.base_donation)


def update_donation(weekly_progress: WeeklyProgress):
    reg_dis = weekly_progress.registered_mileage.distance

    setting = get_or_create_week_base_donation(year=weekly_progress.year, week_num=weekly_progress.week_num,
                                               distance=reg_dis)
    donation_per_km = setting.base_donation

    if reg_dis > 0 and weekly_progress.distance == 0:
        donation = weekly_progress.registered_mileage.distance * donation_per_km
    else:
        donation = donation_per_km * (weekly_progress.registered_mileage.distance - weekly_progress.distance)

    donation = int(donation)
    if donation < 0:
        donation = 0
    if donation % 10 >= 5:
        donation = donation + 10 - (donation % 10)
    else:
        donation = donation - (donation % 10)

    weekly_progress.donation = donation
    weekly_progress.save()
