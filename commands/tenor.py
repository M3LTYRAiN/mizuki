import disnake
from disnake.ext import commands
import aiohttp
import os
import re
from dotenv import load_dotenv
from bot import bot

# 환경 변수 로드
load_dotenv()
TENOR_API_KEY = os.getenv('TENOR_API_KEY')

@bot.slash_command(name="tenor", description="GIF를 보내는 것이다.")
async def tenor(inter: disnake.ApplicationCommandInteraction, search: str):
    await inter.response.defer(ephemeral=True)  # 응답을 자신에게만 보이도록 설정

    # Tenor 공유 URL인지 확인
    match = re.match(r"^https?://tenor\.com/(?:[a-z]{2}/)?view/[\w\-]+-(\d+)", search.strip())
    if match:
        gif_id = match.group(1)

        # 해당 ID로 GIF 정보 조회
        async with aiohttp.ClientSession() as session:
            async with session.get("https://tenor.googleapis.com/v2/posts", params={"ids": gif_id, "key": TENOR_API_KEY}) as response:
                data = await response.json()

        results = data.get("results", [])
        if not results:
            await inter.edit_original_response(content="해당 URL의 GIF를 찾을 수 없는 것이다. 😢", embed=None, view=None)
            return

        gif_url = results[0]["media_formats"]["gif"]["url"]

        # 웹훅으로 전송
        webhook = await inter.channel.create_webhook(name=inter.user.display_name, avatar=await inter.user.avatar.read())
        await webhook.send(gif_url, username=inter.user.display_name, avatar_url=inter.user.avatar.url)
        await webhook.delete()
        await inter.delete_original_response()
        return

    # 검색어 기반으로 GIF 검색
    async with aiohttp.ClientSession() as session:
        params = {
            "q": search,
            "key": TENOR_API_KEY,
            "limit": 10,
            "media_filter": "minimal"
        }
        async with session.get("https://tenor.googleapis.com/v2/search", params=params) as response:
            data = await response.json()

    results = data.get("results", [])
    if not results:
        await inter.edit_original_response(content="GIF를 찾을 수 없는 것이다. 😢", embed=None, view=None)
        return

    gifs = [item["media_formats"]["gif"]["url"] for item in results]

    # 버튼 인터페이스
    class GifView(disnake.ui.View):
        def __init__(self):
            super().__init__(timeout=60)
            self.current_index = 0

        async def interaction_check(self, interaction: disnake.MessageInteraction) -> bool:
            if interaction.user.id != inter.user.id:
                await interaction.response.send_message("이 버튼은 명령어 사용한 사람만 사용할 수 있는 것이다!", ephemeral=True)
                return False
            return True

        @disnake.ui.button(label="⬅️ 이전", style=disnake.ButtonStyle.primary)
        async def previous_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
            self.current_index = (self.current_index - 1) % len(gifs)
            await interaction.response.edit_message(embed=make_embed(gifs[self.current_index]), view=self)

        @disnake.ui.button(label="선택", style=disnake.ButtonStyle.success)
        async def select_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
            webhook = await inter.channel.create_webhook(name=interaction.user.display_name, avatar=await interaction.user.avatar.read())
            await webhook.send(gifs[self.current_index], username=interaction.user.display_name, avatar_url=interaction.user.avatar.url)
            await webhook.delete()
            await inter.delete_original_response()

        @disnake.ui.button(label="다음 ➡️", style=disnake.ButtonStyle.primary)
        async def next_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
            self.current_index = (self.current_index + 1) % len(gifs)
            await interaction.response.edit_message(embed=make_embed(gifs[self.current_index]), view=self)

    def make_embed(gif_url):
        return disnake.Embed(title=f"{search} 관련 GIF").set_image(url=gif_url)

    await inter.edit_original_response(embed=make_embed(gifs[0]), view=GifView())

# Cog로 등록
def setup(bot):
    bot.add_cog(GifCommand(bot))
