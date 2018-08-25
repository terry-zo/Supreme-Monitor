import aiohttp
import asyncio
import math
import sqlite3
import time
from bs4 import BeautifulSoup as soup
from random import randint, choice
from discord_hooks import Webhook


# Wrapper function
async def initialize():
    proxies = readproxyfile("proxies.txt")
    delay = math.ceil(8 / len(proxies))

    webhook_url = "https://discordapp.com/api/webhooks/482851244210389002/TYS8VFdEzqHRAyKhJ42CuQ0LPYF2oCDeQKbxc4qeH1aJfYFabUiRvnzfgC4Sg3tjo2lR"

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

        await startup("http://www.supremenewyork.com/shop/all", proxies, generalHeaders, webhook_url, conn, c)

    except Exception as e:
        print(e)

    while True:
        await monitor("http://www.supremenewyork.com/shop/all", proxies, generalHeaders, webhook_url, conn, c)
        time.sleep(delay)


# Creates an initial database
async def startup(link, proxies, headers, webhook_url, conn, c):
    async with aiohttp.ClientSession() as s:
        response = await fetch(s, link, headers, choice(proxies))
    html_soup = soup(response, "html.parser")
    products = html_soup.findAll("div", {"class": "inner-article"})
    webhook = Webhook(webhook_url, color=0xc11300)
    await webhook.apost(Announcement=f"Monitoring **{len(products)} products** on supreme site.")

    async def productInformation(product, s):
        link = f'https://www.supremenewyork.com{product.a["href"]}'

        image = f'https:{product.a.img["src"]}'
        sold_out = product.text == "sold out"

        async with aiohttp.ClientSession() as s:
            product_html = await fetch(s, link, headers, choice(proxies))
        soupped_html = soup(product_html, "html.parser")
        name = soupped_html.find("title").text
        price = soupped_html.find("p", {"class": "price"}).span.text

        with conn:
            c.execute("INSERT INTO products VALUES (:name, :link, :image, :sold_out, :price)", {"name": name, "link": link, "image": image, "sold_out": sold_out * 1, "price": price})

        print(f"{name} added to database.")

    futures = [asyncio.ensure_future(productInformation(product, s)) for product in products]
    await asyncio.gather(*futures)


# Compares newly fetched supreme site from database
async def monitor(link, proxies, headers, webhook_url, conn, c):
    async with aiohttp.ClientSession() as s:
        response = await fetch(s, link, headers, choice(proxies))
    html_soup = soup(response, "html.parser")
    products = html_soup.findAll("div", {"class": "inner-article"})

    async def monitorProduct(product, s):
        link = f'https://www.supremenewyork.com{product.a["href"]}'
        sold_out = product.text == "sold out"
        database_product = await database_fetch(link, c)

        if database_product is not None:

            # Check if database sold_out = False -> True (Sold Out)
            if database_product[3] == False and sold_out == True:
                print(f"{database_product[0]} is now sold out.")
                # Send sold-out embed
                webhook = Webhook(webhook_url, color=0xc11300)
                await webhook.apost(SoldOut=database_product[0], Link=database_product[1], Image=database_product[2])

                # Update database
                with conn:
                    c.execute("""UPDATE products SET sold_out = :sold_out
                                WHERE link = :link""",
                              {'link': link, 'sold_out': sold_out * 1})

            # Check if database sold_out = True -> False (Restock)
            elif database_product[3] == True and sold_out == False:
                print(f"{database_product[0]} restocked!")
                # Send restock embed
                webhook = Webhook(webhook_url, color=0xc11300)
                await webhook.apost(Restock=database_product[0], Link=database_product[1], Image=database_product[2], Price=database_product[4])

                # Update database
                with conn:
                    c.execute("""UPDATE products SET sold_out = :sold_out
                                WHERE link = :link""",
                              {'link': link, 'sold_out': sold_out * 1})

        else:  # Product does not exist in database
            image = f'https:{product.a.img["src"]}'
            async with aiohttp.ClientSession() as s:
                product_html = await fetch(s, link, headers, choice(proxies))
            soupped_html = soup(product_html, "html.parser")
            name = soupped_html.find("title").text
            price = soupped_html.find("p", {"class": "price"}).span.text
            with conn:
                c.execute("INSERT INTO products VALUES (:name, :link, :image, :sold_out, :price)", {"name": name, "link": link, "image": image, "sold_out": sold_out * 1, "price": price})

            print(f"{name} added to database.")
            # Send new-product embed
            webhook = Webhook(webhook_url, color=0xc11300)
            await webhook.apost(New=name, Link=link, Image=image, Price=price)

    futures = [asyncio.ensure_future(monitorProduct(product, s)) for product in products]
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
