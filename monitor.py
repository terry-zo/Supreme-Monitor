import aiohttp
import asyncio
import math
import sqlite3
import time
from pymongo import MongoClient
from bs4 import BeautifulSoup as soup
from random import randint, choice
from discord_hooks import Webhook


class SupremeDatabase(object):
    """A mongo database that contains accumulated supreme products."""

    def __init__(self):
        mongoURL = "mongodb://terry:terry123@ds133632.mlab.com:33632/monitors"
        client = MongoClient(mongoURL)
        db = client["monitors"]
        self.keys = db["supreme"]

    # Fetches a object from the database with the matching link criteria
    def database_fetch(self, link):
        return self.keys.find_one({"link": link})

    # Inserts a supreme product into the database and stores it for further use
    def insert_product(self, name, link, image, sold_out, price):
        keys = self.keys
        user_key = self.keys.find_one({"link": link})
        if user_key is None:
            post = {
                "name": name,
                "link": link,
                "image": image,
                "sold_out": sold_out,
                "price": price
            }
            self.keys.insert_one(post)
        else:
            print(f"{name} already exists in database.")

    def update_product(self, _query, _set):
        self.keys.find_one_and_update(_query, _set)


async def create_webhooks(color=0x0061ff):
    return [
        Webhook("https://discordapp.com/api/webhooks/483371331912728586/RkTSxPXYqDToGTRFPeqanjtIjD9p7tjDyZTv5r5z90Lc2ONH1kvz7gqQQj6AjnR2mbG_", color=color),
        Webhook("https://discordapp.com/api/webhooks/482851244210389002/TYS8VFdEzqHRAyKhJ42CuQ0LPYF2oCDeQKbxc4qeH1aJfYFabUiRvnzfgC4Sg3tjo2lR", color=color)
    ]


# Wrapper function
async def initialize():
    proxies = readproxyfile("proxies.txt")
    delay = math.ceil(8 / len(proxies))

    generalHeaders = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36"}

    mongoSupreme = SupremeDatabase()

    if mongoSupreme.keys.find_one() is None:
        await startup("http://www.supremenewyork.com/shop/all", proxies, generalHeaders, mongoSupreme)
    else:
        print("Monitoring http://www.supremenewyork.com/shop/all")
        while True:
            await monitor("http://www.supremenewyork.com/shop/all", proxies, generalHeaders, mongoSupreme)
            time.sleep(delay)


# Creates an initial database
async def startup(link, proxies, headers, mongoSupreme):

    # 0 False
    # 1 True

    print("Scraping http://www.supremenewyork.com/shop/all")

    async with aiohttp.ClientSession() as s:
        response = await fetch(s, link, headers, choice(proxies))
        html_soup = soup(response, "html.parser")
        products = html_soup.findAll("div", {"class": "inner-article"})

        async def productInformation(product, s, mongoSupreme):
            link = f'https://www.supremenewyork.com{product.a["href"]}'

            image = f'https:{product.a.img["src"]}'
            sold_out = "sold out" in product.text

            product_html = await fetch(s, link, headers, choice(proxies))
            soupped_html = soup(product_html, "html.parser")
            name = soupped_html.find("title").text
            try:
                price = soupped_html.find("span", {"itemprop": "price"}).text
            except:
                price = "$"

            mongoSupreme.insert_product(name, link, image, sold_out, price)
            print(f"{name} added to database.")

        futures = [asyncio.ensure_future(productInformation(product, s, mongoSupreme)) for product in products]
        await asyncio.gather(*futures)

        all_db_items = mongoSupreme.keys.count_documents({})
        print(f"Monitoring {all_db_items} products on Supreme site.")
        webhooks = await create_webhooks(0x0061ff)  # bright blue
        futures = [asyncio.ensure_future(webhook.apost(Announcement=f"Monitoring **{all_db_items} products** on [Supreme]({link}) site.")) for webhook in webhooks]
        await asyncio.gather(*futures)


