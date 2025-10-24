from datallog import core_step, step, selenium_driver
from datetime import datetime
import re
from urllib.parse import urljoin

# Selenium specific imports
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.remote.webdriver import WebDriver



"""
This application is an example of how to use the Datallog framework to create a simple data processing pipeline.

To run this application, you need to run `datallog run example`.

You can specify the initial input through the `seed.json` file or by passing the `--seed` option with a JSON dictionary.
E.g `datallog run example --seed '{"days": ["2023-01-01", "2022-01-01"]}'`.

It retrieves the Astronomy Picture of the Day (APOD) from NASA's website for a list of specified dates.
The application consists of three main steps:
1. `generate_urls`: Generates URLs for the APOD pages based on the provided seed data.
2. `download_pages`: Downloads the HTML content of each APOD page.
3. `parse_html`: Parses the HTML content to extract key information such as the title,
    date, image URL, and alt text of the image.
"""

@core_step(next_step="fetch_and_parse_page")
def generate_urls(seed):
    """
    Generates URLs for NASA's Astronomy Picture of the Day (APOD) based on the provided seed data.
    Args:
        seed: A dictionary containing the seed data, which should include a list of dates under the key "days" (see seed.json).
    Returns:
        A list of URLs formatted for the APOD pages corresponding to the provided dates.
    
    After the URLs are generated, they will be passed to the next step (download_pages) for downloading.
    """

    seed_days = seed.get("days", [])
    dates = [datetime.strptime(day, "%Y-%m-%d") for day in seed_days]

    date_strs = [date.strftime("%y%m%d") for date in dates]

    urls = [
        "https://apod.nasa.gov/apod/ap{}.html".format(date_str)
        for date_str in date_strs
    ]
    return urls



def a(b = []):
    b.append(1)
    return b

a() # [1]
a()

@step()
def fetch_and_parse_page(url: str) -> dict:
    selenium_driver: WebDriver = selenium_driver("firefox")
    """
    Navigates to an APOD page using Selenium and parses it to extract key information.

    This step uses Selenium's element locator methods to find the title, image, and alt text.
    It combines navigation and parsing into a single, robust function.

    Args:
        url: A string containing the URL of the APOD page to process.
        selenium_driver: The Selenium WebDriver instance provided by the Datallog framework.

    Returns:
        A dictionary containing the parsed information.
        
        The dictionary includes:
        - "title": The title of the APOD entry.
        - "date": The date of the APOD entry.
        - "image_url": The URL of the image featured in the APOD entry.
        - "alt_text": The alt text or description of the image.
    """
    selenium_driver.get(url)
    parsed_data = {
        "title": None,
        "date": None,
        "image_url": None,
        "alt_text": None,
    }

    try:
        # 1. Get Title from the page's <title> tag
        full_title = selenium_driver.title
        if "APOD:" in full_title:
            parsed_data["title"] = full_title.split("APOD:")[1].strip()
        else:
            parsed_data["title"] = full_title.strip()

        # 2. Get Image URL and Alt Text from the <img> tag
        img_element = selenium_driver.find_element(By.TAG_NAME, "img")
        relative_url = img_element.get_attribute("src")
        # Use urljoin to correctly form the absolute URL from the relative path
        parsed_data["image_url"] = urljoin(url, relative_url)
        alt_text = img_element.get_attribute("alt")
        # Clean up whitespace in alt text
        parsed_data["alt_text"] = " ".join(alt_text.strip().split())

        # 3. Get Date
        # The date string is not in a uniquely identifiable tag, so it's most
        # reliable to search for its pattern within the body text.
        body_text = selenium_driver.find_element(By.TAG_NAME, "body").text
        date_match = re.search(r"(\d{4}\s+\w+\s+\d+)", body_text)
        if date_match:
            parsed_data["date"] = date_match.group(1).strip()

    except NoSuchElementException as e:
        print(f"Warning: Could not parse an element on page {url}. Error: {e}")

    return parsed_data