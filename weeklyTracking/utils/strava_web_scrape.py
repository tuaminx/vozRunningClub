import datetime
import logging
import os
from typing import List, Dict

from bs4 import BeautifulSoup
from django.contrib.auth.models import User
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait
from social_django.models import UserSocialAuth

from weeklyTracking.models import SettingStravaClub, WeeklyProgress, SettingRegisteredMileage
from weeklyTracking.utils.donation import update_donation
from weeklyTracking.utils.time import get_last_week_year_and_week_num

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_elevation_gain(text):
    if text == "--":
        return 0.0
    else:
        return float(text.split()[0].replace(",", ""))


def get_average_pace_in_seconds(minute_second):
    if minute_second == "--":
        return 0.0
    else:
        minute, second = minute_second.split(":")
        return 60 * float(minute) + float(second)


def get_strava_leaderboards():
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")

    if "GOOGLE_CHROME_BIN" in os.environ:  # Heroku
        chrome_options.binary_location = os.environ["GOOGLE_CHROME_BIN"]
        driver = webdriver.Chrome(executable_path=os.environ["CHROMEDRIVER_PATH"], chrome_options=chrome_options)
    else:
        driver = webdriver.Chrome(chrome_options=chrome_options)

    # get URL of Strava club
    club_url = SettingStravaClub.objects.get().club_url

    # navigate to Strava group page
    driver.get(club_url)

    # get "This Week's Leaderboard"
    try:
        WebDriverWait(driver, 10).until(expected_conditions.presence_of_element_located(
            (By.CSS_SELECTOR, "div.leaderboard > table > tbody")))
    except TimeoutException:
        logger.info("Request Timed Out")

    # get this week's leaderboard
    ic = datetime.date.today().isocalendar()
    this_year, this_week_num = ic[0], ic[1]

    this_week_runners = get_data_from_driver(driver, year=this_year, week_num=this_week_num)

    # get last week's leaderboard
    last_week_btn = driver.find_element(By.CSS_SELECTOR, "span.button.last-week")
    last_week_btn.click()

    last_week_year, last_week_num = get_last_week_year_and_week_num()

    last_week_runners = get_data_from_driver(driver, year=last_week_year, week_num=last_week_num)

    driver.close()

    return this_week_runners, last_week_runners


def get_data_from_driver(driver, year, week_num):
    table = driver.find_element(By.CSS_SELECTOR, "div.leaderboard > table > tbody").get_attribute("innerHTML")
    soup = BeautifulSoup(table, "html.parser")

    # Example table row:
    #
    # <tr>
    # <td class="rank">1</td>
    # <td class="athlete">
    # <div class="avatar avatar-athlete avatar-sm">
    # <a class="avatar-content" href="/athletes/48089747">
    # <div class="avatar-img-wrapper avatar-default">
    #
    # <img alt="Minh Đức L." src="/assets/avatar/athlete/medium.png" title="Minh Đức L.">
    # </div>
    # </a>
    # </div>
    # <a class="athlete-name minimal" href="/athletes/48089747">
    # Minh Đức L.
    # </a>
    # </td>
    # <td class="distance highlighted-column">40.6 <abbr class="unit short" title="kilometers">km</abbr></td>
    # <td class="num-activities">2</td>
    # <td class="longest-activity">
    # 20.3 <abbr class="unit short" title="kilometers">km</abbr>
    # </td>
    # <td class="average-pace">5:35 <abbr class="unit short" title="minutes per kilometer">/km</abbr></td>
    # <td class="elev-gain">--</td>
    # </tr>

    runners = []
    for row in soup.find_all("tr"):
        runner = {
            "id": int(row.find("td", class_="athlete").find("a")["href"].split("/")[-1]),
            "name": row.find("a", class_="athlete-name").text.strip(),
            "distance": float(row.find("td", class_="distance").text.split()[0]),
            "runs": int(row.find("td", class_="num-activities").text),
            "longest_run": float(row.find("td", class_="longest-activity").text.split()[0]),
            "average_pace": get_average_pace_in_seconds(
                row.find("td", class_="average-pace").text.split("/")[0].strip()),
            "elevation_gain": get_elevation_gain(row.find("td", class_="elev-gain").text.strip()),
            "year": year,
            "week_num": week_num
        }

        runners.append(runner)

    return runners


