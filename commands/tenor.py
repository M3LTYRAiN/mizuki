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

# 핵심 기능을 분리하여 재사용 가능한 함수로 구현
async def process_tenor_command(context, search, is_slash_command=True):
    """
    Tenor GIF 검색 및 표시 기능을 처리하는 함수
    
    Parameters:
    - context: 슬래시 커맨드의 인터랙션이나 일반 메시지 객체
    - search: 검색어나 Tenor URL
    - is_slash_command: 슬래시 명령어인지 일반 텍스트 명령어인지 구분
    """
    # 응답 지연 (슬래시 명령어일 경우만)
    if is_slash_command:
        await context.response.defer(ephemeral=True)

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
            if is_slash_command:
                await context.edit_original_response(content="해당 URL의 GIF를 찾을 수 없는 것이다. 😢", embed=None, view=None)
            else:
                await context.reply("해당 URL의 GIF를 찾을 수 없는 것이다. 😢", ephemeral=True)
            return

        gif_url = results[0]["media_formats"]["gif"]["url"]

        # 웹훅으로 전송
        channel = context.channel
        author = context.author if not is_slash_command else context
        webhook = await channel.create_webhook(name=author.display_name, avatar=await author.avatar.read())
        await webhook.send(gif_url, username=author.display_name, avatar_url=author.avatar.url)
        await webhook.delete()
        
        # 원본 메시지/인터랙션 삭제 또는 응답 삭제
        if is_slash_command:
            await context.delete_original_response()
        else:
            try:
                await context.delete()
            except:
                pass
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
        if is_slash_command:
            await context.edit_original_response(content="GIF를 찾을 수 없는 것이다. 😢", embed=None, view=None)
        else:
            await context.reply("GIF를 찾을 수 없는 것이다. 😢", ephemeral=True)
        return

    gifs = [item["media_formats"]["gif"]["url"] for item in results]

    # 버튼 인터페이스
    class GifView(disnake.ui.View):
        def __init__(self, original_message=None):
            super().__init__(timeout=60)
            self.current_index = 0
            self.original_message = original_message  # 원본 메시지 저장 (텍스트 명령어용)

        async def interaction_check(self, interaction: disnake.MessageInteraction) -> bool:
            if interaction.user.id != (context.author.id if not is_slash_command else context.user.id):
                await interaction.response.send_message("이 버튼은 명령어 사용한 사람만 사용할 수 있는 것이다!", ephemeral=True)
                return False
            return True

        @disnake.ui.button(label="⬅️ 이전", style=disnake.ButtonStyle.primary)
        async def previous_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
            self.current_index = (self.current_index - 1) % len(gifs)
            await interaction.response.edit_message(embed=make_embed(gifs[self.current_index]), view=self)

        @disnake.ui.button(label="선택", style=disnake.ButtonStyle.success)
        async def select_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
            webhook = await interaction.channel.create_webhook(name=interaction.user.display_name, avatar=await interaction.user.avatar.read())
            await webhook.send(gifs[self.current_index], username=interaction.user.display_name, avatar_url=interaction.user.avatar.url)
            await webhook.delete()
            
            # 원본 메시지 삭제 처리 (사용된 명령어 종류에 따라)
            if is_slash_command:
                await context.delete_original_response()
            else:
                # 응답 메시지 삭제
                await interaction.message.delete()
                
                # 원본 메시지 삭제 시도
                if self.original_message:
                    try:
                        await self.original_message.delete()
                    except:
                        pass

        @disnake.ui.button(label="다음 ➡️", style=disnake.ButtonStyle.primary)
        async def next_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
            self.current_index = (self.current_index + 1) % len(gifs)
            await interaction.response.edit_message(embed=make_embed(gifs[self.current_index]), view=self)

    def make_embed(gif_url):
        return disnake.Embed(title=f"{search} 관련 GIF").set_image(url=gif_url)

    # 응답 처리 (슬래시 명령어 또는 일반 메시지에 따라)
    if is_slash_command:
        await context.edit_original_response(embed=make_embed(gifs[0]), view=GifView())
    else:
        response = await context.reply(
            embed=make_embed(gifs[0]), 
            view=GifView(original_message=context),
            ephemeral=True
        )
        return response

@bot.slash_command(name="테놀", description="GIF를 보내는 것이다.")
async def tenor(inter: disnake.ApplicationCommandInteraction, search: str):
    # 기존 슬래시 명령어는 공통 함수 호출
    await process_tenor_command(inter, search, is_slash_command=True)

# Cog로 등록
def setup(bot):
    bot.add_cog(GifCommand(bot))