# Compares newly fetched supreme site from database
async def monitor(link, proxies, headers, mongoSupreme):
    # 0 False
    # 1 True

    async with aiohttp.ClientSession() as s:
        response = await fetch(s, link, headers, choice(proxies))
        html_soup = soup(response, "html.parser")
        products = html_soup.findAll("div", {"class": "inner-article"})

        async def monitorProduct(product, s, mongoSupreme, proxies):
            link = f'https://www.supremenewyork.com{product.a["href"]}'
            sold_out = "sold out" in product.text
            database_product = mongoSupreme.database_fetch(link)

            if database_product is not None:

                # Check if database sold_out = True -> False (Restock)
                if database_product["sold_out"] == True and sold_out == False:
                    print(f"{database_product['name']} restocked!")
                    # Send restock embed
                    webhooks = await create_webhooks(0x00ff4c)  # bright green
                    futures = [asyncio.ensure_future(webhook.apost(Restock=database_product["name"], Link=database_product["link"], Image=database_product["image"], Price=database_product["price"])) for webhook in webhooks]
                    await asyncio.gather(*futures)

                    # Update database
                    mongoSupreme.update_product({"link": link}, {"sold_out": sold_out})

                # Check if database sold_out = False -> True (Sold Out)
                elif database_product["sold_out"] == False and sold_out == True:
                    print(f"{database_product['name']} is now sold out.")
                    # Send sold-out embed
                    webhooks = await create_webhooks(0xc11300)  # red
                    futures = [asyncio.ensure_future(webhook.apost(SoldOut=database_product["name"], Image=database_product["name"])) for webhook in webhooks]
                    await asyncio.gather(*futures)

                    # Update database
                    mongoSupreme.update_product({"link": link}, {"sold_out": sold_out})

                if database_product["price"] == "$":
                    product_html = await fetch(s, database_product["link"], headers, choice(proxies))
                    soupped_html = soup(product_html, "html.parser")
                    try:
                        price = soupped_html.find("span", {"itemprop": "price"}).text

                        # Update database
                        mongoSupreme.update_product({"link": database_product["link"]}, {"price": price})

                    except Exception as e:
                        print(f"{e}")

            else:  # Product does not exist in database
                image = f'https:{product.a.img["src"]}'
                product_html = await fetch(s, link, headers, choice(proxies))
                soupped_html = soup(product_html, "html.parser")
                name = soupped_html.find("title").text
                try:
                    price = soupped_html.find("span", {"itemprop": "price"}).text
                except:
                    price = "$"

                mongoSupreme.insert_product(name, link, image, sold_out, price)
                print(f"{name} added to database.")

                # Send new-product embed
                webhooks = await create_webhooks(0xf2ff00)  # bright yellow
                futures = [asyncio.ensure_future(webhook.apost(New=name, Link=link, Image=image, Price=price)) for webhook in webhooks]
                await asyncio.gather(*futures)

        futures = [asyncio.ensure_future(monitorProduct(product, s, mongoSupreme, proxies)) for product in products]
        await asyncio.gather(*futures)


# Returns a list of proxies from designated file name passed as an argument
def readproxyfile(proxyfile):
    with open(proxyfile, "r") as raw_proxies:
        proxies = raw_proxies.read().split("\n")
        proxies_list = []
        for individual_proxies in proxies:
            if individual_proxies.strip() != "":
                p_splitted = individual_proxies.split(":")
                if len(p_splitted) == 2:
                    proxies_list.append("http://" + individual_proxies)
                if len(p_splitted) == 4:
                    # ip0:port1:user2:pass3
                    # -> username:password@ip:port
                    p_formatted = f"http://{p_splitted[2]}:{p_splitted[3]}@{p_splitted[0]}:{p_splitted[1]}"
                    proxies_list.append(p_formatted)
        proxies_list.append(None)
    return proxies_list


# Utilizes asyncio and aiohttp for retrieving asynchronous HTML flawlessly
async def fetch(session, url, headers=None, proxy=None):
    # print(f"Using proxy: {proxy}")
    async with session.get(url, headers=headers, proxy=proxy) as response:
        return await response.text()


if __name__ == "__main__":

    loop = asyncio.get_event_loop()
    loop.run_until_complete(initialize())