def update_week_progress(strava_runners: List[Dict], remove_non_strava_runners: bool = False):
    if not strava_runners:
        return

    if len(set([runner["year"] for runner in strava_runners])) != 1:
        raise ValueError("All runners must be from the same year")

    if len(set([runner["week_num"] for runner in strava_runners])) != 1:
        raise ValueError("All runners must be from the same week")

    year = strava_runners[0]["year"]
    week_num = strava_runners[0]["week_num"]

    for runner in strava_runners:
        if not User.objects.filter(social_auth__provider="strava", social_auth__uid=runner["id"]).exists():
            # create user
            user = User.objects.create_user(username=f"strava_{runner['id']}")
            user.first_name = " ".join(runner["name"].split()[:-1])
            user.last_name = runner["name"].split()[-1]
            user.save()

            strava_social_auth = UserSocialAuth.objects.create(
                user=user,
                provider="strava",
                uid=runner["id"],
                extra_data="{}"
            )
            strava_social_auth.save()
        else:
            user = User.objects.get(social_auth__provider="strava", social_auth__uid=runner["id"])

        if WeeklyProgress.objects.filter(user=user, week_num=week_num, year=year).exists():
            obj = WeeklyProgress.objects.get(user=user, week_num=week_num, year=year)
            obj.distance = runner["distance"]
            obj.runs = runner["runs"]
            obj.longest_run = runner["longest_run"]
            obj.average_pace = runner["average_pace"]
            obj.elevation_gain = runner["elevation_gain"]
            obj.save()
        else:
            obj = WeeklyProgress.objects.create(
                user=user,
                week_num=week_num,
                year=year,
                registered_mileage=SettingRegisteredMileage.objects.get(distance=0),
                distance=runner["distance"],
                runs=runner["runs"],
                longest_run=runner["longest_run"],
                average_pace=runner["average_pace"],
                elevation_gain=runner["elevation_gain"]
            )

        update_donation(weekly_progress=obj)

    # Check if any runners have been removed from the real-time Strava leaderboard
    # If so, delete them from the database
    if not remove_non_strava_runners:
        return
    db_progress = WeeklyProgress.objects.filter(year=year, week_num=week_num)
    db_ids = set([obj.user.social_auth.uid for obj in db_progress if obj.user.social_auth.provider == "strava"])
    strava_ids = set([runner["id"] for runner in strava_runners])
    removed_ids = db_ids - strava_ids
    if removed_ids:
        print(f"Removing {len(removed_ids)} runners from the database: {removed_ids}")
        WeeklyProgress.objects.filter(user__social_auth__provider="strava", user__social_auth__uid=removed_ids,
                                      year=year, week_num=week_num).delete()


def handle_leaderboard_update_request():
    logger.info("Fetching Strava Leaderboards")
    this_week_runners, last_week_runners = get_strava_leaderboards()

    # check if the leaderboard has been updated for the new week
    # issues happen on sunday night (time zone issues?)
    # compare strava this week vs db last week
    last_week_year, last_week_num = get_last_week_year_and_week_num()
    db_this_week_progress = WeeklyProgress.objects.filter(
        year=last_week_year, week_num=last_week_num).order_by("-distance").all()
    db_total_runs = sum([obj.runs for obj in db_this_week_progress])
    db_total_runners = len(db_this_week_progress)

    strava_total_runs = sum([runner["runs"] for runner in this_week_runners])
    strava_total_runners = len(this_week_runners)

    if db_total_runners == strava_total_runners and db_total_runs == strava_total_runs:
        logger.info("Leaderboard has not been updated for the new week")
        return

    logger.info("Updating Week Progress Table")
    update_week_progress(this_week_runners, remove_non_strava_runners=False)
    # update_week_progress(this_week_runners, remove_non_strava_runners=True)
    # update_week_progress(last_week_runners, remove_non_strava_runners=False)
    logger.info("Leaderboard update complete")
