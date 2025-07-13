from datallog import core_step, step
import requests
import re
from datetime import datetime

"""
This application is an example of how to use the Datallog framework to create a simple data processing pipeline.

To run this application, you need run `datallog run example`

To push the applications to the Datallog service, use `datallog push`.


It retrieves the Astronomy Picture of the Day (APOD) from NASA's website for a list of specified dates.
The application consists of three main steps:
1. `generate_urls`: Generates URLs for the APOD pages based on the provided seed data.
2. `download_pages`: Downloads the HTML content of each APOD page.
3. `parse_html`: Parses the HTML content to extract key information such as the title,
    date, image URL, and alt text of the image.
"""

@core_step(next_step="download_pages")
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

    date_strs = [date.strftime("%Y%m%d") for date in dates]

    urls = [
        "https://apod.nasa.gov/apod/ap{}.html".format(date_str)
        for date_str in date_strs
    ]
    return urls


@step(next_step="parse_html")
def download_pages(url):
    """
    Downloads the HTML content of a given URL.
    Args:
        url: A string containing the URL to download.
    Returns:
        A string containing the HTML content of the page.
    
    This step will be executed for each URL generated in the previous step (generate_urls).
    It retrieves the HTML content of the NASA APOD page for further processing.
    """
    return requests.get(url).text


@step()
def parse_html(html: str):
    """
    Parses the HTML of a NASA APOD page to extract key information.

    Args:
        html: A string containing the HTML content of the APOD page.

    Returns:
        A dictionary containing the parsed information.
        
        The dictionary includes:
        - "title": The title of the APOD entry.
        - "date": The date of the APOD entry.
        - "image_url": The URL of the image featured in the APOD entry.
        - "alt_text": The alt text or description of the image.

    This function uses regular expressions to extract the title, date, image URL, and alt text from the HTML content.
    It constructs a dictionary with this information, which can be used for further processing or storage.
    Example of the returned dictionary:
    
    {
        "title": "Astronomy Picture of the Day",
        "date": "2023 January 01",
        "image_url": "https://apod.nasa.gov/apod/image/230101/image.jpg",
        "alt_text": "A beautiful image of the night sky."
    }
    
    """
    parsed_data = {}

    # Regex to find the title
    title_match = re.search(r"<title>\s*APOD:\s*(.*?)\s*</title>", html, re.IGNORECASE)
    if title_match:
        parsed_data["title"] = title_match.group(1).strip()

    # Regex to find the date
    date_match = re.search(r"(\d{4}\s+\w+\s+\d+)", html)
    if date_match:
        parsed_data["date"] = date_match.group(1).strip()

    # Regex to find the image URL
    image_match = re.search(r'<IMG SRC="([^"]*?)"', html, re.IGNORECASE)
    if image_match:
        # Construct full URL if relative
        base_url = "https://apod.nasa.gov/apod/"
        parsed_data["image_url"] = base_url + image_match.group(1)

    # Regex to find the image alt text (description)
    alt_text_match = re.search(
        r'<IMG SRC="[^"]*?"\s+alt="([^"]*?)"', html, re.DOTALL | re.IGNORECASE
    )
    if alt_text_match:
        parsed_data["alt_text"] = " ".join(alt_text_match.group(1).strip().split())

    return parsed_data
