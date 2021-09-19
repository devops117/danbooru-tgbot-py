from pyrogram import Client, idle, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from asyncio import get_event_loop, gather, sleep
from os import environ as env, cpu_count
from logging import basicConfig, INFO
from aiohttp import ClientSession as aiohttpClient
from aiofiles.tempfile import TemporaryDirectory
from aiofiles import open
import ujson
from math import ceil, gcd
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


async def get(url: str, iterator: range=range(0)):
    async with aiohttpClient(json_serialize=ujson.dumps) as session:
        if iterator:
            for page in iterator:
                async with session.get(
                    f"{url}&page={page}"
                ) as resp:
                    if resp.status == 500:
                        async for resp in get(url, range(page, iterator.step, iterator.stop)):
                            yield resp
                    else:
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


async def IO(page_count, name, file):
    async for resp in get(
        f"{url}/posts.json?tags={name}&limit=200",
        page_count
    ):
        async with stream.iterate(
            await resp.json()
        ).stream() as streamer:
            async for post in streamer:
                if type(post)==dict and post.get('file_url'):
                    await file.write(f"{post.get('file_url')}\n")


@app.on_callback_query(filters.regex("^owo"))
async def givemethesauce(_, query: CallbackQuery):
   async with TemporaryDirectory() as tempdir:
        match = query.data.split("--")
        name = match[1]
        async with open(f"{tempdir}/sauce-{name}.txt", 'w') as file:
            POST_LIMIT = 200
            tasks = []
            start = 1
            page_count = ceil(int(match[2])/POST_LIMIT) if int(match[2])<=200_000 else 1000
            cpu_count_ = cpu_count() # gcd(cpu_count())
            corus = page_count%cpu_count_
            if corus:
                corus = gcd(ceil(page_count-(page_count%cpu_count_)), cpu_count_)+1
                diff = ceil((page_count-(page_count%cpu_count_))/cpu_count_)+1
            else:
                corus = cpu_count_
                diff = page_count//cpu_count_

            for task_id in range(1, corus+1):
                if task_id*diff+1 > page_count:
                    tasks+=[loop.create_task(IO(
                        range(start, page_count+1),
                        name, file))]
                    break
                else:
                    tasks+=[loop.create_task(IO(
                        range(start, task_id*diff+1),
                        name, file))]
                    start+=diff

            await gather(*tasks)
            await file.close()
            await query.message.reply_document(file.name)


loop = get_event_loop()
loop.run_until_complete(main())
