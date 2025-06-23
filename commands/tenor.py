import disnake
from disnake.ext import commands
import aiohttp
import os
import re
import random  # 랜덤 모듈 추가
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
                await context.reply("해당 URL의 GIF를 찾을 수 없는 것이다. 😢")
            return

        gif_url = results[0]["media_formats"]["gif"]["url"]

        # 웹훅으로 전송 (수정된 부분)
        channel = context.channel
        author = context.author if not is_slash_command else context
        
        # 아바타 처리 - 아바타가 없는 경우 기본 아바타 사용
        try:
            avatar_bytes = await author.avatar.read() if author.avatar else None
            webhook = await channel.create_webhook(name=author.display_name, avatar=avatar_bytes)
            await webhook.send(gif_url, username=author.display_name, avatar_url=author.display_avatar.url)
            await webhook.delete()
        except Exception as e:
            print(f"웹훅 생성 중 오류: {e}")
            # 웹훅 생성 실패 시 일반 메시지로 전송
            await channel.send(f"{author.mention}: {gif_url}")
        
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
            await context.reply("GIF를 찾을 수 없는 것이다. 😢")
        return

    gifs = [item["media_formats"]["gif"]["url"] for item in results]

    # !테놀 텍스트 명령어인 경우 랜덤 GIF 즉시 전송
    if not is_slash_command:
        # 검색 결과에서 랜덤하게 하나 선택
        random_gif_url = random.choice(gifs)
        
        # 웹훅으로 전송 (오류 처리 추가)
        try:
            # 아바타 체크 추가
            avatar_bytes = await context.author.avatar.read() if context.author.avatar else None
            webhook = await context.channel.create_webhook(name=context.author.display_name, avatar=avatar_bytes)
            # display_avatar를 사용하면 기본 아바타 URL을 가져올 수 있음
            await webhook.send(random_gif_url, username=context.author.display_name, avatar_url=context.author.display_avatar.url)
            await webhook.delete()
        except Exception as e:
            print(f"웹훅 생성 중 오류: {e}")
            # 웹훅 생성 실패 시 일반 메시지로 전송
            await context.channel.send(f"{context.author.mention}: {random_gif_url}")
        
        # 원본 명령어 메시지 삭제
        try:
            await context.delete()
        except:
            pass
        
        return

    # 슬래시 명령어용 GIF 선택 UI
    class GifView(disnake.ui.View):
        def __init__(self):
            super().__init__(timeout=60)
            self.current_index = 0

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
            try:
                # 아바타 처리 - 아바타가 없는 경우 기본 아바타 사용
                avatar_bytes = await interaction.user.avatar.read() if interaction.user.avatar else None
                webhook = await interaction.channel.create_webhook(name=interaction.user.display_name, avatar=avatar_bytes)
                await webhook.send(gifs[self.current_index], username=interaction.user.display_name, avatar_url=interaction.user.display_avatar.url)
                await webhook.delete()
            except Exception as e:
                print(f"웹훅 생성 중 오류: {e}")
                # 웹훅 생성 실패 시 일반 메시지로 전송
                await interaction.channel.send(f"{interaction.user.mention}: {gifs[self.current_index]}")
            
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
