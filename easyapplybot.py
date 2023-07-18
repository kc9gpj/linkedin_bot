from __future__ import annotations
import time
import random
import os
import csv
import platform
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import pyautogui

from urllib.request import urlopen
from webdriver_manager.chrome import ChromeDriverManager
import re
import yaml
from datetime import datetime, timedelta

log = logging.getLogger(__name__)
driver = webdriver.Chrome("/usr/lib/chromium-browser/chromedriver")


def setupLogger() -> None:
    dt: str = datetime.strftime(datetime.now(), "%m_%d_%y %H_%M_%S ")

    if not os.path.isdir('./logs'):
        os.mkdir('./logs')

    logging.basicConfig(filename=('./logs/' + str(dt) + 'applyJobs.log'), filemode='w',
                        format='%(asctime)s::%(name)s::%(levelname)s::%(message)s', datefmt='./logs/%d-%b-%y %H:%M:%S')
    log.setLevel(logging.DEBUG)
    c_handler = logging.StreamHandler()
    c_handler.setLevel(logging.DEBUG)
    c_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s', '%H:%M:%S')
    c_handler.setFormatter(c_format)
    log.addHandler(c_handler)


class EasyApplyBot:
    setupLogger()
    # MAX_SEARCH_TIME is 10 hours by default, feel free to modify it
    # MAX_SEARCH_TIME = 10 * 60 * 60
    MAX_SEARCH_TIME = 1 * 60 * 60

    def __init__(self,
                 username,
                 password,
                 phone_number,
                 uploads={},
                 filename='output.csv',
                 blacklist=[],
                 blackListTitles=[]) -> None:

        log.info("Welcome to Easy Apply Bot")
        dirpath: str = os.getcwd()
        log.info("current directory is : " + dirpath)

        self.uploads = uploads
        past_ids: list | None = self.get_appliedIDs(filename)
        self.appliedJobIDs: list = past_ids if past_ids != None else []
        self.filename: str = filename
        self.options = self.browser_options()
        self.browser = driver
        self.wait = WebDriverWait(self.browser, 30)
        self.blacklist = blacklist
        self.blackListTitles = blackListTitles
        self.start_linkedin(username, password)
        self.phone_number = phone_number

    def get_appliedIDs(self, filename) -> list | None:
        try:
            df = pd.read_csv(filename,
                             header=None,
                             names=['timestamp', 'jobID', 'job',
                                    'company', 'attempted', 'result'],
                             lineterminator='\n',
                             encoding='utf-8')

            df['timestamp'] = pd.to_datetime(
                df['timestamp'], format="%Y-%m-%d %H:%M:%S")
            df = df[df['timestamp'] > (datetime.now() - timedelta(days=2))]
            jobIDs: list = list(df.jobID)
            log.info(f"{len(jobIDs)} jobIDs found")
            return jobIDs
        except Exception as e:
            log.info(
                str(e) + "   jobIDs could not be loaded from CSV {}".format(filename))
            return None

    def browser_options(self):
        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument('--no-sandbox')
        options.add_argument("--disable-extensions")

        # Disable webdriver flags or you will be easily detectable
        options.add_argument("--disable-blink-features")
        options.add_argument("--disable-blink-features=AutomationControlled")
        return options

    def start_linkedin(self, username, password) -> None:
        log.info("Logging in.....Please wait :)  ")
        self.browser.get(
            "https://www.linkedin.com/login?trk=guest_homepage-basic_nav-header-signin")
        try:
            user_field = self.browser.find_element("id", "username")
            pw_field = self.browser.find_element("id", "password")
            login_button = self.browser.find_element("xpath",
                                                     '//*[@id="organic-div"]/form/div[3]/button')
            user_field.send_keys(username)
            user_field.send_keys(Keys.TAB)
            time.sleep(2)
            pw_field.send_keys(password)
            time.sleep(2)
            login_button.click()
            # sleep a minute in case of captcha
            time.sleep(60)
        except TimeoutException:
            log.info(
                "TimeoutException! Username/password field or login button not found")

    def fill_data(self) -> None:
        self.browser.set_window_size(1, 1)
        self.browser.set_window_position(2000, 2000)

    def start_apply(self, positions, locations) -> None:
        start: float = time.time()
        self.fill_data()

        combos: list = []
        while len(combos) < len(positions) * len(locations):
            position = positions[random.randint(0, len(positions) - 1)]
            location = locations[random.randint(0, len(locations) - 1)]
            combo: tuple = (position, location)
            if combo not in combos:
                combos.append(combo)
                log.info(f"Applying to {position}: {location}")
                location = "&location=" + location
                self.applications_loop(position, location)
            if len(combos) > 500:
                break

    def applications_loop(self, position, location):

        count_application = 0
        count_job = 0
        jobs_per_page = 0
        start_time: float = time.time()

        log.info("Looking for jobs.. Please wait..")

        self.browser.set_window_position(1, 1)
        self.browser.maximize_window()
        self.browser, _ = self.next_jobs_page(
            position, location, jobs_per_page)
        log.info("Looking for jobs.. Please wait..")

        while time.time() - start_time < self.MAX_SEARCH_TIME:
            try:
                log.info(
                    f"{(self.MAX_SEARCH_TIME - (time.time() - start_time)) // 60} minutes left in this search")
                randoTime: float = random.uniform(3.5, 4.9)
                log.debug(f"Sleeping for {round(randoTime, 1)}")
                time.sleep(randoTime)
                self.load_page(sleep=1)

                time.sleep(1)

                links = self.browser.find_elements("xpath",
                                                   '//div[@data-job-id]'
                                                   )

                if len(links) == 0:
                    log.debug("No links found")
                    break

                IDs: list = []

                for link in links:
                    children = link.find_elements("xpath",
                                                  '//ul[@class="scaffold-layout__list-container"]'
                                                  )
                    for child in children:
                        if child.text not in self.blacklist:
                            temp = link.get_attribute("data-job-id")
                            jobID = temp.split(":")[-1]
                            log.info(jobID)
                            IDs.append(int(jobID))
                        else:
                            print('skipping ' + child.text)
                IDs: list = set(IDs)
                log.debug(IDs)
                before: int = len(IDs)
                jobIDs: list = [x for x in IDs if x not in self.appliedJobIDs]
                after: int = len(jobIDs)
                log.debug(before)
                log.debug(after)
                if len(jobIDs) == 0 and len(IDs) > 23:
                    jobs_per_page = jobs_per_page + 25
                    count_job = 0
                    self.avoid_lock()
                    self.browser, jobs_per_page = self.next_jobs_page(position,
                                                                      location,
                                                                      jobs_per_page)
                for i, jobID in enumerate(jobIDs):
                    count_job += 1
                    self.get_job_page(jobID)

                    button = self.get_easy_apply_button()

                    if button is not False:
                        log.debug(self.browser.title)
                        log.debug(self)
                        log.debug(self.browser)
                        log.debug(blackListTitles)
                        log.debug(any(word in self.browser.title.lower()
                                  for word in blackListTitles))
                        if any(word in self.browser.title.lower() for word in blackListTitles):
                            log.info(
                                'skipping this application, a blacklisted keyword was found in the job position')
                            string_easy = "* Contains blacklisted keyword"
                            result = False
                        elif any(word in self.browser.title.lower() for word in blacklist):
                            log.info(
                                'skipping this application, a blacklisted company was found in the job position')
                            string_easy = "* Contains blacklisted copmany"
                            result = False
                        else:
                            string_easy = "* has Easy Apply Button"
                            log.info("Clicking the EASY apply button")
                            button.click()
                            time.sleep(3)
                            # self.fill_out_phone_number()
                            result: bool = self.send_resume()
                            count_application += 1
                    else:
                        log.info("The button does not exist.")
                        string_easy = "* Doesn't have Easy Apply Button"
                        result = False

                    position_number: str = str(count_job + jobs_per_page)
                    log.info(
                        f"\nPosition {position_number}:\n {self.browser.title} \n {string_easy} \n")

                    self.write_to_file(
                        button, jobID, self.browser.title, result)

                    if count_application != 0 and count_application % 20 == 0:
                        sleepTime: int = random.randint(500, 900)
                        log.info(f"""********count_application: {count_application}************\n\n
                                    Time for a nap - see you in:{int(sleepTime / 60)} min
                                ****************************************\n\n""")
                        time.sleep(sleepTime)

                    if count_job == len(jobIDs):
                        jobs_per_page = jobs_per_page + 25
                        count_job = 0
                        log.info("""****************************************\n\n
                        Going to next jobs page, YEAAAHHH!!
                        ****************************************\n\n""")
                        self.avoid_lock()
                        self.browser, jobs_per_page = self.next_jobs_page(position,
                                                                          location,
                                                                          jobs_per_page)
            except Exception as e:
                print(e)

    def write_to_file(self, button, jobID, browserTitle, result) -> None:
        def re_extract(text, pattern):
            target = re.search(pattern, text)
            if target:
                target = target.group(1)
            return target

        timestamp: str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        attempted: bool = False if button == False else True
        job = re_extract(browserTitle.split(' | ')[0], r"\(?\d?\)?\s?(\w.*)")
        company = re_extract(browserTitle.split(' | ')[1], r"(\w.*)")

        toWrite: list = [timestamp, jobID, job, company, attempted, result]
        with open(self.filename, 'a') as f:
            writer = csv.writer(f)
            writer.writerow(toWrite)

    def get_job_page(self, jobID):

        job: str = 'https://www.linkedin.com/jobs/view/' + str(jobID)
        self.browser.get(job)
        self.job_page = self.load_page(sleep=0.5)
        return self.job_page

    def get_easy_apply_button(self):
        try:
            button = self.browser.find_elements("xpath",
                                                '//button[contains(@class, "jobs-apply-button")]'
                                                )

            EasyApplyButton = button[0]

        except Exception as e:
            print("Exception:", e)
            EasyApplyButton = False

        return EasyApplyButton

    def fill_out_phone_number(self):
        def is_present(button_locator) -> bool:
            return len(self.browser.find_elements(button_locator[0],
                                                  button_locator[1])) > 0
        # try:
        next_locater = (By.CSS_SELECTOR,
                        "button[aria-label='Continue to next step']")

        input_field = self.browser.find_element(
            By.CSS_SELECTOR, "input.artdeco-text-input--input[type='text']")

        if input_field:
            input_field.clear()
            input_field.send_keys(self.phone_number)
            time.sleep(random.uniform(4.5, 6.5))

            next_locater = (By.CSS_SELECTOR,
                            "button[aria-label='Continue to next step']")
            error_locator = (By.CSS_SELECTOR,
                             "p[data-test-form-element-error-message='true']")

            button: None = None
            if is_present(next_locater):
                button: None = self.wait.until(
                    EC.element_to_be_clickable(next_locater))

            if is_present(error_locator):
                for element in self.browser.find_elements(error_locator[0],
                                                          error_locator[1]):
                    text = element.text
                    if "Please enter a valid answer" in text:
                        button = None
                        break
            if button:
                button.click()
                time.sleep(random.uniform(1.5, 2.5))

        else:
            log.debug(f"Could not find phone number field")

    def send_resume(self) -> bool:
        def is_present(button_locator) -> bool:
            return len(self.browser.find_elements(button_locator[0],
                                                  button_locator[1])) > 0

        try:
            time.sleep(random.uniform(1.5, 2.5))
            next_locater = (By.CSS_SELECTOR,
                            "button[aria-label='Continue to next step']")
            review_locater = (By.CSS_SELECTOR,
                              "button[aria-label='Review your application']")
            submit_locater = (By.CSS_SELECTOR,
                              "button[aria-label='Submit application']")
            submit_application_locator = (By.CSS_SELECTOR,
                                          "button[aria-label='Submit application']")
            error_locator = (By.CSS_SELECTOR,
                             "p[data-test-form-element-error-message='true']")
            upload_locator = upload_locator = (
                By.CSS_SELECTOR, "button[aria-label='DOC, DOCX, PDF formats only (5 MB).']")
            follow_locator = (
                By.CSS_SELECTOR, "label[for='follow-company-checkbox']")

            submitted = False
            timeout = time.time() + 60*1
            while True:
                test = 0
                if test == 5 or time.time() > timeout:
                    log.info('skipping took too long')
                    break
                test = test - 1
                # Upload Cover Letter if possible
                if is_present(upload_locator):

                    input_buttons = self.browser.find_elements(upload_locator[0],
                                                               upload_locator[1])
                    for input_button in input_buttons:
                        parent = input_button.find_element(By.XPATH, "..")
                        sibling = parent.find_element(
                            By.XPATH, "preceding-sibling::*[1]")
                        grandparent = sibling.find_element(By.XPATH, "..")
                        for key in self.uploads.keys():
                            sibling_text = sibling.text
                            gparent_text = grandparent.text
                            if key.lower() in sibling_text.lower() or key in gparent_text.lower():
                                input_button.send_keys(self.uploads[key])

                    time.sleep(random.uniform(4.5, 6.5))

                button: None = None
                buttons: list = [next_locater, review_locater, follow_locator,
                                 submit_locater, submit_application_locator]
                for i, button_locator in enumerate(buttons):
                    if is_present(button_locator):
                        button: None = self.wait.until(
                            EC.element_to_be_clickable(button_locator))

                    if is_present(error_locator):
                        for element in self.browser.find_elements(error_locator[0],
                                                                  error_locator[1]):
                            text = element.text
                            if "Please enter a valid answer" in text:
                                button = None
                                break
                    if button:
                        button.click()
                        time.sleep(random.uniform(1.5, 2.5))
                        if i in (3, 4):
                            submitted = True
                        if i != 2:
                            break
                if button == None:
                    log.info("Could not complete submission")
                    break
                elif submitted:
                    log.info("Application Submitted")
                    break

            time.sleep(random.uniform(1.5, 2.5))

        except Exception as e:
            log.info(e)
            log.info("cannot apply to this job")
            raise (e)

        return submitted

    def load_page(self, sleep=1):
        scroll_page = 0
        while scroll_page < 4000:
            self.browser.execute_script(
                "window.scrollTo(0," + str(scroll_page) + " );")
            scroll_page += 200
            time.sleep(sleep)

        if sleep != 1:
            self.browser.execute_script("window.scrollTo(0,0);")
            time.sleep(sleep * 3)
        page = BeautifulSoup(self.browser.page_source, "html5lib")
        # page = BeautifulSoup(self.browser.page_source, "lxml")
        return page

    def avoid_lock(self) -> None:
        x, _ = pyautogui.position()
        pyautogui.moveTo(x + 200, pyautogui.position().y, duration=1.0)
        pyautogui.moveTo(x, pyautogui.position().y, duration=0.5)
        pyautogui.keyDown('ctrl')
        pyautogui.press('esc')
        pyautogui.keyUp('ctrl')
        time.sleep(0.5)
        pyautogui.press('esc')

    def next_jobs_page(self, position, location, jobs_per_page):
        self.browser.get(
            # one week
            # "https://www.linkedin.com/jobs/search/?f_LF=f_AL&f_TPR=r604800&sortBy=DD&keywords=" +
            # 24 hours
            "https://www.linkedin.com/jobs/search/?f_LF=f_AL&f_TPR=r86400&sortBy=DD&keywords=" +
            position + location + "&start=" + str(jobs_per_page))
        self.avoid_lock()
        log.info("Lock avoided.")
        self.load_page()
        return (self.browser, jobs_per_page)

    def finish_apply(self) -> None:
        self.browser.close()


