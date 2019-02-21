import asyncio
import os
import inspect
import re
import logging

import aiohttp
import aiofiles
from bs4 import BeautifulSoup

OUTPUT_FOLDER = f'{os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))}/output'
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

logging.basicConfig(level=logging.INFO)


async def get_image(session, url):
    """Get single image on the provided url

    :param session: http session passed to the function
    :param url: image url
    :return: image in bytes format
    """
    async with session.get(url) as resp:
        if resp.status != 200:
            logging.error(f'response status != 200 for image {url}')
            return None
        return await resp.read()


async def get_page(session, url):
    """Try to get content on the provided url

    :param session: session passed to the function
    :param url: page url
    :return: if request is successful page content is returned. Otherwise None is returned.
    """
    try:
        resp = await session.get(url)
        if resp.status != 200:
            logging.error('response status != 200 for %s', url)
            return None
        return await resp.text()
    except aiohttp.ClientConnectorCertificateError:
        logging.error('certificate error for page %s', url)
        return None
    except Exception as e:
        logging.error('Exception %s for %s', e, url)
        return None


async def get_all_relevant_subpages(session, main_page):
    """Get all sub pages with the main page domain

    :param session: session passed to the function
    :param main_page: page used to search for sub pages
    :return: list of relevant sub pages
    """
    url = f'https://{main_page}'
    content = await get_page(session, url)

    soup = BeautifulSoup(content, features="html.parser")
    links = [link.get('href') for link in soup.find_all('a', attrs={'href': re.compile("^http")})]
    relevant_links = [link for link in links if main_page in link]

    return relevant_links


async def get_url_images(session, url):
    """Get all images available on the provided url

    :param session: http session passed to the function
    :param url:
    :return: list of tuples in format (source, bytes image)
    """
    content = await get_page(session, url)
    if not content:
        return []
    soup = BeautifulSoup(content, features="html.parser")
    image_sources = [img['src'] for img in soup.find_all('img')]
    image_sources_fixed = [f'https:{source}' if 'https:' not in source else source for source in image_sources]
    images = []
    for source in image_sources_fixed:
        image = await get_image(session, source)
        if image:
            images.append((source, image))

    return images


async def save_url_images(images):
    """Save all provided images to the hard drive

    :param images: list of image tuples from get_url_images
    """
    for source, image in images:
        name = source.split('/')[-1]
        async with aiofiles.open(f'{OUTPUT_FOLDER}/{name}', 'wb') as f:
            await f.write(image)


async def scrape_page(session, url):
    """Get and save all the images found on the page

    :param session: http session passed to the function
    :param url: url of the page
    """
    logging.info('Scraping %s', url)
    images = await get_url_images(session, url)
    await save_url_images(images)


async def scrape_pages(session, pages):
        """Get and save all the images found on all the pages

        :param session: http session passed to the function
        :param pages: list of pages
        """
        tasks = [scrape_page(session, url) for url in pages]
        await asyncio.gather(*tasks)


async def download_all_images(main_page):
    """Download all images found on the main page and its sub pages

    :param main_page: main page used to search for sub pages and images
    """
    all_relevant_pages = [f'https://{main_page}']
    async with aiohttp.ClientSession() as session:
        subpages = await get_all_relevant_subpages(session, main_page)
        all_relevant_pages.extend(subpages)

        await scrape_pages(session, all_relevant_pages)

    logging.info('Images from main page %s and its sub pages were download', main_page)


async def main():
    await download_all_images('exponea.com')


if __name__ == "__main__":
    asyncio.run(main())
