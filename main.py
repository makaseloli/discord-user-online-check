import asyncio
import os
from contextlib import asynccontextmanager
from typing import Optional, Tuple

import discord
from discord.utils import MISSING
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

import dotenv

dotenv.load_dotenv()

DISCORD_TOKEN = os.environ["DISCORD_BOT_TOKEN"]

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.presences = True

client = discord.Client(intents=intents)
_start_task: Optional[asyncio.Task[None]] = None


async def wait_until_ready() -> None:
    if client.is_ready():
        return
    await client.wait_until_ready()


async def ensure_client_started() -> None:
    global _start_task
    if client.is_ready():
        return
    if _start_task is None or _start_task.done():
        _start_task = asyncio.create_task(client.start(DISCORD_TOKEN))
    while getattr(client, "_ready", MISSING) is MISSING:
        if _start_task.done():
            _start_task.result()
        await asyncio.sleep(0.05)
    await wait_until_ready()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_client_started()
    try:
        yield
    finally:
        global _start_task
        if client.is_ready():
            await client.close()
        _start_task = None


app = FastAPI(lifespan=lifespan)


class UserQuery(BaseModel):
    user_id: int


async def get_member(user_id: int) -> Optional[discord.Member]:
    await wait_until_ready()
    for guild in client.guilds:
        member = guild.get_member(user_id)
        if member and member.status not in (None, discord.Status.offline):
            return member

        if member is None:
            try:
                member = await guild.fetch_member(user_id)
            except discord.NotFound:
                member = None
            else:
                if member.status not in (None, discord.Status.offline):
                    return member

        try:
            matched = await guild.query_members(
                user_ids=[user_id],
                presences=True,
                cache=True,
            )
        except discord.HTTPException:
            matched = []

        for candidate in matched:
            if candidate.id == user_id:
                if candidate.status not in (None, discord.Status.offline):
                    return candidate
                member = member or candidate

        if member is not None:
            return member

    return None


async def _resolve_status(user_id: int) -> Tuple[Optional[discord.Status], bool]:
    member = await get_member(user_id)
    if member is None:
        return None, False
    if member.status is None or member.status == discord.Status.offline:
        return None, True
    return member.status, True


@app.post("/check-status")
async def check_status(payload: UserQuery):
    status_value, found = await _resolve_status(payload.user_id)
    if not found:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found",
        )
    if status_value:
        return {"status": status_value.name}
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="User offline",
    )


@app.get("/{user_id}")
async def check_status_from_path(user_id: str):
    try:
        snowflake = int(user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID",
        ) from exc

    status_value, found = await _resolve_status(snowflake)
    if not found:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found",
        )
    if status_value:
        return {"status": status_value.name}
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="User offline",
    )
