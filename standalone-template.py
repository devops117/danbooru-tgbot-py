from pyrogram import Client, idle, filters
from pyrogram.types import Message
from asyncio import get_event_loop, sleep
from os import environ as env
from logging import basicConfig, INFO

from aiohttp import ClientSession as aiohttpClient
from aiofiles.tempfile import TemporaryDirectory
from aiofiles import open
import ujson

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

async def danbooru(url):
    async with aiohttpClient(json_serialize=ujson.dumps) as session:
        async with session.get(url) as resp:
            return await resp.json()

@app.on_message(filters.command("get"))
async def givemethesauce(_, msg: Message):
    try:
        match = [ i for i in await danbooru(f"{url}/tags.json?search[name_or_alias_matches]={msg.command[1]}") ][0]
    except IndexError:
        match = None
        await msg.reply_text("404: Not Found")
    
    if match:
        post_count = match["post_count"]
        name = match["name"]
        i = 1
        async with TemporaryDirectory() as tempdir:
            async with open(f"{tempdir}/sauce.txt", 'w') as f:
                while post_count >= 0:
                    z = await danbooru(f"{url}/posts.json?tags={name}&limit=200&page={i}")
                    for j in z:
                        x = j.get("file_url")
                        if x:
                            await f.write(f"{x}\n")
                    i+=1
                    post_count -= 200
                    print(f"post_count: {post_count}")
                await f.close()
                await msg.reply_document(f.name)
                
        
get_event_loop().run_until_complete(main())
