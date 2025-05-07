
import disnake
from disnake.ext import commands
from bot import bot

@bot.slash_command(
    name="테스트",
    description="관리자 전용 테스트 명령어인 것이다."
)
@commands.has_permissions(administrator=True)
async def test_command(inter: disnake.ApplicationCommandInteraction):
    await inter.response.send_message("야옹! 테스트가 성공한 것이다! 😺")