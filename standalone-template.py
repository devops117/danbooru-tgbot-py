from pyrogram import Client, idle, filters
from pyrogram.types import Message
from asyncio import get_event_loop
from os import environ as env
from logging import basicConfig, INFO

from aiohttp import ClientSession as aiohttpClient
from aiofiles.tempfile import TemporaryDirectory
from aiofiles import open
import ujson
from math import ceil
from aiostream import stream

url = "https://danbooru.donmai.us"
basicConfig(level=INFO)
# maybe use ":memory:"
app = Client("test",
        int(env.get("api_id")),
        env.get("api_hash"),
        bot_token=env.get("bot_token"))

async def main():
    await app.start()
    await idle()

async def get(url: str, iterator: int=1):
    async with aiohttpClient(json_serialize=ujson.dumps) as session:
        for page in range(iterator):
            async with session.get(url) as resp:
                if resp.status != 500:
                    yield resp


async def search(url: str):
    async with aiohttpClient(json_serialize=ujson.dumps) as session:
        async with session.get(url) as resp:
            if resp.status == 500:
                return []
            else:
                return await resp.json()


@app.on_message(filters.command("get"))
async def givemethesauce(_, msg: Message):
    try:
        match = (await search(f"{url}/tags.json?search[name_or_alias_matches]={msg.command[1]}"))[0]
    except IndexError:
        match = None
        await msg.reply_text("404: Not Found")
    
    if match:
        POST_LIMIT = 200
        post_count = ceil(match["post_count"]/POST_LIMIT)
        name = match["name"]
        async with TemporaryDirectory() as tempdir:
            async with open(f"{tempdir}/sauce.txt", 'w') as f:
                async for resp in get(
                    f"""{url}/posts.json?
                    tags={name}&limit=200""",
                    post_count
                ):
                    async with stream.iterate(
                        await resp.json()
                    ).stream() as streamer:
                        async for post in streamer:
                            if post.get('file_url'):
                                await f.write(f"{post.get('file_url')}\n")
                await f.close()
                await msg.reply_document(f.name)
                
        
get_event_loop().run_until_complete(main())
