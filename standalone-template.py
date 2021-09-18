from pyrogram import Client, idle, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
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

async def get(url: str, iterator: int=0):
    async with aiohttpClient(json_serialize=ujson.dumps) as session:
        if iterator:
            for page in range(iterator):
                async with session.get(
                    f"{url}&page={page}"
                ) as resp:
                    if resp.status != 500:
                        yield resp
        else:
            async with session.get(url) as resp:
                if resp.status != 500:
                    yield resp


@app.on_message(filters.command("get"))
async def searchthestuff(_, msg: Message):
    RESULT_LIMIT=10
    async for resp in (
        get(f"{url}/tags.json?search[name_or_alias_matches]={msg.command[1]}")
    ):
        async with stream.chunks(
            stream.map(
                stream.iterate(
                    await resp.json()
                ),
                lambda x: [InlineKeyboardButton(
                    text=f"{x['name']}--{x['post_count']}",
                    callback_data=f"owo--{x['name']}--{x['post_count']}"
                )]
            ),
            RESULT_LIMIT
        ).stream() as streamer:
            async for i in streamer:
                await msg.reply_text(
                    "search results:",
                    reply_markup=InlineKeyboardMarkup(i)
                )


@app.on_callback_query(filters.regex("^owo"))
async def givemethesauce(_, query: CallbackQuery):
    POST_LIMIT = 200
    match = query.data.split("--")
    name = match[1]
    post_count = ceil(int(match[2])/POST_LIMIT)
    async with TemporaryDirectory() as tempdir:
        async with open(f"{tempdir}/sauce-{name}.txt", 'w') as f:
            async for resp in get(
                f"{url}/posts.json?tags={name}&limit=200",
                post_count
            ):
                async with stream.iterate(
                    await resp.json()
                ).stream() as streamer:
                    async for post in streamer:
                        if post.get('file_url'):
                            await f.write(f"{post.get('file_url')}\n")
            await f.close()
            await query.message.reply_document(f.name)
                
        
get_event_loop().run_until_complete(main())
