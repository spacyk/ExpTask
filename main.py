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
    async with session.get(url) as resp:
        if resp.status != 200:
            logging.error(f'response status != 200 for image {url}')
            return None
        return await resp.read()


async def get_page(session, url):
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


async def get_all_relevant_subpagese(session, url='https://exponea.com/'):

    content = await get_page(session, url)

    soup = BeautifulSoup(content, features="html.parser")
    links = [link.get('href') for link in soup.find_all('a', attrs={'href': re.compile("^http")})]
    exponea_links = [link for link in links if 'exponea.com' in link]

    return exponea_links


async def get_url_images(session, url='https://exponea.com/'):
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


async def save_images(images):
    for source, image in images:
        name = source.split('/')[-1]
        async with aiofiles.open(f'{OUTPUT_FOLDER}/{name}', 'wb') as f:
            await f.write(image)


async def scrape_page(session, url):
    logging.info('Scraping %s', url)
    images = await get_url_images(session, url)
    await save_images(images)

async def main():

    main_page = 'exponea.com'
    main_url = f'https://{main_page}'

    async with aiohttp.ClientSession() as session:

        subpages = await get_all_relevant_subpagese(session, url=main_url)

        tasks = [scrape_page(session, url) for url in subpages]
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
