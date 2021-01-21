# -*- coding: utf-8 -*-
from loguru import logger
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import platform
import re
import unittest
import json
import time
import traceback

SUCCESS_CODE = 0
EXIT_CODE = 1


class Accom_bot:
    def __init__(self) -> None:
        self.driver = None
        config = self.validate_config(self.read_config())
        self.requirements = config["requirements"]
        self.websites = config["websites"]

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
        if platform.system() == "Darwin":
            driver = webdriver.Safari()
        elif platform.system() == "Windows":
            driver = webdriver.Edge()
        else:
            driver = webdriver.Firefox()
        return driver

    def validate_config(self, config: dict):
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

    def process_action(self, key: str, action: str) -> None:
        if action == "xpath":
            self.driver.find_element_by_xpath(key).click()
        if action == "click_id":
            self.driver.find_element_by_id(key).click()
        if action == "location":
            self.driver.find_element_by_id(key).send_keys(self.requirements[action])
            self.driver.find_element_by_id(key).send_keys(Keys.TAB)
        if action in ["beds_min", "beds_max"]:
            select = Select(self.driver.find_element_by_xpath(key))
            select.select_by_value(self.requirements[action])
        if action == "link_text":
            self.driver.find_element_by_link_text(key).click()
        if action == "css":
            self.driver.find_element_by_css_selector(key).click()

    def handle_pagination(
        self, key: str, action: str, regex: str, max_page: str
    ) -> list:
        pages = []
        links = []
        if action == "get_xpath_list":
            html_list = self.driver.find_element_by_xpath(key)
            items = html_list.find_elements_by_tag_name("li")
            for item in items:
                a_tags = item.find_elements_by_tag_name("a")
                for a_tag in a_tags:
                    pages.append(a_tag.get_attribute("href"))
            pages = sorted(list(set([page for page in pages if page is not None])))
            for index, page in enumerate(pages):
                logger.info(f"Getting {index+1}/{len(pages)}: {page}")
                self.driver.get(page)
                urls = self.extract_urls(regex)
                for url in urls:
                    links.append(url)
        elif action == "select":
            i = 1
            max_page = int(self.driver.find_element_by_xpath(max_page).text)
            logger.debug(max_page)
            while True:
                logger.info(f"Getting page {i}")
                ActionChains(self.driver).send_keys(Keys.END).perform()
                urls = self.extract_urls(regex)
                for url in urls:
                    links.append(url)
                self.driver.find_element_by_xpath(key).click()
                if i == max_page:
                    break
                i += 1
        link = list(set(links))
        link = [result for result in link if result is not None]
        return links

    def extract_urls(self, regex: str) -> list:
        urls = []
        elems = self.driver.find_elements_by_xpath("//a[@href]")
        for elem in elems:
            try:
                url = elem.get_attribute("href")
                if re.search(rf"{regex}", url):
                    urls.append(url)
            except:
                pass
        return urls

    def go_to_website(self, website: dict) -> None:
        url = website["url"]
        logger.info(f"Current website: {url}")
        self.driver.get(url)

    def fill_search_form(self, website: dict) -> None:
        for index, step in enumerate(website["search"], 1):
            for key, action in step.items():
                try:
                    logger.debug(f"Search action {index} - {key}, {action}")
                    self.process_action(key, action)
                except:
                    pass
            time.sleep(0.5)

    def get_links(self, website: dict, max_page=None) -> list:
        links = []
        for index, step in enumerate(website["step"], 1):
            for key, action in step.items():
                logger.debug(f"Extract action {index} - {key}, {action}")
                if action == "match_url_regex":
                    page_instructions = website["pagination"]
                    for step in page_instructions:
                        for key1, action1 in step.items():
                            links = sorted(
                                self.handle_pagination(key1, action1, key, max_page)
                            )
        links = list(set(links))
        logger.info(f"Found {len(links)} results from website {website['url']}")
        return links

    def print_places(self, all_places: list) -> None:
        all_places = sorted(all_places)
        places = "\n".join(all_places)
        logger.info(f"All places:\n{places}")

    def main(self) -> int:
        try:
            all_places = []
            self.driver = self.init_driver()
            self.driver.set_window_size(1920, 1080)
            for website in self.websites:
                self.go_to_website(website)
                time.sleep(1)
                self.fill_search_form(website)
                time.sleep(5)
                max_page = website.get("max_page", None)
                links = self.get_links(website, max_page)
                all_places = all_places + links
            self.driver.quit()
            self.print_places(all_places)
            return SUCCESS_CODE
        except:
            self.driver.quit()
            logger.error(traceback.format_exc())
            return EXIT_CODE


class Tests(unittest.TestCase):
    def setUp(self) -> None:
        return super().setUp()

    def tearDown(self) -> None:
        return super().tearDown()


if __name__ == "__main__":
    accom_bot = Accom_bot()
    accom_bot.main()
