# -*- coding: utf-8 -*-
from loguru import logger
from lxml import html
from concurrent.futures import ThreadPoolExecutor
import pyppeteer
import asyncio
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

    async def init_browser(self) -> pyppeteer.browser.Browser:
        browser = await pyppeteer.launch(headless=False, slowMo = 5) #TODO REMOVE HEADLESS
        return browser
    
    async def new_browser_page(self, browser: pyppeteer.browser.Browser) -> pyppeteer.page.Page:
        page = await browser.newPage()
        await page.setViewport({
            "width": 960,
            "height": 1080
        })
        return page

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

    async def check_bathroom_requirements(self, website: dict, places: list) -> list: #TODO VERIFY
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

    async def process_action(self, page: pyppeteer.page.Page, key: str, action: str) -> None:
        logger.debug(f"key: {key}, action: {action}")
        time.sleep(0.5)
        try:
            if action == "click":
                await page.click(key)
            if action == "evaluate_click":
                evaluate = f"() => document.querySelector('{key}').click()"
                await page.evaluate(evaluate)
            if action == "location":
                await page.keyboard.type(self.requirements[action])
            if action in ["beds_min", "beds_max"]:
                await page.select(key, self.requirements[action])
            if action == "wait":
                task = asyncio.create_task(page.waitForNavigation({"waitUntil": "networkidle0"}))
                await asyncio.wait({task})
        except:
            logger.error(traceback.format_exc())
            
    async def handle_pagination(
        self, page: pyppeteer.page.Page, key: str, action: str, regex: str, max_page: str, domain: str
    ) -> list: #TODO DEBUG
        links = []
        if action == "get_pages":
            while True:
                try:    
                    evaluate = f"""() => Array.from(
                        document.querySelectorAll('a[href]'),
                        a => a.getAttribute('href')
                    )"""
                    logger.info('evaluated')
                    all_links = await page.evaluate(evaluate)
                    all_links = [f"{domain}{x}" for x in all_links]
                    matched_urls = await self.extract_urls(all_links, regex)
                    logger.debug(matched_urls)
                    for url in matched_urls:
                        links.append(url)
                    #TODO DEBUG
                    evaluate = f"""() => {{
                        var ul = document.querySelector('{key}');
                        var last_url = ul.children[ul.children.length-1].getAttribute('href');
                        return last_url
                    }}
                    """
                    next_url = await page.evaluate(evaluate)
                    logger.info(next_url)
                    break
                except:
                    logger.error(traceback.format_exc())
                    break
        elif action == "select":
            """
            i = 1
            max_page = int(page.xpath(max_page).text)
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
            """
        link = list(set(links))
        link = [result for result in link if result is not None]
        return links

    async def extract_urls(self, urls: list, regex: str) -> list: #TODO REPLACE
        matched_urls = []
        for url in urls:
            try:
                if re.search(rf"{regex}", url):
                    matched_urls.append(url)
            except:
                pass
        return matched_urls

    async def go_to_website(self, page: pyppeteer.page.Page, website: dict) -> None: #TODO VERIFY
        url = website["url"]
        logger.info(f"Current website: {url}")
        await page.goto(url)
        time.sleep(1)

    async def fill_search_form(self, page: pyppeteer.page.Page, website: dict) -> None: #TODO REPLACE
        for step in website["search"]:
            for key, action in step.items():
                try:
                     await self.process_action(page, key, action)
                except:
                    pass
            time.sleep(0.5)

    async def get_links(self, page: pyppeteer.page.Page, website: dict, max_page=None) -> list: #TODO VERIFY
        links = []
        for step in website["step"]:
            for key, action in step.items():
                if action == "match_url_regex":
                    page_instructions = website["pagination"]
                    for step in page_instructions:
                        for key1, action1 in step.items():
                            links = sorted(
                                await self.handle_pagination(
                                    page, key1, action1, key, max_page, website["domain"]
                                )
                            )
        links = list(set(links))
        links = await self.check_bathroom_requirements(website, links)
        logger.info(f"Found {len(links)} results from website {website['url']}")
        return links

    def print_places(self, all_places: list) -> None:
        all_places = sorted(all_places)
        places = "\n".join(all_places)
        logger.info(f"All {len(all_places)} places:\n{places}")

    async def find_places(self, website: dict): #TODO VERIFY
        browser = await self.init_browser()
        links = []
        try:
            page = await self.new_browser_page(browser)
            await self.go_to_website(page, website)
            await self.fill_search_form(page, website)
            max_page = website.get("max_page", None)
            links = await self.get_links(page, website, max_page)
            await browser.close()
        except:
            logger.error(traceback.format_exc())
            await browser.close()
        finally:
            return links

    def open_links(self, places: list):
        for place in places:
            webbrowser.open_new_tab(place)

    async def main(self) -> int: #TODO REPLACE
        try:
            all_places = []
            data = []
            for website in self.websites:
                results = await self.find_places(website)
                logger.debug(results)
                for url in results:
                    all_places.append(url)
                time.sleep(5)
            """
            all_places = sorted(all_places)
            self.print_places(all_places)
            """
            if self.open_results:
                self.open_links(all_places)
            return SUCCESS_CODE
        except:
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

    async def run_bot(self):
        argv = self.read_args()
        bot = Accom_bot(argv.open_results)
        await bot.main()
        


class Tests(unittest.TestCase):
    def setUp(self) -> None:
        return super().setUp()

    def tearDown(self) -> None:
        return super().tearDown()

if __name__ == "__main__":
    run = Run()
    asyncio.get_event_loop().run_until_complete(run.run_bot())