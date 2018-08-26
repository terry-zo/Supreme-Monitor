import aiohttp
import asyncio
import math
import sqlite3
import time
from bs4 import BeautifulSoup as soup
from random import randint, choice
from discord_hooks import Webhook


async def create_webhooks(color=0x0061ff):
    return [
        Webhook("https://discordapp.com/api/webhooks/483371331912728586/RkTSxPXYqDToGTRFPeqanjtIjD9p7tjDyZTv5r5z90Lc2ONH1kvz7gqQQj6AjnR2mbG_", color),
        Webhook("https://discordapp.com/api/webhooks/482851244210389002/TYS8VFdEzqHRAyKhJ42CuQ0LPYF2oCDeQKbxc4qeH1aJfYFabUiRvnzfgC4Sg3tjo2lR", color)
    ]


# Wrapper function
async def initialize():
    proxies = readproxyfile("proxies.txt")
    delay = math.ceil(8 / len(proxies))

    generalHeaders = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36"}

    conn = sqlite3.connect('products.db')
    c = conn.cursor()

    try:

        # If the table already exist it'll throw an error
        with conn:
            c.execute("""CREATE TABLE products (
                        name text,
                        link text,
                        image text,
                        sold_out integer,
                        price text

                )""")

        await startup("http://www.supremenewyork.com/shop/all", proxies, generalHeaders, conn, c)

    except Exception as e:
        print(e)

    while True:
        await monitor("http://www.supremenewyork.com/shop/all", proxies, generalHeaders, conn, c)
        time.sleep(delay)


# Creates an initial database
async def startup(link, proxies, headers, conn, c):

    # 0 False
    # 1 True

    async with aiohttp.ClientSession() as s:
        response = await fetch(s, link, headers, choice(proxies))
        html_soup = soup(response, "html.parser")
        products = html_soup.findAll("div", {"class": "inner-article"})

        async def productInformation(product, s, conn, c):
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

            with conn:
                c.execute("INSERT INTO products VALUES (:name, :link, :image, :sold_out, :price)", {"name": name, "link": link, "image": image, "sold_out": sold_out * 1, "price": price})

            print(f"{name} added to database.")

        futures = [asyncio.ensure_future(productInformation(product, s, conn, c)) for product in products]
        await asyncio.gather(*futures)

        c.execute("SELECT * FROM products")
        all_db_items = c.fetchall()
        print(f"Monitoring {len(all_db_items)} products on Supreme site.")
        webhooks = await create_webhooks(0x0061ff)  # bright blue
        futures = [asyncio.ensure_future(webhook.apost(Announcement=f"Monitoring **{len(all_db_items)} products** on [Supreme]({link}) site.")) for webhook in webhooks]
        await asyncio.gather(*futures)


# Compares newly fetched supreme site from database
async def monitor(link, proxies, headers, conn, c):
    # 0 False
    # 1 True

    async with aiohttp.ClientSession() as s:
        response = await fetch(s, link, headers, choice(proxies))
        html_soup = soup(response, "html.parser")
        products = html_soup.findAll("div", {"class": "inner-article"})

        async def monitorProduct(product, s, conn, c):
            link = f'https://www.supremenewyork.com{product.a["href"]}'
            sold_out = "sold out" in product.text
            database_product = await database_fetch(link, c)

            if database_product is not None:

                # Check if database sold_out = True -> False (Restock)
                if database_product[3] == True and sold_out == False:
                    print(f"{database_product[0]} restocked!")
                    # Send restock embed
                    webhooks = await create_webhooks(0x00ff4c)  # bright green
                    futures = [asyncio.ensure_future(webhook.apost(Restock=database_product[0], Link=database_product[1], Image=database_product[2], Price=database_product[4])) for webhook in webhooks]
                    await asyncio.gather(*futures)

                    # Update database
                    with conn:
                        c.execute("""UPDATE products SET sold_out = :sold_out
                                    WHERE link = :link""",
                                  {'link': link, 'sold_out': 0})

                # Check if database sold_out = False -> True (Sold Out)
                elif database_product[3] == False and sold_out == True:
                    print(f"{database_product[0]} is now sold out.")
                    # Send sold-out embed
                    webhooks = await create_webhooks(0xc11300)  # red
                    futures = [asyncio.ensure_future(webhook.apost(SoldOut=database_product[0], Image=database_product[2])) for webhook in webhooks]
                    await asyncio.gather(*futures)

                    # Update database
                    with conn:
                        c.execute("""UPDATE products SET sold_out = :sold_out
                                    WHERE link = :link""",
                                  {'link': link, 'sold_out': 1})

            else:  # Product does not exist in database
                image = f'https:{product.a.img["src"]}'
                product_html = await fetch(s, link, headers, choice(proxies))
                soupped_html = soup(product_html, "html.parser")
                name = soupped_html.find("title").text
                try:
                    price = soupped_html.find("span", {"itemprop": "price"}).text
                except:
                    price = "$"

                with conn:
                    c.execute("INSERT INTO products VALUES (:name, :link, :image, :sold_out, :price)", {"name": name, "link": link, "image": image, "sold_out": sold_out * 1, "price": price})

                print(f"{name} added to database.")
                # Send new-product embed
                webhooks = await create_webhooks(0xf2ff00)  # bright yellow
                futures = [asyncio.ensure_future(webhook.apost(New=name, Link=link, Image=image, Price=price)) for webhook in webhooks]
                await asyncio.gather(*futures)

        futures = [asyncio.ensure_future(monitorProduct(product, s, conn, c)) for product in products]
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


# Fetches a object from the database with the matching link criteria
async def database_fetch(link, c):
    c.execute("SELECT * FROM products WHERE link=:link", {'link': link})
    return c.fetchone()


if __name__ == "__main__":

    loop = asyncio.get_event_loop()
    loop.run_until_complete(initialize())
