# -*- coding: utf-8 -*-
from loguru import logger
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from concurrent.futures import ThreadPoolExecutor
from lxml import html
import platform
import argparse
import webbrowser
import requests
import re
import unittest
import json
import time
import traceback

SUCCESS_CODE = 0
EXIT_CODE = 1


class Accom_bot:
    def __init__(self, open_results = False) -> None:
        config = self.validate_config(self.read_config())
        self.requirements = config["requirements"]
        self.websites = config["websites"]
        self.open_results = open_results

    def read_config(self, filename="config.json") -> dict:
        data = []
        try:
            with open(filename, "r") as f:
                data = json.load(f)
        except:
            logger.error(f"config (filename: {filename}) not found.")
        finally:
            if data:
                return data
            else:
                raise ValueError(f"No config found.")

    def init_driver(self) -> webdriver:
        if platform.system() == "Darwin": driver =  webdriver.Safari()
        elif platform.system() == "Linux": driver = webdriver.Firefox()
        else: driver = webdriver.Edge()
        return driver

    def validate_config(self, config: dict) -> dict:
        requirements = config["requirements"]
        min_beds = requirements.get("beds_min", None)
        max_beds = requirements.get("beds_max", None)
        location = requirements.get("location", None)
        bathrooms = requirements.get("bathrooms", None)
        errors = []
        if not min_beds:
            errors.append("key-value pair 'beds_min' not found.")
        if not max_beds:
            errors.append("key-value pair 'beds_max' not found.")
        if not location:
            errors.append("key-value pair 'location' not found.")
        if not bathrooms:
            errors.append("key-value pair 'bathrooms' not found.")
        try:
            int(bathrooms)
        except:
            errors.append(
                f"value for key 'bathrooms' is not an integer (value: {bathrooms})"
            )
        try:
            if (min_beds and max_beds) and (int(min_beds) > int(max_beds)):
                errors.append("minimum number of beds exceed maximum number of beds")
        except Exception:
            try:
                int(min_beds)
            except:
                errors.append(
                    f"value for key 'beds_min' is not an integer (value: {min_beds})"
                )
            try:
                int(max_beds)
            except:
                errors.append(
                    f"value for key 'beds_max' is not an integer (value: {max_beds})"
                )
        finally:
            if errors:
                errors = "\n".join(errors)
                errors = f"The following errors are found while loading config.json:\n{errors}"
                raise ValueError(errors)
            else:
                return config

    def request_thread_function(self, url: str) -> str:
        page = requests.get(url)
        return html.fromstring(page.content)

    def check_bathroom_requirements(self, website: dict, places: list) -> list:
        logger.info("Checking bathroom requirements...")
        final_places = []
        with ThreadPoolExecutor(max_workers=70) as e:
            results = list(e.map(self.request_thread_function, places))
        number_of_bathrooms = self.requirements["bathrooms"]
        search_elements = website["check_property"]
        for index, place in enumerate(places):
            url_element = results[index]
            bathrooms = url_element.xpath(search_elements["xpath"])
            if (
                bathrooms
                and bathrooms[0][search_elements["index"]] >= number_of_bathrooms
            ):
                final_places.append(place)
        return final_places

    def process_action(self, driver: webdriver, key: str, action: str) -> None:
        if action == "xpath":
            driver.find_element_by_xpath(key).click()
        if action == "click_id":
            driver.find_element_by_id(key).click()
        if action == "location":
            driver.find_element_by_id(key).send_keys(self.requirements[action])
            driver.find_element_by_id(key).send_keys(Keys.TAB)
        if action in ["beds_min", "beds_max"]:
            select = Select(driver.find_element_by_xpath(key))
            select.select_by_value(self.requirements[action])
        if action == "link_text":
            driver.find_element_by_link_text(key).click()
        if action == "css":
            driver.find_element_by_css_selector(key).click()

    def handle_pagination(
        self, driver: webdriver, key: str, action: str, regex: str, max_page: str
    ) -> list:
        pages = []
        links = []
        if action == "get_xpath_list":
            html_list = driver.find_element_by_xpath(key)
            items = html_list.find_elements_by_tag_name("li")
            for item in items:
                a_tags = item.find_elements_by_tag_name("a")
                for a_tag in a_tags:
                    pages.append(a_tag.get_attribute("href"))
            pages = sorted(list(set([page for page in pages if page is not None])))
            for index, page in enumerate(pages):
                logger.info(f"Getting {index+1}/{len(pages)}: {page}")
                driver.get(page)
                urls = self.extract_urls(driver, regex)
                for url in urls:
                    links.append(url)
        elif action == "select":
            i = 1
            max_page = int(driver.find_element_by_xpath(max_page).text)
            logger.debug(max_page)
            while True:
                logger.info(f"Getting page {i}/{max_page}")
                ActionChains(driver).send_keys(Keys.END).perform()
                urls = self.extract_urls(driver, regex)
                for url in urls:
                    links.append(url)
                driver.find_element_by_xpath(key).click()
                if i == max_page:
                    break
                i += 1
        link = list(set(links))
        link = [result for result in link if result is not None]
        return links

    def extract_urls(self, driver: webdriver, regex: str) -> list:
        urls = []
        elems = driver.find_elements_by_xpath("//a[@href]")
        for elem in elems:
            try:
                url = elem.get_attribute("href")
                if re.search(rf"{regex}", url):
                    urls.append(url)
            except:
                pass
        return urls

    def go_to_website(self, driver: webdriver, website: dict) -> None:
        url = website["url"]
        logger.info(f"Current website: {url}")
        driver.get(url)

    def fill_search_form(self, driver: webdriver, website: dict) -> None:
        for step in website["search"]:
            for key, action in step.items():
                try:
                    self.process_action(driver, key, action)
                except:
                    pass
            time.sleep(0.5)

    def get_links(self, driver: webdriver, website: dict, max_page=None) -> list:
        links = []
        for step in website["step"]:
            for key, action in step.items():
                if action == "match_url_regex":
                    page_instructions = website["pagination"]
                    for step in page_instructions:
                        for key1, action1 in step.items():
                            try:
                                links = sorted(
                                    self.handle_pagination(
                                        driver, key1, action1, key, max_page
                                    )
                                )
                            except Exception:
                                pass
        links = list(set(links))
        links = self.check_bathroom_requirements(website, links)
        logger.info(f"Found {len(links)} results from website {website['url']}")
        return links

    def print_places(self, all_places: list) -> None:
        all_places = sorted(all_places)
        places = "\n".join(all_places)
        logger.info(f"All {len(all_places)} places:\n{places}")

    def find_places(self, data: dict):
        driver = data["driver"]
        website = data["website"]
        driver.set_window_size(1920, 1080)
        self.go_to_website(driver, website)
        time.sleep(1)
        self.fill_search_form(driver, website)
        time.sleep(5)
        max_page = website.get("max_page", None)
        links = self.get_links(driver, website, max_page)
        return links

    def open_links(self, places: list):
        for place in places:
            webbrowser.open_new_tab(place)

    def main(self) -> int:
        driver = self.init_driver()
        try:
            all_places = []
            data = []
            for website in self.websites:
                data = {"driver": driver, "website": website}
                results = self.find_places(data)
                for x in results:
                    all_places.append(x)
            driver.quit()
            all_places = sorted(all_places)
            self.print_places(all_places)
            if self.open_results:
                self.open_links(all_places)
            return SUCCESS_CODE
        except:
            driver.quit()
            logger.error(traceback.format_exc())
            return EXIT_CODE

class Run:
    
    def __init__(self) -> None:
        pass

    def read_args(self) -> argparse.Namespace:
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--open-results", action="store_true")
        argv = parser.parse_args()
        return argv

    def run_bot(self):
        argv = self.read_args()
        bot = Accom_bot(argv.open_results)
        bot.main()


class Tests(unittest.TestCase):
    def setUp(self) -> None:
        return super().setUp()

    def tearDown(self) -> None:
        return super().tearDown()

if __name__ == "__main__":
    run = Run()
    run.run_bot()