if __name__ == '__main__':

    with open("config.yaml", 'r') as stream:
        try:
            parameters = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            raise exc

    assert len(parameters['positions']) > 0
    assert len(parameters['locations']) > 0
    assert parameters['username'] is not None
    assert parameters['password'] is not None
    assert parameters['phone_number'] is not None

    if 'uploads' in parameters.keys() and type(parameters['uploads']) == list:
        raise Exception("uploads read from the config file appear to be in list format" +
                        " while should be dict. Try removing '-' from line containing" +
                        " filename & path")

    log.info({k: parameters[k] for k in parameters.keys()
             if k not in ['username', 'password']})

    output_filename: list = [f for f in parameters.get(
        'output_filename', ['output.csv']) if f != None]
    output_filename: list = output_filename[0] if len(
        output_filename) > 0 else 'output.csv'
    blacklist = parameters.get('blacklist', [])
    blackListTitles = parameters.get('blackListTitles', [])

    uploads = {} if parameters.get(
        'uploads', {}) == None else parameters.get('uploads', {})
    for key in uploads.keys():
        assert uploads[key] != None

    bot = EasyApplyBot(parameters['username'],
                       parameters['password'],
                       parameters['phone_number'],
                       uploads=uploads,
                       filename=output_filename,
                       blacklist=blacklist,
                       blackListTitles=blackListTitles
                       )

    locations: list = [l for l in parameters['locations'] if l != None]
    positions: list = [p for p in parameters['positions'] if p != None]
    bot.start_apply(positions, locations)
