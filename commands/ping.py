import disnake
from disnake.ext import commands
from bot import bot
import time

@bot.slash_command(
    name="핑",
    description="봇의 지연 시간을 보여주는 것이다."
)
async def ping(inter: disnake.ApplicationCommandInteraction):
    # 응답 지연 (Discord API 지연 시간 측정용)
    start = time.perf_counter()
    await inter.response.defer()
    end = time.perf_counter()
    
    # API 지연 시간
    api_latency = round((end - start) * 1000)
    
    # 웹소켓 지연 시간
    ws_latency = round(bot.latency * 1000)
    
    # 결과 표시
    embed = disnake.Embed(
        title="🏓 퐁!",
        description="봇의 응답 시간을 측정한 것이다!",
        color=disnake.Color.blue()
    )
    
    embed.add_field(
        name="API 지연 시간",
        value=f"`{api_latency}ms`",
        inline=True
    )
    
    embed.add_field(
        name="웹소켓 지연 시간",
        value=f"`{ws_latency}ms`",
        inline=True
    )
    
    status = "매우 좋은 것이다! 😄" if ws_latency < 100 else \
             "좋은 것이다! 🙂" if ws_latency < 200 else \
             "괜찮은 것이다. 😐" if ws_latency < 400 else \
             "느린 것이다... 😕" if ws_latency < 800 else \
             "매우 느린 것이다! 😢"
             
    embed.add_field(
        name="상태",
        value=status,
        inline=False
    )
    
    embed.set_footer(text=f"요청자: {inter.author.display_name}")
    
    await inter.followup.send(embed=embed)
